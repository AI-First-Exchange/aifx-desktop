from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../aifx
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6 import QtCore, QtWidgets, QtGui

from core.aifp.naming import is_aifx_package_path
from core.packaging.aifi_packager import build_aifi
from core.packaging.aifv_packager import build_aifv
from core.provenance.sda_templates import AIFX_SDA_001_TEXT
from ui.desktop.aifp_panel import AIFPPanel
from ui.desktop.validator_bridge import validate_package_local

# -----------------------------
# Constants / helpers
# -----------------------------

def _format_check_value(k: str, v: object) -> str:
    # Normalize integrity string values from canonical validator
    if k == "integrity" and isinstance(v, str):
        if v.lower() == "ok":
            return "PASS"
        if v.lower() == "fail":
            return "FAIL"
    return str(v)


def _check_bucket(k: str) -> int:
    # Deterministic grouping order
    if k.startswith("files."):
        return 10
    if k.startswith("security."):
        return 20
    if k.startswith(("manifest.", "work.", "author", "contact", "ai_declared", "aifx_version")):
        return 30
    if k == "integrity" or k.startswith("integrity."):
        return 40
    if k.startswith("info."):
        return 50
    return 90


def _iter_checks_grouped(checks: dict) -> list[tuple[str, object]]:
    items = list(checks.items())
    items.sort(key=lambda kv: (_check_bucket(kv[0]), kv[0]))
    return items


AIFX_PACKAGE_EXTS = (".aifx", ".aifm", ".aifv", ".aifi", ".aifp")

AUDIO_EXTS = (".wav", ".mp3", ".flac", ".m4a", ".ogg")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

PRODUCTION_ORG_NAME = "AI-First-Exchange"
PRODUCTION_APP_NAME = "AIFX Desktop"


def _abs(p: str) -> str:
    return os.path.abspath(os.path.expanduser(p))

def resource_path(rel_path: str) -> str:
    base = Path(getattr(sys, "_MEIPASS")) if hasattr(sys, "_MEIPASS") else REPO_ROOT
    return str((base / rel_path).resolve())


def checkbox_checkmark_path() -> str:
    path = Path(tempfile.gettempdir()) / "aifx_checkbox_checkmark.svg"
    if not path.exists():
        path.write_text(
            """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
<path d="M3 8.5L6.3 11.8L13 5.2" fill="none" stroke="#f8fbff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
""",
            encoding="utf-8",
        )
    return str(path)


def _declaration_view() -> QtWidgets.QLabel:
    box = QtWidgets.QLabel(AIFX_SDA_001_TEXT)
    box.setWordWrap(True)
    box.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    box.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
    box.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Minimum
    )
    box.setStyleSheet("""
        QLabel {
            border: 1px solid #3a3a3a;
            border-radius: 6px;
            padding: 8px;
            background: #1e1e1e;
        }
    """)
    return box


def collect_packages(selected_files: list[str], selected_folder: str | None = None) -> list[str]:
    files: list[str] = []

    for p in selected_files or []:
        if is_aifx_package_path(p) and os.path.isfile(p):
            files.append(_abs(p))

    if selected_folder:
        for root, _, names in os.walk(selected_folder):
            for name in names:
                if is_aifx_package_path(name):
                    fp = os.path.join(root, name)
                    if os.path.isfile(fp):
                        files.append(_abs(fp))

    return sorted(set(files))


def collect_sources_by_ext(selected_files: list[str], selected_folder: str | None, exts: tuple[str, ...]) -> list[str]:
    files: list[str] = []

    for p in selected_files or []:
        if p.lower().endswith(exts) and os.path.isfile(p):
            files.append(_abs(p))

    if selected_folder:
        for root, _, names in os.walk(selected_folder):
            for name in names:
                if name.lower().endswith(exts):
                    fp = os.path.join(root, name)
                    if os.path.isfile(fp):
                        files.append(_abs(fp))

    return sorted(set(files))


# -----------------------------
# Defaults (stored via QSettings)
# -----------------------------
@dataclass
class AppDefaults:
    creator_name: str = ""
    creator_email: str = ""
    default_mode: str = ""
    default_output_dir: str = ""

def _qsettings() -> QtCore.QSettings:
    return QtCore.QSettings()

def load_defaults() -> AppDefaults:
    qs = _qsettings()
    return AppDefaults(
        creator_name=str(qs.value("defaults/creator_name", "")),
        creator_email=str(qs.value("defaults/creator_email", "")),
        default_mode=str(qs.value("defaults/default_mode", "")),
        default_output_dir=str(qs.value("defaults/default_output_dir", "")),
    )

def save_defaults(d: AppDefaults) -> None:
    qs = _qsettings()
    qs.setValue("defaults/creator_name", d.creator_name.strip())
    qs.setValue("defaults/creator_email", d.creator_email.strip())
    qs.setValue("defaults/default_mode", d.default_mode.strip())
    qs.setValue("defaults/default_output_dir", d.default_output_dir.strip())

MODE_EXPLANATIONS = {
    "human-directed-ai": (
        "human-directed-ai: You are the main creative director. "
        "AI is a tool you steer, while you control prompts, selection, arrangement, edits, and final output."
    ),
    "ai-assisted": (
        "ai-assisted: The work is primarily human-led, but AI helps with specific parts of the workflow "
        "such as ideation, drafting, cleanup, enhancement, or support tasks."
    ),
    "ai-generated": (
        "ai-generated: The output is produced mostly by the AI system, with limited human creative intervention "
        "beyond setup, guidance, or acceptance of results."
    ),
}

