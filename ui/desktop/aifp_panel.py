from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from core.aifp import AIFPHistoryStore, build_aifp_package, scan_project
from core.aifp.naming import build_output_filename
from ui.desktop.validator_bridge import validate_package_local


class FolderDropZone(QtWidgets.QFrame):
    pathDropped = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AIFPDropZone")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self._set_style(False)

        label = QtWidgets.QLabel("Drop a project folder here\n(or use Browse)")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("background: transparent; color: rgba(255,255,255,0.9);")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(label)

    def _set_style(self, active: bool) -> None:
        if active:
            border = "2px dashed rgba(174, 210, 255, 0.85)"
            bg = "rgba(42, 58, 82, 0.38)"
        else:
            border = "1px solid rgba(255, 255, 255, 0.20)"
            bg = "rgba(26, 30, 38, 0.28)"
        self.setStyleSheet(
            f"""
            #AIFPDropZone {{
                border: {border};
                border-radius: 14px;
                background: {bg};
            }}
            #AIFPDropZone:hover {{
                background: rgba(40, 46, 58, 0.34);
                border: 1px solid rgba(255, 255, 255, 0.30);
            }}
            """
        )

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            self._set_style(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_style(False)
        event.accept()

    def dropEvent(self, event) -> None:
        self._set_style(False)
        urls = event.mimeData().urls()
        if not urls:
            return
        self.pathDropped.emit(urls[0].toLocalFile())


class ScanAIFPWorker(QtCore.QObject):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)

    def __init__(
        self,
        *,
        folder_path: str,
        project_name: str,
        version_label: str,
        creator_name: str,
        creator_contact: str,
        mode: str,
        notes: str,
        mark_complete: bool,
    ) -> None:
        super().__init__()
        self.folder_path = folder_path
        self.project_name = project_name
        self.version_label = version_label
        self.creator_name = creator_name
        self.creator_contact = creator_contact
        self.mode = mode
        self.notes = notes
        self.mark_complete = mark_complete

    @QtCore.Slot()
    def run(self) -> None:
        try:
            store = AIFPHistoryStore()
            existing = store.load_for_root(self.folder_path)
            previous = existing.get("latest") if isinstance(existing, dict) else None
            result = scan_project(
                Path(self.folder_path),
                project_name=self.project_name,
                version_label=self.version_label,
                creator_name=self.creator_name,
                creator_contact=self.creator_contact,
                mode=self.mode,
                notes=self.notes,
                mark_complete=self.mark_complete,
                previous_snapshot=previous,
            )
            self.finished.emit(result.to_dict())
        except Exception as exc:
            self.error.emit(str(exc))


class ExportAIFPWorker(QtCore.QObject):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)

    def __init__(self, *, folder_path: str, output_dir: str, scan_payload: dict) -> None:
        super().__init__()
        self.folder_path = folder_path
        self.output_dir = output_dir
        self.scan_payload = scan_payload

    @QtCore.Slot()
    def run(self) -> None:
        try:
            from core.aifp.models import DiffSummary, FileInventoryEntry, ProjectRecord, ProjectScanResult, SnapshotRecord

            payload = self.scan_payload
            project = ProjectRecord(**payload["project"])
            snapshot = SnapshotRecord(**payload["snapshot"])
            files = [FileInventoryEntry(**item) for item in payload["files"]]
            diff = DiffSummary(**payload["diff"]) if payload.get("diff") else None
            scan_result = ProjectScanResult(
                project=project,
                snapshot=snapshot,
                files=files,
                tree=payload["tree"],
                warnings=list(payload.get("warnings", [])),
                diff=diff,
            )
            out = build_aifp_package(scan_result=scan_result, output_dir=Path(self.output_dir))
            store = AIFPHistoryStore()
            store.save_snapshot(root_path=self.folder_path, scan_result=payload, export_path=str(out))
            validation = validate_package_local(str(out))
            self.finished.emit((str(out), validation))
        except Exception as exc:
            self.error.emit(str(exc))


class AIFPPanel(QtWidgets.QWidget):
    def __init__(self, defaults) -> None:
        super().__init__()
        self._defaults = defaults
        self._scan_thread: Optional[QtCore.QThread] = None
        self._scan_worker: Optional[ScanAIFPWorker] = None
        self._export_thread: Optional[QtCore.QThread] = None
        self._export_worker: Optional[ExportAIFPWorker] = None
        self._scan_payload: Optional[dict] = None
        self._folder_path: Optional[str] = None
        self._applying_scan_payload = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignTop)

        title = QtWidgets.QLabel("Project (AIFP)")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(title)

        self.drop = FolderDropZone()
        self.drop.pathDropped.connect(self._on_drop)
        layout.addWidget(self.drop)

        row = QtWidgets.QHBoxLayout()
        self.browse_btn = QtWidgets.QPushButton("Browse Folder…")
        self.scan_btn = QtWidgets.QPushButton("Scan Project")
        self.scan_btn.setEnabled(False)
        self.export_btn = QtWidgets.QPushButton("Create Snapshot")
        self.export_btn.setEnabled(False)
        row.addWidget(self.browse_btn)
        row.addWidget(self.scan_btn)
        row.addStretch(1)
        row.addWidget(self.export_btn)
        layout.addLayout(row)

        self.browse_btn.clicked.connect(self._browse_folder)
        self.scan_btn.clicked.connect(self._start_scan)
        self.export_btn.clicked.connect(self._start_export)

        self.folder_label = QtWidgets.QLabel("No project folder selected.")
        self.folder_label.setWordWrap(True)
        self.folder_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.folder_label)

        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        self.project_name = QtWidgets.QLineEdit()
        self.version_label = QtWidgets.QLineEdit("alpha")
        self.creator_name = QtWidgets.QLineEdit(getattr(defaults, "creator_name", ""))
        self.creator_contact = QtWidgets.QLineEdit(getattr(defaults, "creator_email", ""))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["human-directed-ai", "ai-assisted", "ai-generated"])
        default_mode = getattr(defaults, "default_mode", "human-directed-ai")
        idx = self.mode_combo.findText(default_mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.output_dir = QtWidgets.QLineEdit(getattr(defaults, "default_output_dir", str(Path.home())))
        self.output_btn = QtWidgets.QPushButton("Browse…")
        self.output_btn.clicked.connect(self._browse_output_dir)
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlaceholderText("Optional notes")
        self.notes.setMaximumHeight(90)
        self.mark_complete = QtWidgets.QCheckBox("Mark Project Complete")

        out_row = QtWidgets.QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.addWidget(self.output_dir, 1)
        out_row.addWidget(self.output_btn)
        out_wrap = QtWidgets.QWidget()
        out_wrap.setLayout(out_row)

        form.addRow("Project Name:", self.project_name)
        form.addRow("Version Label:", self.version_label)
        form.addRow("Creator Name:", self.creator_name)
        form.addRow("Creator Contact:", self.creator_contact)
        form.addRow("Mode:", self.mode_combo)
        form.addRow("Output Folder:", out_wrap)
        form.addRow("Notes:", self.notes)
        form.addRow("", self.mark_complete)
        layout.addLayout(form)

        self.preview_label = QtWidgets.QLabel("Output preview: —")
        self.preview_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.preview_label)

        self.summary = QtWidgets.QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(130)
        layout.addWidget(self.summary)

        self.tree_preview = QtWidgets.QPlainTextEdit()
        self.tree_preview.setReadOnly(True)
        self.tree_preview.setMaximumHeight(160)
        layout.addWidget(self.tree_preview)

        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setMinimumHeight(140)
        layout.addWidget(self.results)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("opacity: 0.82;")
        layout.addWidget(self.status)

        self.project_name.textChanged.connect(self._refresh_preview)
        self.version_label.textChanged.connect(self._refresh_preview)
        self.output_dir.textChanged.connect(self._refresh_preview)
        self.mark_complete.stateChanged.connect(self._refresh_preview)
        self.mark_complete.stateChanged.connect(self._refresh_export_state)
        self.project_name.textChanged.connect(self._mark_scan_stale)
        self.version_label.textChanged.connect(self._mark_scan_stale)
        self.creator_name.textChanged.connect(self._mark_scan_stale)
        self.creator_contact.textChanged.connect(self._mark_scan_stale)
        self.mode_combo.currentTextChanged.connect(self._mark_scan_stale)
        self.notes.textChanged.connect(self._mark_scan_stale)
        self.mark_complete.stateChanged.connect(self._mark_scan_stale)

        self._refresh_preview()

    def reload_defaults(self) -> None:
        settings = QtCore.QSettings()
        self.creator_name.setText(str(settings.value("defaults/creator_name", "")))
        self.creator_contact.setText(str(settings.value("defaults/creator_email", "")))
        self.output_dir.setText(str(settings.value("defaults/default_output_dir", str(Path.home()))))
        mode = str(settings.value("defaults/default_mode", "human-directed-ai"))
        idx = self.mode_combo.findText(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self._refresh_preview()

    def _browse_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select project folder", self.output_dir.text() or str(Path.home()))
        if folder:
            self._set_folder(folder)

    def _browse_output_dir(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder", self.output_dir.text() or str(Path.home()))
        if folder:
            self.output_dir.setText(folder)
            self._refresh_preview()

    def _on_drop(self, path: str) -> None:
        candidate = Path(path)
        if not candidate.is_dir():
            QtWidgets.QMessageBox.information(self, "Folder required", "Drop a project folder, not a file.")
            return
        self._set_folder(str(candidate))

    def _set_folder(self, folder: str) -> None:
        resolved = str(Path(folder).expanduser().resolve())
        self._folder_path = resolved
        self._scan_payload = None
        self.folder_label.setText(f"Selected folder: {resolved}")
        if not self.project_name.text().strip():
            self.project_name.setText(Path(resolved).name)
        self.scan_btn.setEnabled(True)
        self.status.setText("Ready to scan.")
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        filename = build_output_filename(
            self.project_name.text().strip() or "project",
            self.version_label.text().strip() or "snapshot",
            locked=self.mark_complete.isChecked(),
        )
        out_dir = self.output_dir.text().strip() or str(Path.home())
        self.preview_label.setText(f"Output preview: {Path(out_dir).expanduser() / filename}")
        self.export_btn.setText("Create Final Locked Export" if self.mark_complete.isChecked() else "Create Snapshot")

    def _refresh_export_state(self) -> None:
        self.export_btn.setEnabled(self._scan_payload is not None and bool(self.output_dir.text().strip()))

    def _start_scan(self) -> None:
        if not self._folder_path:
            return
        self.results.clear()
        self.summary.clear()
        self.tree_preview.clear()
        self._scan_payload = None
        self.export_btn.setEnabled(False)
        self.status.setText("Scanning project…")

        self._scan_thread = QtCore.QThread(self)
        self._scan_worker = ScanAIFPWorker(
            folder_path=self._folder_path,
            project_name=self.project_name.text().strip(),
            version_label=self.version_label.text().strip(),
            creator_name=self.creator_name.text().strip(),
            creator_contact=self.creator_contact.text().strip(),
            mode=self.mode_combo.currentText().strip(),
            notes=self.notes.toPlainText().strip(),
            mark_complete=self.mark_complete.isChecked(),
        )
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_worker.error.connect(self._scan_thread.quit)
        self._scan_worker.error.connect(self._scan_worker.deleteLater)
        self._scan_thread.start()

    def _on_scan_error(self, message: str) -> None:
        self.status.setText("Scan failed.")
        self.results.appendPlainText(f"ERROR: {message}")

    def _on_scan_finished(self, payload: dict) -> None:
        self._scan_payload = payload
        project = payload["project"]
        snapshot = payload["snapshot"]
        warnings = payload.get("warnings", [])
        diff = payload.get("diff")

        self._applying_scan_payload = True
        self.project_name.setText(project["project_name"])
        self._applying_scan_payload = False
        self.summary.setPlainText(
            "\n".join(
                [
                    f"Project: {project['project_name']}",
                    f"Files: {snapshot['file_count']}",
                    f"Total size: {snapshot['total_bytes']} bytes",
                    f"Counts: {snapshot['asset_counts_by_type']}",
                    f"Primary candidates: {', '.join(snapshot['primary_candidates']) or 'None'}",
                    f"Warnings: {len(warnings)}",
                    f"Diff: {diff['human_summary'] if diff else 'Initial snapshot.'}",
                ]
            )
        )
        self.tree_preview.setPlainText(self._tree_to_text(payload["tree"]))
        self.results.clear()
        for warning in warnings:
            self.results.appendPlainText(f"Warning: {warning}")
        if diff:
            self.results.appendPlainText(diff["human_summary"])
        self.status.setText("Scan complete.")
        self._refresh_export_state()

    def _mark_scan_stale(self) -> None:
        if self._applying_scan_payload:
            return
        if self._scan_payload is not None:
            self._scan_payload = None
            self.export_btn.setEnabled(False)
            self.status.setText("Scan is out of date. Rescan to export.")

    def _start_export(self) -> None:
        if not self._scan_payload:
            return
        self.results.appendPlainText("Creating AIFP package…")
        self.export_btn.setEnabled(False)

        self._export_thread = QtCore.QThread(self)
        self._export_worker = ExportAIFPWorker(
            folder_path=self._folder_path or "",
            output_dir=self.output_dir.text().strip(),
            scan_payload=self._scan_payload,
        )
        self._export_worker.moveToThread(self._export_thread)
        self._export_thread.started.connect(self._export_worker.run)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.finished.connect(self._export_thread.quit)
        self._export_worker.finished.connect(self._export_worker.deleteLater)
        self._export_thread.finished.connect(self._export_thread.deleteLater)
        self._export_worker.error.connect(self._export_thread.quit)
        self._export_worker.error.connect(self._export_worker.deleteLater)
        self._export_thread.start()

    def _on_export_error(self, message: str) -> None:
        self.status.setText("Export failed.")
        self.results.appendPlainText(f"ERROR: {message}")
        self._refresh_export_state()

    def _on_export_finished(self, payload: object) -> None:
        out_path, validation = payload
        self.results.appendPlainText(f"[OK] Wrote: {out_path}")
        self.results.appendPlainText(f"Post-validate: {'PASS' if validation.get('valid') and not validation.get('errors') else 'FAIL'}")
        for key, value in sorted((validation.get("checks") or {}).items()):
            self.results.appendPlainText(f"  - {key}: {value}")
        for warning in validation.get("warnings") or []:
            self.results.appendPlainText(f"  ~ {warning}")
        for error in validation.get("errors") or []:
            self.results.appendPlainText(f"  ! {error}")
        self.status.setText("Export complete.")
        self._refresh_export_state()

    def _tree_to_text(self, node: dict, depth: int = 0) -> str:
        lines = [f"{'  ' * depth}{node.get('name', '')}/" if node.get("type") == "dir" else f"{'  ' * depth}{node.get('name', '')}"]
        for child in node.get("children", []):
            lines.append(self._tree_to_text(child, depth + 1))
        return "\n".join(lines)