# -----------------------------
# UI pieces
# -----------------------------
class SidebarButton(QtWidgets.QPushButton):
    def __init__(self, text: str, *, indent: int = 0) -> None:
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        pad_left = 12 + indent if indent else 12

        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                min-height: 32px;
                padding: 6px 12px;
                padding-left: {pad_left}px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.90);
            }}

            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.10);
                border: 1px solid rgba(255, 255, 255, 0.16);
            }}

            QPushButton:checked {{
                font-weight: 700;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.28);
                background: rgba(140, 180, 255, 0.22);
            }}

            QPushButton:checked:hover {{
                border: 1px solid rgba(255, 255, 255, 0.34);
                background: rgba(140, 180, 255, 0.28);
            }}
        """)

class DropZone(QtWidgets.QFrame):
    pathDropped = QtCore.Signal(str)

    def __init__(self, label_text: str = "Drop files here") -> None:
        super().__init__()
        self.setObjectName("DropZone")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self._set_glass_style(False)

        self.setAcceptDrops(True)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)
        self.setMinimumHeight(120)

        self.label = QtWidgets.QLabel(label_text)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent; color: rgba(255,255,255,0.9);")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self.label)

    def set_text(self, s: str) -> None:
        self.label.setText(s)

    def _set_glass_style(self, drag_active: bool) -> None:
        if drag_active:
            border = "2px dashed rgba(174, 210, 255, 0.85)"
            bg = "rgba(42, 58, 82, 0.38)"
        else:
            border = "1px solid rgba(255, 255, 255, 0.20)"
            bg = "rgba(26, 30, 38, 0.28)"
        self.setStyleSheet(f"""
        #DropZone {{
            border: {border};
            border-radius: 14px;
            background: {bg};
        }}
        #DropZone:hover {{
            background: rgba(40, 46, 58, 0.34);
            border: 1px solid rgba(255, 255, 255, 0.30);
        }}
        """)

    def dragEnterEvent(self, event: QtCore.QEvent) -> None:
        if event.mimeData().hasUrls():
            self._set_glass_style(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QtCore.QEvent) -> None:
        self._set_glass_style(False)
        event.accept()

    def dropEvent(self, event: QtCore.QEvent) -> None:
        self._set_glass_style(False)
        urls = event.mimeData().urls()
        if not urls:
            return
        p = Path(urls[0].toLocalFile())
        self.pathDropped.emit(str(p))


# -----------------------------
# Workers
# -----------------------------
class ValidateWorker(QtCore.QObject):
    finished = QtCore.Signal(object)  # list[(path, result)]
    error = QtCore.Signal(str)

    def __init__(self, package_paths: list[str]) -> None:
        super().__init__()
        self.package_paths = package_paths

    @QtCore.Slot()
    def run(self) -> None:
        try:
            results: list[tuple[str, dict]] = []
            for fp in self.package_paths:
                try:
                    res = validate_package_local(fp)
                    results.append((fp, res))
                except Exception as e:
                    results.append((fp, {"valid": False, "errors": [str(e)], "warnings": [], "checks": {}}))
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

class ConvertMusicWorker(QtCore.QObject):
    finished = QtCore.Signal(object)  # (out_path: str, validated: dict|None)
    error = QtCore.Signal(str)

    def __init__(self, aifm_inputs: object, out_path: str) -> None:
        super().__init__()
        self.aifm_inputs = aifm_inputs
        self.out_path = out_path

    @QtCore.Slot()
    def run(self) -> None:
        try:
            from core.conversion.aifm_converter import convert_to_aifm

            out = convert_to_aifm(self.aifm_inputs, Path(self.out_path))
            # Optional: auto-validate output after conversion
            try:
                v = validate_package_local(str(out))
            except Exception as e:
                v = {"valid": False, "errors": [f"Post-validate error: {e}"], "warnings": [], "checks": {}}

            self.finished.emit((str(out), v))
        except Exception as e:
            self.error.emit(str(e))

class PackAIFVWorker(QtCore.QObject):
    finished = QtCore.Signal(object)  # payload
    error = QtCore.Signal(str)

    def __init__(
        self,
        video_path: str,
        thumb_path: str,
        out_path: str,
        title: str,
        creator_name: str,
        creator_contact: str,
        mode: str,
        primary_tool: str,
        primary_tool_version: str,
        supporting_tools: list[str],
        origin_url: str,
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.thumb_path = thumb_path
        self.out_path = out_path
        self.title = title
        self.creator_name = creator_name
        self.creator_contact = creator_contact
        self.mode = mode
        self.primary_tool = primary_tool
        self.primary_tool_version = primary_tool_version
        self.supporting_tools = supporting_tools
        self.origin_url = origin_url

    @QtCore.Slot()
    def run(self) -> None:
        try:
            from core.packaging.aifv_packager import AIFVInputs, ProvenanceTool

            supporting = [ProvenanceTool(name=n) for n in self.supporting_tools[:3] if n]

            out = build_aifv(
                AIFVInputs(
                    video_path=Path(self.video_path),
                    thumb_path=Path(self.thumb_path),
                    out_path=Path(self.out_path),
                    title=self.title,
                    creator_name=self.creator_name,
                    creator_contact=self.creator_contact,
                    mode=self.mode,
                    primary_tool=ProvenanceTool(
                        name=self.primary_tool,
                        version=self.primary_tool_version or None,
                    ),
                    supporting_tools=supporting,
                    origin_url=self.origin_url or None,
                )
            )
            # Auto-validate
            v = validate_package_local(str(out))
            self.finished.emit((str(out), v))
        except Exception as e:
            self.error.emit(str(e))


class PackAIFIWorker(QtCore.QObject):
    finished = QtCore.Signal(object)  # payload
    error = QtCore.Signal(str)

    def __init__(
        self,
        image_path: str,
        out_path: str,
        title: str,
        creator_name: str,
        creator_contact: str,
        mode: str,
        primary_tool: str,
        supporting_tools: list[str],
    ) -> None:
        super().__init__()
        self.image_path = image_path
        self.out_path = out_path
        self.title = title
        self.creator_name = creator_name
        self.creator_contact = creator_contact
        self.mode = mode
        self.primary_tool = primary_tool
        self.supporting_tools = supporting_tools

    @QtCore.Slot()
    def run(self) -> None:
        try:
            out = build_aifi(
                image_path=Path(self.image_path),
                out_path=Path(self.out_path),
                title=self.title,
                creator_name=self.creator_name,
                creator_contact=self.creator_contact,
                mode=self.mode,
                primary_tool=self.primary_tool,
                supporting_tools=self.supporting_tools[:3],
            )
            v = validate_package_local(str(out))
            self.finished.emit((str(out), v))
        except Exception as e:
            self.error.emit(str(e))



# -----------------------------
# Panels
# -----------------------------
class HomePanel(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        # --- Title
        title = QtWidgets.QLabel("AIFX Desktop (v0)")
        title.setStyleSheet("font-size: 20px; font-weight: 900;")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Converter + Validator for AI-First Exchange packages.")
        subtitle.setStyleSheet("opacity: 0.8;")
        layout.addWidget(subtitle)

        layout.addSpacing(12)

        # --- Body
        body = QtWidgets.QLabel(
            """
<b>What is AIFX?</b><br>
AIFX (AI-First Exchange) is an open packaging standard for AI-generated works.
It bundles media + a manifest with <b>Self-Declared Authorship (SDA)</b>
and integrity hashes so files remain verifiable after sharing.<br><br>

<b>Supported in v0</b><br>
• Music → <b>.aifm</b><br>
• Video → <b>.aifv</b><br>
• Image → <b>.aifi</b><br>
• Package validation (PASS / WARN / FAIL)<br><br>

<b>Declaration Model</b><br>
v0 uses standardized <b>AIFX-SDA-001</b>.  
This app validates structure and integrity only — it does not perform identity verification.<br><br>

<b>Quick Start</b><br>
1. Set <b>Defaults</b><br>
2. Convert / Package<br>
3. Validate your output<br><br>

<b>Foundation</b><br>
GitHub: AI-First-Exchange / aifx-desktop
"""
        )

        body.setWordWrap(True)
        body.setTextFormat(QtCore.Qt.RichText)
        body.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        body.setStyleSheet("font-size: 13px; opacity: 0.95;")

        layout.addWidget(body)
        layout.addStretch(1)


class DefaultsPanel(QtWidgets.QWidget):
    defaultsSaved = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Defaults")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(title)

        self.creator_name = QtWidgets.QLineEdit()
        self.creator_email = QtWidgets.QLineEdit()

        self.mode_combo = QtWidgets.QComboBox()
        for mode_key, description in MODE_EXPLANATIONS.items():
            self.mode_combo.addItem(mode_key, description)
        mode_view = QtWidgets.QListView(self.mode_combo)
        mode_view.setWordWrap(False)
        mode_view.setTextElideMode(QtCore.Qt.ElideRight)
        if hasattr(mode_view, "setUniformItemSizes"):
            mode_view.setUniformItemSizes(True)
        mode_view.setMinimumWidth(220)
        mode_view.setStyleSheet("""
            QListView {
                background-color: #000000;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.20);
                outline: 0;
            }
            QListView::item {
                padding: 6px 10px;
                min-height: 24px;
            }
            QListView::item:selected {
                background-color: rgba(80, 120, 200, 0.60);
                color: #ffffff;
            }
        """)
        self.mode_combo.setView(mode_view)

        self.output_dir = QtWidgets.QLineEdit()
        
        # Make key fields readable (about ~60 chars)
        for le in (self.creator_name, self.creator_email, self.output_dir):
            le.setMinimumWidth(60)
            le.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            le.setClearButtonEnabled(True)

        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse_outdir)

        out_row = QtWidgets.QHBoxLayout()
        out_row.addWidget(self.output_dir, 1)
        out_row.addWidget(browse)

        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        form.addRow("Creator Name:", self.creator_name)
        form.addRow("Creator Email:", self.creator_email)
        form.addRow("Default Mode:", self.mode_combo)

        self.mode_help = QtWidgets.QLabel()
        self.mode_help.setWordWrap(True)
        self.mode_help.setStyleSheet("opacity: 0.82; padding-top: 2px;")
        form.addRow("", self.mode_help)

        form.addRow("Default Output Dir:", out_row)
        layout.addLayout(form)

        self.mode_combo.currentTextChanged.connect(self._refresh_mode_help)

        layout.addSpacing(10)

        self.save_btn = QtWidgets.QPushButton("Save Defaults")
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("opacity: 0.8;")
        layout.addWidget(self.status)
        layout.addStretch(1)

        self.reload()

    def reload(self) -> None:
        d = load_defaults()
        self.creator_name.setText(d.creator_name)
        self.creator_email.setText(d.creator_email)
        self.output_dir.setText(d.default_output_dir)

        idx = self.mode_combo.findText(d.default_mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self._refresh_mode_help()

    def _refresh_mode_help(self) -> None:
        description = self.mode_combo.currentData()
        if description is None:
            description = MODE_EXPLANATIONS.get(self.mode_combo.currentText(), "")
        self.mode_help.setText(str(description))

    def _browse_outdir(self) -> None:
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose default output folder", self.output_dir.text() or str(Path.home()))
        if d:
            self.output_dir.setText(d)

    def _save(self) -> None:
        d = AppDefaults(
            creator_name=self.creator_name.text().strip(),
            creator_email=self.creator_email.text().strip(),
            default_mode=self.mode_combo.currentText().strip(),
            default_output_dir=self.output_dir.text().strip(),
        )
        save_defaults(d)
        self.status.setText("Saved.")
        self.defaultsSaved.emit()


class ValidatePanel(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[ValidateWorker] = None

        self.selected_files: list[str] = []
        self.selected_folder: Optional[str] = None

        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Validate")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(title)

        self.drop = DropZone("Drop .aifm/.aifv/.aifi/.aifp/.aifp-* (or .aifx) here\n(or use Browse)")
        self.drop.pathDropped.connect(self._on_drop)
        layout.addWidget(self.drop)

        row = QtWidgets.QHBoxLayout()
        self.browse_files_btn = QtWidgets.QPushButton("Browse File(s)…")
        self.browse_folder_btn = QtWidgets.QPushButton("Browse Folder…")
        self.validate_btn = QtWidgets.QPushButton("Validate")
        self.validate_btn.setEnabled(False)

        self.browse_files_btn.clicked.connect(self._browse_files)
        self.browse_folder_btn.clicked.connect(self._browse_folder)
        self.validate_btn.clicked.connect(self.run_validate)

        row.addWidget(self.browse_files_btn)
        row.addWidget(self.browse_folder_btn)
        row.addStretch(1)
        row.addWidget(self.validate_btn)
        layout.addLayout(row)

        self.selection_path_label = QtWidgets.QLabel("No file or folder selected.")
        self.selection_path_label.setWordWrap(True)
        self.selection_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.selection_path_label.setStyleSheet("opacity: 0.82; padding-top: 2px;")
        layout.addWidget(self.selection_path_label)

        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)

        fm = self.results.fontMetrics()
        lines = 14  # adjust 10–15 to taste
        h = (fm.lineSpacing() * lines) + 16

        self.results.setMinimumHeight(h)
        self.results.setMaximumHeight(h)
        self.results.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Fixed)

        layout.addWidget(self.results)  # <-- no stretch factor

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("opacity: 0.8;")
        layout.addWidget(self.status)

        layout.addStretch(1)  # optional: keeps layout balanced

    def _on_drop(self, p: str) -> None:
        pp = Path(p)
        self.selected_files = []
        self.selected_folder = None

        if pp.is_dir():
            self.selected_folder = str(pp)
            self.status.setText(f"Folder selected: {pp}")
            self.selection_path_label.setText(f"Selected folder: {pp}")
        else:
            self.selected_files = [str(pp)]
            self.status.setText(f"File selected: {pp}")
            self.selection_path_label.setText(f"Selected file: {pp}")

        self.validate_btn.setEnabled(True)

    def _browse_files(self) -> None:
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select AIFX package(s)",
            "",
            "AIFX Packages (*.aifx *.aifm *.aifv *.aifi *.aifp *.aifp-*);;All files (*)",
        )
        if files:
            self.selected_files = files
            self.selected_folder = None
            self.status.setText(f"{len(files)} file(s) selected.")
            if len(files) == 1:
                self.selection_path_label.setText(f"Selected file: {files[0]}")
            else:
                self.selection_path_label.setText("Selected files:\n" + "\n".join(files))
            self.validate_btn.setEnabled(True)

    def _browse_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder to scan (recursive)", "")
        if folder:
            self.selected_folder = folder
            self.selected_files = []
            self.status.setText(f"Folder selected: {folder}")
            self.selection_path_label.setText(f"Selected folder: {folder}")
            self.validate_btn.setEnabled(True)

    def run_validate(self) -> None:
        targets = collect_packages(self.selected_files, self.selected_folder)

        if not targets:
            QtWidgets.QMessageBox.information(self, "No input", "Pick a package or folder first.")
            return

        self.results.clear()
        self.results.appendPlainText("Running local validation…")
        self.validate_btn.setEnabled(False)

        self._thread = QtCore.QThread(self)
        self._worker = ValidateWorker(targets)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._worker.error.connect(self._thread.quit)
        self._worker.error.connect(self._worker.deleteLater)

        self._thread.start()

    def _on_error(self, msg: str) -> None:
        self.results.appendPlainText("")
        self.results.appendPlainText(f"ERROR: {msg}")
        self.validate_btn.setEnabled(True)

    def _on_finished(self, results: list[tuple[str, dict]]) -> None:
        passes = 0
        fails = 0

        self.results.appendPlainText("")
        for fp, res in results:
            valid = bool(res.get("valid", False))
            checks = res.get("checks", {}) or {}
            warnings = res.get("warnings", []) or []
            errors = res.get("errors", []) or []

            if valid and not errors:
                passes += 1
                verdict = "PASS"
            else:
                fails += 1
                verdict = "FAIL"

            self.results.appendPlainText(f"[{verdict}] {fp}")
            if checks:
                self.results.appendPlainText("  Checks:")
                for k, v in _iter_checks_grouped(checks):
                    self.results.appendPlainText(f"    - {k}: {_format_check_value(k, v)}")
            if warnings:
                self.results.appendPlainText("  Warnings:")
                for w in warnings:
                    self.results.appendPlainText(f"    - {w}")
            if errors:
                self.results.appendPlainText("  Errors:")
                for e in errors:
                    self.results.appendPlainText(f"    - {e}")
            self.results.appendPlainText("")

        self.status.setText(f"Done. PASS={passes} FAIL={fails}")
        self.validate_btn.setEnabled(True)


class ConvertMusicPanel(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[ConvertMusicWorker] = None

        self.selected_file: Optional[str] = None

        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Convert → Music (Single Track)")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(title)

        self.drop = DropZone("Drop ONE .wav/.mp3/.flac/.m4a/.ogg here\n(or use Browse)")
        self.drop.pathDropped.connect(self._on_drop)
        layout.addWidget(self.drop)

        row = QtWidgets.QHBoxLayout()
        self.browse_file_btn = QtWidgets.QPushButton("Browse File…")
        self.convert_btn = QtWidgets.QPushButton("Convert to .aifm")
        self.convert_btn.setEnabled(False)

        self.browse_file_btn.clicked.connect(self._browse_file)
        self.convert_btn.clicked.connect(self.run_convert)

        row.addWidget(self.browse_file_btn)
        row.addStretch(1)
        row.addWidget(self.convert_btn)
        layout.addLayout(row)

        # ---- Creator fields (auto-fill from defaults if present, but editable) ----
        self.creator_name = QtWidgets.QLineEdit()
        self.creator_email = QtWidgets.QLineEdit()

        # ---- Required per-track fields ----
        self.origin_platform = QtWidgets.QLineEdit()
        self.origin_url = QtWidgets.QLineEdit()
        self.ai_system = QtWidgets.QLineEdit()

        self.origin_platform.setPlaceholderText("e.g., Suno, Udio, ElevenLabs, Custom")
        self.origin_url.setPlaceholderText("https://… (optional)")
        self.ai_system.setPlaceholderText("e.g., Suno (required)")

        # Convenience: mirror origin platform → ai_system unless user edits ai_system
        self._ai_system_user_touched = False
        self.ai_system.textEdited.connect(self._mark_ai_system_touched)
        self.origin_platform.textChanged.connect(self._maybe_mirror_ai_system)

        # ---- Optional metadata ----
        self.persona = QtWidgets.QLineEdit()
        self.cover_path = QtWidgets.QLineEdit()
        self.cover_browse = QtWidgets.QPushButton("Browse…")
        self.cover_browse.clicked.connect(self._browse_cover)

        self.music_title = QtWidgets.QLineEdit()
        self.music_title.setPlaceholderText("Song title (auto-filled from filename)")

        self.selected_file_label = QtWidgets.QLabel("")
        self.selected_file_label.setStyleSheet("opacity: 0.7;")
        self.selected_file_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.selected_file_label.setMinimumWidth(120)

        # Make important fields readable
        for le in (
            self.creator_name,
            self.creator_email,
            self.origin_platform,
            self.origin_url,
            self.ai_system,
            self.persona,
            self.cover_path,
            self.music_title,
        ):
            le.setMinimumWidth(60)
            le.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            le.setClearButtonEnabled(True)

        cover_row = QtWidgets.QHBoxLayout()
        cover_row.setContentsMargins(0, 0, 0, 0)
        cover_row.addWidget(self.cover_path, 1)
        cover_row.addWidget(self.cover_browse)

        self.prompt_text = QtWidgets.QPlainTextEdit()
        self.prompt_text.setPlaceholderText("Optional prompt…")

        self.lyrics_text = QtWidgets.QPlainTextEdit()
        self.lyrics_text.setPlaceholderText("Optional lyrics…")

        # Output .aifm (file path)
        self.out_path = QtWidgets.QLineEdit()
        self.out_path.setPlaceholderText("Output .aifm path (e.g., ~/Desktop/MySong.aifm)")
        self.out_btn = QtWidgets.QPushButton("Browse…")
        self.out_btn.clicked.connect(self._browse_out_aifm)

        out_row = QtWidgets.QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.addWidget(self.out_path, 1)
        out_row.addWidget(self.out_btn)

        self.declaration_view = _declaration_view()
        self.declaration_ack_cb = QtWidgets.QCheckBox("I affirm this SDA declaration (AIFX-SDA-001).")

        # Form layout
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        form.addRow("Creator Name (required):", self.creator_name)
        form.addRow("Creator Email (required):", self.creator_email)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(self.music_title, 1)
        title_row.addWidget(self.selected_file_label)

        form.addRow("Title (required):", title_row)
        form.addRow("Origin Platform (required):", self.origin_platform)
        form.addRow("Origin URL (optional):", self.origin_url)
        form.addRow("AI System (required):", self.ai_system)
        form.addRow("Persona (optional):", self.persona)
        form.addRow("Cover image (optional):", cover_row)
        form.addRow("Output .aifm (required):", out_row)

        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel("Declaration (AIFX-SDA-001):"))
        layout.addWidget(self.declaration_ack_cb)
        layout.addWidget(self.declaration_view, 0)
        self.declaration_view.setFixedHeight(120)

        layout.addWidget(QtWidgets.QLabel("Prompt (optional):"))
        layout.addWidget(self.prompt_text, 1)
        layout.addWidget(QtWidgets.QLabel("Lyrics (optional):"))
        layout.addWidget(self.lyrics_text, 1)

        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.results, 2)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("opacity: 0.8;")
        layout.addWidget(self.status)

        # Gate convert button as fields change
        self.origin_platform.textChanged.connect(self._refresh_convert_enabled)
        self.origin_url.textChanged.connect(self._refresh_convert_enabled)
        self.ai_system.textChanged.connect(self._refresh_convert_enabled)
        self.declaration_ack_cb.stateChanged.connect(self._refresh_convert_enabled)

        self.creator_name.textChanged.connect(self._refresh_convert_enabled)
        self.creator_email.textChanged.connect(self._refresh_convert_enabled)
        self.music_title.textChanged.connect(self._refresh_convert_enabled)
        self.out_path.textChanged.connect(self._refresh_convert_enabled)

        # ✅ Load defaults once (only fill if empty)
        self.reload_defaults()

        self._refresh_convert_enabled()

    def _mark_ai_system_touched(self) -> None:
        self._ai_system_user_touched = True

    def _maybe_mirror_ai_system(self, text: str) -> None:
        if not self._ai_system_user_touched:
            self.ai_system.setText(text)

    def reload_defaults(self) -> None:
        d = load_defaults()
        # Only fill if empty, so user can override and it works without defaults too
        if not self.creator_name.text().strip():
            self.creator_name.setText(d.creator_name)
        if not self.creator_email.text().strip():
            self.creator_email.setText(d.creator_email)

    def _reset_form(self) -> None:
        self.selected_file = None
        self.selected_file_label.setText("No file selected")

        # Clear known per-conversion fields.
        self.music_title.clear()
        self.creator_name.clear()
        self.creator_email.clear()
        self.origin_platform.clear()
        self.origin_url.clear()
        self.ai_system.clear()
        self.persona.clear()
        self.cover_path.clear()
        self.out_path.clear()
        self.prompt_text.clear()
        self.lyrics_text.clear()

        # Clear optional alias fields if present.
        for name in (
            "title_field",
            "creator_name_field",
            "creator_contact_field",
            "primary_tool_field",
            "supporting_tools_field",
            "origin_url_field",
            "cover_path_field",
            "out_path_field",
        ):
            w = getattr(self, name, None)
            if w is not None and hasattr(w, "clear"):
                w.clear()

        self.declaration_ack_cb.setChecked(False)
        self.results.clear()
        self.status.setText("")

        if hasattr(self, "results_text"):
            self.results_text.clear()
        if hasattr(self, "status_label"):
            self.status_label.setText("")

        self._ai_system_user_touched = False
        self.reload_defaults()
        self._refresh_convert_enabled()

    def _on_drop(self, p: str) -> None:
        pp = Path(p)
        if pp.is_dir():
            QtWidgets.QMessageBox.information(
                self, "Single track only",
                "Music conversion is single-track only. Drop an audio file, not a folder."
            )
            return

        if pp.suffix.lower() not in AUDIO_EXTS:
            QtWidgets.QMessageBox.information(
                self, "Unsupported file",
                "Please drop a supported audio file (.wav/.mp3/.flac/.m4a/.ogg)."
            )
            return

        self.selected_file = str(pp)
        self.status.setText(f"Selected: {pp.name}")
        self.selected_file_label.setText(f"({pp.name})")

        # Auto-fill title if empty
        if not self.music_title.text().strip():
            self.music_title.setText(pp.stem)

        # Auto-suggest output if empty
        if not self.out_path.text().strip():
            self._autofill_out_path_from_selected(pp)

        self._refresh_convert_enabled()

    def _browse_file(self) -> None:
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select one audio file",
            str(Path.home()),
            "Audio Files (*.wav *.mp3 *.flac *.m4a *.ogg)",
        )
        if file:
            self.selected_file = file
            pp = Path(file)
            self.status.setText(f"Selected: {pp.name}")
            self.selected_file_label.setText(f"({pp.name})")

            if not self.music_title.text().strip():
                self.music_title.setText(pp.stem)

            if not self.out_path.text().strip():
                self._autofill_out_path_from_selected(pp)

            self._refresh_convert_enabled()

    def _browse_cover(self) -> None:
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select cover image (optional)",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if file:
            self.cover_path.setText(file)

    def _browse_out_aifm(self) -> None:
        d = load_defaults()
        start_dir = str(Path.home())

        try:
            cur = self.out_path.text().strip()
            if cur:
                start_dir = str(Path(cur).expanduser().resolve().parent)
            elif getattr(d, "default_output_dir", ""):
                start_dir = str(Path(d.default_output_dir).expanduser().resolve())
            elif self.selected_file:
                start_dir = str(Path(self.selected_file).expanduser().resolve().parent)
        except Exception:
            pass

        default_name = "track.aifm"
        try:
            if self.music_title.text().strip():
                default_name = f"{self.music_title.text().strip()}.aifm"
            elif self.selected_file:
                default_name = f"{Path(self.selected_file).stem}.aifm"
        except Exception:
            pass

        fp, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save AIFM package as…",
            str(Path(start_dir) / default_name),
            "AIFM Package (*.aifm);;All files (*)",
        )
        if fp:
            if not fp.lower().endswith(".aifm"):
                fp += ".aifm"
            self.out_path.setText(fp)
            self._refresh_convert_enabled()

    def _autofill_out_path_from_selected(self, pp: Path) -> None:
        d = load_defaults()
        base_dir = None
        try:
            if getattr(d, "default_output_dir", ""):
                base_dir = Path(d.default_output_dir).expanduser()
        except Exception:
            base_dir = None

        if not base_dir:
            base_dir = pp.expanduser().resolve().parent

        title = self.music_title.text().strip() or pp.stem
        self.out_path.setText(str((base_dir / f"{title}.aifm").resolve()))

    def _refresh_convert_enabled(self) -> None:
        has_file = bool(self.selected_file)

        creator_ok = bool(self.creator_name.text().strip()) and bool(self.creator_email.text().strip())

        req_ok = (
            bool(self.music_title.text().strip())
            and bool(self.origin_platform.text().strip())
            and bool(self.ai_system.text().strip())
        )

        out_ok = bool(self.out_path.text().strip())
        confirmed = self.declaration_ack_cb.isChecked()

        self.convert_btn.setEnabled(bool(has_file and creator_ok and req_ok and out_ok and confirmed))

    def run_convert(self) -> None:
        if not self.selected_file:
            QtWidgets.QMessageBox.information(self, "No input", "Select one audio file first.")
            return
        if not self.convert_btn.isEnabled():
            QtWidgets.QMessageBox.information(
                self, "Missing required fields",
                "Fill required fields, set an output .aifm path, and check confirmation."
            )
            return

        srcp = Path(self.selected_file)

        out_path = Path(_abs(self.out_path.text().strip()))
        out_path.parent.mkdir(parents=True, exist_ok=True)

        title = self.music_title.text().strip() or srcp.stem

        # Build AIFM inputs
        from core.conversion.aifm_converter import AIFMInputs

        cover = self.cover_path.text().strip()
        cover_path = Path(cover).expanduser() if cover else None

        inp = AIFMInputs(
            audio_path=srcp,
            title=title,
            creator_name=self.creator_name.text().strip(),
            creator_contact=self.creator_email.text().strip(),
            mode="human-directed-ai",
            ai_system=self.ai_system.text().strip(),
            origin_platform=self.origin_platform.text().strip(),
            origin_url=self.origin_url.text().strip(),
            prompt_text=self.prompt_text.toPlainText().strip() or None,
            lyrics_text=self.lyrics_text.toPlainText().strip() or None,
            persona_text=self.persona.text().strip() or None,
            cover_image_path=cover_path,
        )

        self.results.clear()
        self.results.appendPlainText("Converting to .aifm…")
        self.convert_btn.setEnabled(False)

        self._thread = QtCore.QThread(self)
        self._worker = ConvertMusicWorker(inp, str(out_path))
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._worker.error.connect(self._thread.quit)
        self._worker.error.connect(self._worker.deleteLater)

        self._thread.start()

    def _on_error(self, msg: str) -> None:
        self.results.appendPlainText("")
        self.results.appendPlainText(f"ERROR: {msg}")
        self._refresh_convert_enabled()

    def _on_finished(self, payload: object) -> None:
        out_path, v = payload

        self.results.appendPlainText("")
        self.results.appendPlainText(f"[OK] Wrote: {out_path}")

        valid = bool(v.get("valid", False))
        errs = v.get("errors", []) or []
        warns = v.get("warnings", []) or []
        checks = v.get("checks", {}) or {}

        self.results.appendPlainText("")
        self.results.appendPlainText(f"Post-validate: {'PASS' if valid and not errs else 'FAIL'}")
        if checks:
            self.results.appendPlainText("Checks:")
            for k, vv in _iter_checks_grouped(checks):
                self.results.appendPlainText(f"  - {k}: {_format_check_value(k, vv)}")
        if warns:
            self.results.appendPlainText("Warnings:")
            for w in warns:
                self.results.appendPlainText(f"  - {w}")
        if errs:
            self.results.appendPlainText("Errors:")
            for e in errs:
                self.results.appendPlainText(f"  - {e}")

        self.status.setText("Done.")
        self._refresh_convert_enabled()
        self._reset_form()

class PackAIFVPanel(QtWidgets.QWidget):
    def __init__(self, defaults: AppDefaults) -> None:
        super().__init__()
        self._defaults = defaults
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[PackAIFVWorker] = None

        self.video_path: Optional[str] = None
        self.thumb_path: Optional[str] = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignTop)     # ✅ prevents the “big gap”
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QtWidgets.QLabel("Package → Video (AIFV)")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(title)

        # --- Pickers row
        pick_row = QtWidgets.QGridLayout()
        layout.addLayout(pick_row)

        self.video_lbl = QtWidgets.QLabel("Video:")
        self.video_path_lbl = QtWidgets.QLabel("—")
        self.video_path_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.video_btn = QtWidgets.QPushButton("Browse Video…")

        self.thumb_lbl = QtWidgets.QLabel("Thumbnail:")
        self.thumb_path_lbl = QtWidgets.QLabel("—")
        self.thumb_path_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.thumb_btn = QtWidgets.QPushButton("Browse Thumb…")

        pick_row.setColumnStretch(0, 0)  # labels
        pick_row.setColumnStretch(1, 1)  # path expands
        pick_row.setColumnStretch(2, 0)  # buttons fixed
        pick_row.setHorizontalSpacing(10)
        pick_row.setVerticalSpacing(10)

        self.video_path_lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.thumb_path_lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        pick_row.addWidget(self.video_lbl, 0, 0)
        pick_row.addWidget(self.video_path_lbl, 0, 1)
        pick_row.addWidget(self.video_btn, 0, 2)

        pick_row.addWidget(self.thumb_lbl, 1, 0)
        pick_row.addWidget(self.thumb_path_lbl, 1, 1)
        pick_row.addWidget(self.thumb_btn, 1, 2)

        self.video_btn.clicked.connect(self._browse_video)
        self.thumb_btn.clicked.connect(self._browse_thumb)

        self.video_btn.setMinimumWidth(160)
        self.thumb_btn.setMinimumWidth(160)

        # --- Form (WRAPPED so it cannot steal vertical space)
        form_wrap = QtWidgets.QWidget()
        form_wrap.setContentsMargins(0, 0, 0, 0)
        form_wrap.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        form = QtWidgets.QFormLayout(form_wrap)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        form.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)

        # IMPORTANT: add the wrapper widget, NOT the layout
        layout.addWidget(form_wrap)

        self.work_title = QtWidgets.QLineEdit()
        self.work_title.setPlaceholderText("Title (required)")
        self.creator_name = QtWidgets.QLineEdit(defaults.creator_name)
        self.creator_name.setPlaceholderText("Creator name (required)")
        self.creator_contact = QtWidgets.QLineEdit(defaults.creator_email)
        self.creator_contact.setPlaceholderText("Creator contact / email (required)")
        self.primary_tool = QtWidgets.QLineEdit()
        self.primary_tool.setPlaceholderText("Primary tool (required)")
        self.primary_tool_version = QtWidgets.QLineEdit()
        self.primary_tool_version.setPlaceholderText("Primary tool version (optional)")
        self.supporting_tools = QtWidgets.QLineEdit()
        self.origin_url = QtWidgets.QLineEdit()
        self.origin_url.setPlaceholderText("Origin URL (optional)")
        self.supporting_tools.setPlaceholderText("Supporting tools (optional, comma-separated, max 3)")

        # Do NOT force widths (it causes clipping in scroll area)
        for w in (self.work_title, self.creator_name, self.creator_contact):
            w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        self.out_path = QtWidgets.QLineEdit()
        self.out_path.setPlaceholderText("Output .aifv path (e.g., ~/Desktop/MyVideo.aifv)")
        self.out_path.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        # Output row with browse button
        self.out_btn = QtWidgets.QPushButton("Browse…")
        self.out_btn.setMinimumWidth(120)
        self.out_btn.clicked.connect(self._browse_out)

        out_row = QtWidgets.QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.setSpacing(10)
        out_row.addWidget(self.out_path, 1)
        out_row.addWidget(self.out_btn)

        out_wrap = QtWidgets.QWidget()
        out_wrap.setContentsMargins(0, 0, 0, 0)
        out_wrap.setLayout(out_row)



        # Add rows
        form.addRow("Title (required)", self.work_title)
        form.addRow("Creator Name (required)", self.creator_name)
        form.addRow("Creator Contact (required)", self.creator_contact)
        form.addRow("Primary Tool (required)", self.primary_tool)
        form.addRow("Primary Tool Version (optional)", self.primary_tool_version)
        form.addRow("Supporting Tools (optional)", self.supporting_tools)
        form.addRow("Origin URL (optional)", self.origin_url)
        form.addRow("Output .aifv (required)", out_wrap)   # ✅ add WIDGET, not layout

        self.declaration_view = _declaration_view()
        self.declaration_ack_cb = QtWidgets.QCheckBox("I affirm this SDA declaration (AIFX-SDA-001).")

        layout.addWidget(QtWidgets.QLabel("Declaration (AIFX-SDA-001):"))
        layout.addWidget(self.declaration_ack_cb)
        layout.addWidget(self.declaration_view)

        # --- Buttons
        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)

        self.pack_btn = QtWidgets.QPushButton("Package AIFV")
        self.pack_btn.setEnabled(False)
        btn_row.addStretch(1)
        btn_row.addWidget(self.pack_btn)

        self.pack_btn.clicked.connect(self.run_pack)

        # --- Results (compact, scrollable)
        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)

        fm = self.results.fontMetrics()
        h = (fm.lineSpacing() * 5) + 16  # ~5 lines

        self.results.setMinimumHeight(h)
        self.results.setMaximumHeight(h)
        self.results.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        layout.addWidget(self.results)

        self._refresh_enabled()

        # Live refresh
        self.work_title.textChanged.connect(self._refresh_enabled)
        self.creator_name.textChanged.connect(self._refresh_enabled)
        self.creator_contact.textChanged.connect(self._refresh_enabled)
        self.out_path.textChanged.connect(self._refresh_enabled)
        self.primary_tool.textChanged.connect(self._refresh_enabled)
        self.declaration_ack_cb.stateChanged.connect(self._refresh_enabled)

    def reload_defaults(self) -> None:
        d = load_defaults()

        # If you have these fields in the panel, populate them.
        # Adjust names to match your widgets.
        if hasattr(self, "creator_name"):
            self.creator_name.setText(d.creator_name)
        if hasattr(self, "creator_email"):
            self.creator_email.setText(d.creator_email)
        if hasattr(self, "output_dir"):
            self.output_dir.setText(d.default_output_dir)

    def _set_status(self, text: str) -> None:
        if hasattr(self, "status"):
            self.status.setText(text)
        elif hasattr(self, "status_label"):
            self.status_label.setText(text)

    def _reset_form(self) -> None:
        self.video_path = ""
        self.thumb_path = ""
        self.video_path_lbl.setText("No file selected")
        self.thumb_path_lbl.setText("No file selected")

        self.work_title.clear()
        self.creator_name.clear()
        self.creator_contact.clear()
        self.primary_tool.clear()
        self.primary_tool_version.clear()
        self.supporting_tools.clear()
        self.origin_url.clear()
        self.out_path.clear()

        for name in (
            "work_title_field",
            "creator_name_field",
            "creator_contact_field",
            "primary_tool_field",
            "primary_tool_version_field",
            "supporting_tools_field",
            "origin_url_field",
            "out_path_field",
        ):
            w = getattr(self, name, None)
            if w is not None and hasattr(w, "clear"):
                w.clear()

        self.declaration_ack_cb.setChecked(False)
        self.results.clear()
        if hasattr(self, "results_text"):
            self.results_text.clear()
        self._set_status("")

        self.reload_defaults()
        self._refresh_enabled()

    def _browse_video(self) -> None:
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select video", str(Path.home()), "Video (*.mp4 *.mov *.webm *.m4v);;All files (*)"
        )
        if fp:
            self.video_path = fp
            self.video_path_lbl.setText(fp)
            self._refresh_enabled()

    def _browse_thumb(self) -> None:
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select thumbnail", str(Path.home()), "Image (*.jpg *.jpeg *.png *.webp);;All files (*)"
        )
        if fp:
            self.thumb_path = fp
            self.thumb_path_lbl.setText(fp)
            self._refresh_enabled()

    def _browse_out(self) -> None:
        # Default directory: whatever is in the box, else defaults output dir, else home
        start_dir = str(Path.home())
        try:
            cur = self.out_path.text().strip()
            if cur:
                start_dir = str(Path(cur).expanduser().resolve().parent)
            elif hasattr(self, "_defaults") and getattr(self._defaults, "default_output_dir", ""):
                start_dir = str(Path(self._defaults.default_output_dir).expanduser().resolve())
        except Exception:
            pass

        fp, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save AIFV package as…",
            str(Path(start_dir) / "video.aifv"),
            "AIFV Package (*.aifv);;All files (*)",
        )  
        if fp:
            if not fp.lower().endswith(".aifv"):
                fp += ".aifv"
            self.out_path.setText(fp)
            self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        ok = True
        ok = ok and bool(self.video_path)
        ok = ok and bool(self.thumb_path)
        ok = ok and bool(self.work_title.text().strip())
        ok = ok and bool(self.creator_name.text().strip())
        ok = ok and bool(self.creator_contact.text().strip())
        ok = ok and bool(self.out_path.text().strip())
        ok = ok and bool(self.primary_tool.text().strip())
        ok = ok and self.declaration_ack_cb.isChecked()
        self.pack_btn.setEnabled(ok)

    def run_pack(self) -> None:
        self.results.clear()
        self.results.appendPlainText("Packaging to .aifv…")
        self.pack_btn.setEnabled(False)

        outp = _abs(self.out_path.text().strip())

        self._thread = QtCore.QThread(self)
        self._worker = PackAIFVWorker(
            video_path=str(self.video_path),
            thumb_path=str(self.thumb_path),
            out_path=outp,
            title=self.work_title.text().strip(),
            creator_name=self.creator_name.text().strip(),
            creator_contact=self.creator_contact.text().strip(),
            mode="human-directed-ai",
            primary_tool=self.primary_tool.text().strip(),
            primary_tool_version=self.primary_tool_version.text().strip(),
            supporting_tools=[
                n.strip()
                for n in self.supporting_tools.text().split(",")
                if n.strip()
            ][:3],
            origin_url=self.origin_url.text().strip(),
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._worker.error.connect(self._thread.quit)
        self._worker.error.connect(self._worker.deleteLater)

        self._thread.start()

    def _on_error(self, msg: str) -> None:
        self.results.appendPlainText("")
        self.results.appendPlainText(f"ERROR: {msg}")
        self._set_status("Failed.")
        self._refresh_enabled()

    def _on_finished(self, payload: object) -> None:
        out_path, v = payload

        self.results.appendPlainText("")
        self.results.appendPlainText(f"[OK] Wrote: {out_path}")

        valid = bool(v.get("valid", False))
        errs = v.get("errors", []) or []
        warns = v.get("warnings", []) or []
        checks = v.get("checks", {}) or {}

        self.results.appendPlainText("")
        self.results.appendPlainText(f"Post-validate: {'PASS' if valid and not errs else 'FAIL'}")

        if checks:
            self.results.appendPlainText("Checks:")
            for k, vv in _iter_checks_grouped(checks):
                self.results.appendPlainText(f"  - {k}: {_format_check_value(k, vv)}")

        if warns:
            self.results.appendPlainText("Warnings:")
            for w in warns:
                self.results.appendPlainText(f"  - {w}")

        if errs:
            self.results.appendPlainText("Errors:")
            for e in errs:
                self.results.appendPlainText(f"  - {e}")

        self._set_status("Done.")
        self._refresh_enabled()
        QtCore.QTimer.singleShot(0, self._reset_form)

class PackAIFIPanel(QtWidgets.QWidget):
    def __init__(self, defaults: AppDefaults) -> None:
        super().__init__()
        self._defaults = defaults
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[PackAIFIWorker] = None

        self.image_path: Optional[str] = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignTop)

        title = QtWidgets.QLabel("Package → Image (AIFI)")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(title)

        pick_row = QtWidgets.QGridLayout()
        layout.addLayout(pick_row)

        self.image_lbl = QtWidgets.QLabel("Image:")
        self.image_path_lbl = QtWidgets.QLabel("—")
        self.image_path_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.image_btn = QtWidgets.QPushButton("Browse Image…")
        self.image_btn.clicked.connect(self._browse_image)
        self.image_btn.setMinimumWidth(120)

        pick_row.addWidget(self.image_lbl, 0, 0)
        pick_row.addWidget(self.image_path_lbl, 0, 1)
        pick_row.addWidget(self.image_btn, 0, 2)
        pick_row.setColumnStretch(1, 1)
        pick_row.setHorizontalSpacing(10)
        pick_row.setVerticalSpacing(10)

        # --- Form (WRAPPED so it cannot steal vertical space)
        form_wrap = QtWidgets.QWidget()
        form_wrap.setContentsMargins(0, 0, 0, 0)
        form_wrap.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        form = QtWidgets.QFormLayout(form_wrap)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        form.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)

        layout.addWidget(form_wrap)

        self.work_title = QtWidgets.QLineEdit()
        self.work_title.setPlaceholderText("Title (required)")
        self.creator_name = QtWidgets.QLineEdit(defaults.creator_name)
        self.creator_name.setPlaceholderText("Creator name (required)")
        self.creator_contact = QtWidgets.QLineEdit(defaults.creator_email)
        self.creator_contact.setPlaceholderText("Creator contact / email (required)")
        self.primary_tool = QtWidgets.QLineEdit()
        self.primary_tool.setPlaceholderText("Primary tool (required)")
        self.supporting_tools = QtWidgets.QLineEdit()
        self.supporting_tools.setPlaceholderText("Supporting tools (optional, comma-separated, max 3)")

        self.out_path = QtWidgets.QLineEdit()
        self.out_path.setPlaceholderText("Output .aifi path (required, e.g., ~/Desktop/MyImage.aifi)")
        self.out_btn = QtWidgets.QPushButton("Browse…")
        self.out_btn.clicked.connect(self._browse_out)

        out_row = QtWidgets.QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.addWidget(self.out_path, 1)
        out_row.addWidget(self.out_btn)

        # macOS clipping guard (because of global padding)
        for w in (
            self.work_title, self.creator_name, self.creator_contact,
            self.primary_tool, self.supporting_tools, self.out_path
        ):
            w.setMinimumHeight(34)

        form.addRow("Title (required)", self.work_title)
        form.addRow("Creator Name (required)", self.creator_name)
        form.addRow("Creator Contact (required)", self.creator_contact)
        form.addRow("Primary Tool (required)", self.primary_tool)
        form.addRow("Supporting Tools (optional)", self.supporting_tools)
        form.addRow("Output .aifi (required)", out_row)

        # Lock wrapper height AFTER rows exist
        form_wrap.setFixedHeight(form_wrap.sizeHint().height() + 2)

        self.declaration_view = _declaration_view()
        self.declaration_ack_cb = QtWidgets.QCheckBox("I affirm this SDA declaration (AIFX-SDA-001).")
        layout.addWidget(QtWidgets.QLabel("Declaration (AIFX-SDA-001):"))
        layout.addWidget(self.declaration_ack_cb)
        layout.addWidget(self.declaration_view)
        
        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)
        self.pack_btn = QtWidgets.QPushButton("Package AIFI")
        self.pack_btn.setEnabled(False)
        btn_row.addStretch(1)
        btn_row.addWidget(self.pack_btn)
        self.pack_btn.clicked.connect(self.run_pack)

        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setMinimumHeight(150)
        self.results.setMaximumHeight(220)
        self.results.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(self.results)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("opacity: 0.85;")
        layout.addWidget(self.status)

        self.work_title.textChanged.connect(self._refresh_enabled)
        self.creator_name.textChanged.connect(self._refresh_enabled)
        self.creator_contact.textChanged.connect(self._refresh_enabled)
        self.primary_tool.textChanged.connect(self._refresh_enabled)
        self.out_path.textChanged.connect(self._refresh_enabled)
        self.declaration_ack_cb.stateChanged.connect(self._refresh_enabled)
        self._refresh_enabled()

    def reload_defaults(self) -> None:
        d = load_defaults()
        self.creator_name.setText(d.creator_name)
        self.creator_contact.setText(d.creator_email)

    def _reset_form(self) -> None:
        self.image_path = ""
        self.image_path_lbl.setText("No file selected")

        self.work_title.clear()
        self.creator_name.clear()
        self.creator_contact.clear()
        self.primary_tool.clear()
        self.supporting_tools.clear()
        self.out_path.clear()

        for name in (
            "work_title_field",
            "creator_name_field",
            "creator_contact_field",
            "primary_tool_field",
            "supporting_tools_field",
            "origin_url_field",
            "out_path_field",
        ):
            w = getattr(self, name, None)
            if w is not None and hasattr(w, "clear"):
                w.clear()

        if hasattr(self, "origin_url") and hasattr(self.origin_url, "clear"):
            self.origin_url.clear()

        self.declaration_ack_cb.setChecked(False)
        self.results.clear()
        self.status.setText("")
        if hasattr(self, "results_text"):
            self.results_text.clear()
        if hasattr(self, "status_label"):
            self.status_label.setText("")

        self.reload_defaults()
        self._refresh_enabled()

    def _browse_image(self) -> None:
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select image", str(Path.home()), "Image (*.png *.jpg *.jpeg *.webp);;All files (*)"
        )
        if fp:
            self.image_path = fp
            self.image_path_lbl.setText(fp)
            if not self.work_title.text().strip():
                self.work_title.setText(Path(fp).stem)
            self._refresh_enabled()

    def _browse_out(self) -> None:
        start_dir = str(Path.home())
        try:
            cur = self.out_path.text().strip()
            if cur:
                start_dir = str(Path(cur).expanduser().resolve().parent)
            elif self.image_path:
                start_dir = str(Path(self.image_path).expanduser().resolve().parent)
            elif self._defaults.default_output_dir:
                start_dir = str(Path(self._defaults.default_output_dir).expanduser().resolve())
        except Exception:
            pass

        fp, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save AIFI package as…",
            str(Path(start_dir) / "image.aifi"),
            "AIFI Package (*.aifi);;All files (*)",
        )
        if fp:
            if not fp.lower().endswith(".aifi"):
                fp += ".aifi"
            self.out_path.setText(fp)
            self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        ok = True
        ok = ok and bool(self.image_path)
        ok = ok and bool(self.work_title.text().strip())
        ok = ok and bool(self.creator_name.text().strip())
        ok = ok and bool(self.creator_contact.text().strip())
        ok = ok and bool(self.primary_tool.text().strip())
        ok = ok and bool(self.out_path.text().strip())
        ok = ok and self.declaration_ack_cb.isChecked()
        self.pack_btn.setEnabled(ok)

    def run_pack(self) -> None:
        self.results.clear()
        self.results.appendPlainText("Packaging to .aifi…")
        self.pack_btn.setEnabled(False)

        self._thread = QtCore.QThread(self)
        self._worker = PackAIFIWorker(
            image_path=str(self.image_path),
            out_path=_abs(self.out_path.text().strip()),
            title=self.work_title.text().strip(),
            creator_name=self.creator_name.text().strip(),
            creator_contact=self.creator_contact.text().strip(),
            mode="human-directed-ai",
            primary_tool=self.primary_tool.text().strip(),
            supporting_tools=[
                n.strip()
                for n in self.supporting_tools.text().split(",")
                if n.strip()
            ][:3],
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._worker.error.connect(self._thread.quit)
        self._worker.error.connect(self._worker.deleteLater)

        self._thread.start()

    def _on_error(self, msg: str) -> None:
        self.results.appendPlainText("")
        self.results.appendPlainText(f"ERROR: {msg}")
        self.status.setText("Failed.")
        self._refresh_enabled()

    def _on_finished(self, payload: object) -> None:
        out_path, v = payload

        self.results.appendPlainText("")
        self.results.appendPlainText(f"[OK] Wrote: {out_path}")

        valid = bool(v.get("valid", False))
        errs = v.get("errors", []) or []
        warns = v.get("warnings", []) or []
        checks = v.get("checks", {}) or {}

        self.results.appendPlainText("")
        self.results.appendPlainText(f"Post-validate: {'PASS' if valid and not errs else 'FAIL'}")
        if checks:
            self.results.appendPlainText("Checks:")
            for k, vv in _iter_checks_grouped(checks):
                self.results.appendPlainText(f"  - {k}: {_format_check_value(k, vv)}")
        if warns:
            self.results.appendPlainText("Warnings:")
            for w in warns:
                self.results.appendPlainText(f"  - {w}")
        if errs:
            self.results.appendPlainText("Errors:")
            for e in errs:
                self.results.appendPlainText(f"  - {e}")

        self.status.setText("Done.")
        self._refresh_enabled()
        self._reset_form()


class PlaceholderPanel(QtWidgets.QWidget):
    def __init__(self, title_text: str, note: str) -> None:
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel(title_text)
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(title)
        msg = QtWidgets.QLabel(note)
        msg.setStyleSheet("opacity: 0.85;")
        msg.setWordWrap(True)
        layout.addWidget(msg)
        layout.addStretch(1)


# -----------------------------
# Main Window
# -----------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        # Background image (window-level, cross-platform safe)
        bg = resource_path("ui/desktop/assets/aifxbackground.png")
        bg_url = bg.replace("\\", "/")
        pm = QtGui.QPixmap(bg)
        if not pm.isNull():
            pal = self.palette()
            pal.setBrush(QtGui.QPalette.Window, QtGui.QBrush(pm))
            self.setAutoFillBackground(True)
            self.setPalette(pal)

        self.setWindowTitle("AIFX Desktop (v0) — Converter + Validator")
        self.resize(980, 640)
        checkmark_url = checkbox_checkmark_path().replace("\\", "/")
        stylesheet = """
        QPushButton {
            min-height: 32px;
            padding: 6px 12px;
            color: rgba(248, 250, 255, 0.96);
            background: rgba(255, 255, 255, 0.11);
            border: 1px solid rgba(255, 255, 255, 0.20);
            border-radius: 9px;
        }
        QPushButton:hover {
            background: rgba(255, 255, 255, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.28);
        }
        QPushButton:pressed {
            background: rgba(255, 255, 255, 0.09);
            border: 1px solid rgba(255, 255, 255, 0.25);
        }
        QPushButton:disabled {
            color: rgba(240, 244, 255, 0.45);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.10);
        }

        QLabel {
            color: rgba(248, 250, 255, 0.96);
            background: transparent;
        }

        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
            min-height: 30px;
            padding: 4px 10px;
            background: rgba(20, 24, 31, 0.44);
            color: rgba(248, 250, 255, 0.96);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 8px;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
            border: 1px solid rgba(170, 208, 255, 0.88);
            background: rgba(22, 26, 34, 0.50);
        }
        QComboBox QAbstractItemView {
            background-color: #000000;
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.20);
            selection-background-color: rgba(80, 120, 200, 0.60);
            selection-color: #ffffff;
        }
        QComboBox QAbstractItemView::item {
            padding: 6px 10px;
            min-height: 24px;
        }
        QCheckBox {
            color: rgba(248, 250, 255, 0.95);
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid rgba(255, 255, 255, 0.72);
            background: rgba(12, 15, 20, 0.92);
        }

        QCheckBox::indicator:unchecked {
            border: 1px solid rgba(255, 255, 255, 0.72);
            background: rgba(12, 15, 20, 0.92);
        }

        QCheckBox::indicator:hover {
            border: 1px solid rgba(255, 255, 255, 0.90);
            background: rgba(20, 24, 31, 0.96);
        }

        QCheckBox::indicator:checked {
            border: 1px solid rgba(170, 208, 255, 0.95);
            background: rgba(42, 58, 82, 0.88);
            image: url(__CHECKMARK_URL__);
        }

        QCheckBox::indicator:disabled {
            border: 1px solid rgba(255, 255, 255, 0.18);
            background: rgba(255, 255, 255, 0.08);
        }
        QMenu {
            background: rgba(24, 26, 34, 0.96);
            color: rgba(248, 250, 255, 0.96);
            border: 1px solid rgba(255,255,255,0.22);
            border-radius: 8px;
            padding: 6px;
        }
        QMenu::item {
            padding: 6px 24px 6px 18px;
            background: transparent;
        }
        QMenu::item:selected {
            background: rgba(255,255,255,0.14);
        }
        """
        self.setStyleSheet(stylesheet.replace("__CHECKMARK_URL__", checkmark_url))

        central = QtWidgets.QWidget()
        central.setObjectName("Central")
        central.setStyleSheet("#Central { background: transparent; }")
        self.setCentralWidget(central)

        # Background layer
        self._bg_label = QtWidgets.QLabel(central)
        self._bg_label.setScaledContents(True)
        self._bg_pixmap = QtGui.QPixmap(resource_path("ui/desktop/assets/aifxbackground.png"))
        self._bg_label.setPixmap(self._bg_pixmap)
        self._bg_label.lower()

        # Ensure background resizes with the window
        central.installEventFilter(self)

        root = QtWidgets.QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Sidebar
        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        sidebar.setStyleSheet("""
        #Sidebar {
            background: rgba(20, 24, 33, 0.34);
            border: 1px solid rgba(255,255,255,0.20);
            border-radius: 14px;
        }
        #Sidebar QLabel {
            background: transparent;
            color: rgba(248, 250, 255, 0.95);
        }
        """)
        sidebar.setMinimumWidth(140)
        sidebar.setMaximumWidth(180)
        self._apply_panel_shadow(sidebar, blur=30, y=8, alpha=120)
        side = QtWidgets.QVBoxLayout(sidebar)
        side.setContentsMargins(12, 12, 12, 12)
        side.setSpacing(10)

        title = QtWidgets.QLabel("AIFX Desktop")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        side.addWidget(title)
        side.addSpacing(8)

        self.btn_home = SidebarButton("Home")
        self.btn_defaults = SidebarButton("Defaults")
        self.btn_validate = SidebarButton("Validate")

        self.lbl_convert = QtWidgets.QLabel("Convert")
        self.lbl_convert.setStyleSheet("font-weight: 700; color: rgba(248, 250, 255, 0.72); padding: 6px 10px;")

        self.btn_music = SidebarButton("Music", indent=14)
        self.btn_video = SidebarButton("Video", indent=14)
        self.btn_image = SidebarButton("Image", indent=14)
        self.btn_project = SidebarButton("Project", indent=14)

        side.addWidget(self.btn_home)
        side.addWidget(self.btn_defaults)
        side.addWidget(self.btn_validate)
        side.addSpacing(6)
        side.addWidget(self.lbl_convert)
        side.addWidget(self.btn_music)
        side.addWidget(self.btn_video)
        side.addWidget(self.btn_image)
        side.addWidget(self.btn_project)
        side.addStretch(1)

        # Pages
        self.pages = QtWidgets.QStackedWidget()
        self.pages.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.pages.setAutoFillBackground(False)
        self.pages.setStyleSheet("background: transparent;")

        defaults = load_defaults()

        self.page_home = HomePanel()
        self.page_defaults = DefaultsPanel()
        self.page_validate = ValidatePanel()
        self.page_music = ConvertMusicPanel()
        self.page_video = PackAIFVPanel(defaults)
        self.page_image = PackAIFIPanel(defaults)

        self.page_project = AIFPPanel(defaults)

        self.pages.addWidget(self.page_home)      # 0
        self.pages.addWidget(self.page_defaults)  # 1
        self.pages.addWidget(self.page_validate)  # 2
        self.pages.addWidget(self.page_music)     # 3
        self.pages.addWidget(self.page_video)     # 4
        self.pages.addWidget(self.page_image)     # 5
        self.pages.addWidget(self.page_project)   # 6

        for page in (
            self.page_home,
            self.page_defaults,
            self.page_validate,
            self.page_music,
            self.page_video,
            self.page_image,
            self.page_project,
        ):
            page.setAutoFillBackground(False)
            page.setAttribute(QtCore.Qt.WA_StyledBackground, True)
            page.setStyleSheet("""
            background: rgba(20, 24, 33, 0.26);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 12px;
            """)
            self._apply_panel_shadow(page, blur=22, y=4, alpha=70)
            lay = page.layout()
            if lay is not None:
                lay.setSpacing(12)
                lay.setContentsMargins(14, 14, 14, 14)

        root.addWidget(sidebar)

        # Scroll area (keeps pages scrollable)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.scroll.viewport().setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setWidget(self.pages)
        self.scroll.setStyleSheet("""
        QScrollArea { background: transparent; border: none; }
        QScrollArea > QWidget > QWidget { background: transparent; }
        """)

        # Content frame (gives us a background panel we can style)
        self.content_frame = QtWidgets.QFrame()
        self.content_frame.setObjectName("contentFrame")
        self.content_frame.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.content_frame.setAutoFillBackground(False)
        self.content_frame.setStyleSheet("""
        QFrame#contentFrame {
            background: rgba(20, 24, 33, 0.36);
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.22);
        }
        """)
        self._apply_panel_shadow(self.content_frame, blur=34, y=10, alpha=130)

        content_layout = QtWidgets.QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.addWidget(self.scroll)

        root.addWidget(self.content_frame, 1)

        # Exclusive nav group
        self.nav_group = QtWidgets.QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for b in (
            self.btn_home,
            self.btn_defaults,
            self.btn_validate,
            self.btn_music,
            self.btn_video,
            self.btn_image,
            self.btn_project,
        ):
            self.nav_group.addButton(b)

        # Routing
        self.btn_home.clicked.connect(lambda: self._go(0, self.btn_home))
        self.btn_defaults.clicked.connect(lambda: self._go(1, self.btn_defaults))
        self.btn_validate.clicked.connect(lambda: self._go(2, self.btn_validate))

        # Convert parent routes to Music by default
        self.btn_music.clicked.connect(lambda: self._go(3, self.btn_music))
        self.btn_video.clicked.connect(lambda: self._go(4, self.btn_video))
        self.btn_image.clicked.connect(lambda: self._go(5, self.btn_image))
        self.btn_project.clicked.connect(lambda: self._go(6, self.btn_project))

        # When defaults saved, refresh convert panels
        self.page_defaults.defaultsSaved.connect(self.page_music.reload_defaults)
        self.page_defaults.defaultsSaved.connect(self.page_video.reload_defaults)
        self.page_defaults.defaultsSaved.connect(self.page_image.reload_defaults)
        self.page_defaults.defaultsSaved.connect(self.page_project.reload_defaults)
        
        # Landing
        self._go(0, self.btn_home)

    def eventFilter(self, obj, event):
        if hasattr(self, "_bg_label") and obj is self.centralWidget() and event.type() == QtCore.QEvent.Resize:
            self._bg_label.setGeometry(0, 0, obj.width(), obj.height())
        return super().eventFilter(obj, event)

    def _apply_panel_shadow(self, widget: QtWidgets.QWidget, *, blur: int, y: int, alpha: int) -> None:
        shadow = QtWidgets.QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, y)
        shadow.setColor(QtGui.QColor(0, 0, 0, alpha))
        widget.setGraphicsEffect(shadow)

    def _set_content_style(self, active: bool) -> None:
        if active:
            self.content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background: rgba(20, 24, 33, 0.38);
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.24);
            }
            """)
        else:
            self.content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background: rgba(20, 24, 33, 0.30);
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.20);
            }
            """)

    def _go(self, index: int, check_btn: QtWidgets.QAbstractButton) -> None:
        self.pages.setCurrentIndex(index)
        self._set_content_style(index != 0)  # Home stays neutral
        check_btn.setChecked(True)

    def _show(self, idx: int) -> None:
        # Switch page
        self.pages.setCurrentIndex(idx)

        # Metallic silver background for active work area
        self.content_frame.setStyleSheet("""
        QFrame#contentFrame {
            background: rgba(20, 24, 33, 0.38);
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.24);
        }
        """)


def main() -> None:
    # Must be set BEFORE QApplication is created
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.AA_DontShowIconsInMenus, True
    )

    app = QtWidgets.QApplication(sys.argv)
    QtCore.QCoreApplication.setOrganizationName(PRODUCTION_ORG_NAME)
    QtCore.QCoreApplication.setApplicationName(PRODUCTION_APP_NAME)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
