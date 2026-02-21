from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../aifx
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6 import QtCore, QtWidgets, QtGui

from core.packaging.aifv_packager import build_aifv
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

ORG_NAME = "AI-First-Exchange"
APP_NAME = "AIFX Desktop"


def _abs(p: str) -> str:
    return os.path.abspath(os.path.expanduser(p))


def collect_packages(selected_files: list[str], selected_folder: str | None = None) -> list[str]:
    files: list[str] = []

    for p in selected_files or []:
        if p.lower().endswith(AIFX_PACKAGE_EXTS) and os.path.isfile(p):
            files.append(_abs(p))

    if selected_folder:
        for root, _, names in os.walk(selected_folder):
            for name in names:
                if name.lower().endswith(AIFX_PACKAGE_EXTS):
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
    default_mode: str = "human-directed-ai"
    default_output_dir: str = str(Path.home() / "Desktop")

def _qsettings() -> QtCore.QSettings:
    return QtCore.QSettings(ORG_NAME, APP_NAME)

def load_defaults() -> AppDefaults:
    qs = _qsettings()
    return AppDefaults(
        creator_name=str(qs.value("defaults/creator_name", "")),
        creator_email=str(qs.value("defaults/creator_email", "")),
        default_mode=str(qs.value("defaults/default_mode", "human-directed-ai")),
        default_output_dir=str(qs.value("defaults/default_output_dir", str(Path.home() / "Desktop"))),
    )

def save_defaults(d: AppDefaults) -> None:
    qs = _qsettings()
    qs.setValue("defaults/creator_name", d.creator_name.strip())
    qs.setValue("defaults/creator_email", d.creator_email.strip())
    qs.setValue("defaults/default_mode", d.default_mode.strip())
    qs.setValue("defaults/default_output_dir", d.default_output_dir.strip())

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
                padding: 10px 12px;
                padding-left: {pad_left}px;
                border: 1px solid transparent;
                border-radius: 10px;
                background: transparent;
                color: rgba(255, 255, 255, 0.88);
            }}

            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.10);
            }}

            QPushButton:checked {{
                font-weight: 800;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.22);

                /* "metallic" highlight */
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.22),
                    stop:0.45 rgba(255,255,255,0.12),
                    stop:1 rgba(0,0,0,0.18)
                );
            }}

            QPushButton:checked:hover {{
                border: 1px solid rgba(255, 255, 255, 0.30);
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.26),
                    stop:0.45 rgba(255,255,255,0.14),
                    stop:1 rgba(0,0,0,0.20)
                );
            }}
        """)

class DropZone(QtWidgets.QFrame):
    pathDropped = QtCore.Signal(str)

    def __init__(self, label_text: str = "Drop files here") -> None:
        super().__init__()
        bg = "/Users/JaiSimon1/Desktop/aifxbackground.png"
        self.setStyleSheet(f"QMainWindow {{ background-image: url('{bg}'); background-position: center; background-repeat: repeat; }}")

        self.setAcceptDrops(True)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)
        self.setMinimumHeight(120)

        self.label = QtWidgets.QLabel(label_text)
        self.label.setAlignment(QtCore.Qt.AlignCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)

    def set_text(self, s: str) -> None:
        self.label.setText(s)

    def dragEnterEvent(self, event: QtCore.QEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtCore.QEvent) -> None:
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
        declaration: str,
        mode: str,
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.thumb_path = thumb_path
        self.out_path = out_path
        self.title = title
        self.creator_name = creator_name
        self.creator_contact = creator_contact
        self.declaration = declaration
        self.mode = mode

    @QtCore.Slot()
    def run(self) -> None:
        try:
            out = build_aifv(
                video_path=Path(self.video_path),
                thumb_path=Path(self.thumb_path),
                out_path=Path(self.out_path),
                title=self.title,
                creator_name=self.creator_name,
                creator_contact=self.creator_contact,
                declaration=self.declaration,
                mode=self.mode,
            )
            # Auto-validate
            v = validate_package_local(str(out), dry_run=True)
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

        title = QtWidgets.QLabel("AIFX Desktop (v0)")
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        subtitle = QtWidgets.QLabel("Converter + Validator shell — SDA by design.")
        subtitle.setStyleSheet("opacity: 0.8;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        msg = QtWidgets.QLabel(
            "Use Defaults once, then Convert in batches.\n"
            "Validate supports files or folders (recursive).\n"
            "No identity verification claims — structure + integrity only."
        )
        msg.setStyleSheet("opacity: 0.9;")
        layout.addWidget(msg)
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
        self.mode_combo.addItems(["human-directed-ai", "ai-assisted", "ai-generated"])

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
        form.addRow("Default Output Dir:", out_row)
        layout.addLayout(form)

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

    def _browse_outdir(self) -> None:
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose default output folder", self.output_dir.text() or str(Path.home()))
        if d:
            self.output_dir.setText(d)

    def _save(self) -> None:
        d = AppDefaults(
            creator_name=self.creator_name.text().strip(),
            creator_email=self.creator_email.text().strip(),
            default_mode=self.mode_combo.currentText().strip(),
            default_output_dir=self.output_dir.text().strip() or str(Path.home() / "Desktop"),
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

        self.drop = DropZone("Drop .aifm/.aifv/.aifi/.aifp (or .aifx) here\n(or use Browse)")
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

        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.results, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("opacity: 0.8;")
        layout.addWidget(self.status)

    def _on_drop(self, p: str) -> None:
        pp = Path(p)
        self.selected_files = []
        self.selected_folder = None

        if pp.is_dir():
            self.selected_folder = str(pp)
            self.status.setText(f"Folder selected: {pp}")
        else:
            self.selected_files = [str(pp)]
            self.status.setText(f"File selected: {pp}")

        self.validate_btn.setEnabled(True)

    def _browse_files(self) -> None:
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select AIFX package(s)",
            "",
            "AIFX Packages (*.aifx *.aifm *.aifv *.aifi *.aifp)",
        )
        if files:
            self.selected_files = files
            self.selected_folder = None
            self.status.setText(f"{len(files)} file(s) selected.")
            self.validate_btn.setEnabled(True)

    def _browse_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder to scan (recursive)", "")
        if folder:
            self.selected_folder = folder
            self.selected_files = []
            self.status.setText(f"Folder selected: {folder}")
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

        # ---- Defaults (loaded) ----
        self.creator_name = QtWidgets.QLineEdit()
        self.creator_email = QtWidgets.QLineEdit()
        self.creator_name.setReadOnly(True)
        self.creator_email.setReadOnly(True)

        # ---- Required per-track fields (NO DEFAULTS) ----
        self.origin_platform = QtWidgets.QLineEdit()
        self.origin_url = QtWidgets.QLineEdit()
        self.ai_system = QtWidgets.QLineEdit()

        self.origin_platform.setPlaceholderText("e.g., Suno, Udio, ElevenLabs, Custom")
        self.origin_url.setPlaceholderText("https://… (required)")
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

        # Make important fields readable (about ~60 chars)
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
        cover_row.addWidget(self.cover_path, 1)
        cover_row.addWidget(self.cover_browse)

        self.prompt_text = QtWidgets.QPlainTextEdit()
        self.prompt_text.setPlaceholderText("Optional prompt…")

        self.lyrics_text = QtWidgets.QPlainTextEdit()
        self.lyrics_text.setPlaceholderText("Optional lyrics…")

        # Output dir (from defaults)
        out_row = QtWidgets.QHBoxLayout()
        self.output_dir = QtWidgets.QLineEdit()
        self.output_browse = QtWidgets.QPushButton("Browse…")
        self.output_browse.clicked.connect(self._browse_outdir)
        out_row.addWidget(self.output_dir, 1)
        out_row.addWidget(self.output_browse)

        # Confirmation checkbox (NO editing of declaration text)
        self.confirm_cb = QtWidgets.QCheckBox(
            "I confirm this work was created using human-directed AI and I assert authorship/responsibility for this package."
        )

        # Form layout
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        form.addRow("Creator Name (Defaults):", self.creator_name)
        form.addRow("Creator Email (Defaults):", self.creator_email)
        
        title_row = QtWidgets.QHBoxLayout()
        title_row.addWidget(self.music_title, 1)
        title_row.addWidget(self.selected_file_label)

        form.addRow("Title (required):", title_row)

        form.addRow("Origin Platform (required):", self.origin_platform)
        form.addRow("Origin URL (required):", self.origin_url)
        form.addRow("AI System (required):", self.ai_system)
        form.addRow("Persona (optional):", self.persona)
        form.addRow("Cover image (optional):", cover_row)
        form.addRow("Output folder:", out_row)
        layout.addLayout(form)

        layout.addWidget(QtWidgets.QLabel("Prompt (optional):"))
        layout.addWidget(self.prompt_text, 1)
        layout.addWidget(QtWidgets.QLabel("Lyrics (optional):"))
        layout.addWidget(self.lyrics_text, 1)
        layout.addWidget(self.confirm_cb)

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
        self.confirm_cb.stateChanged.connect(self._refresh_convert_enabled)

        self._refresh_convert_enabled()

    def _mark_ai_system_touched(self) -> None:
        self._ai_system_user_touched = True

    def _maybe_mirror_ai_system(self, text: str) -> None:
        if not self._ai_system_user_touched:
            self.ai_system.setText(text)

    def reload_defaults(self) -> None:
        d = load_defaults()
        self.creator_name.setText(d.creator_name)
        self.creator_email.setText(d.creator_email)
        self.mode.setText(d.default_mode)
    
    def _on_drop(self, p: str) -> None:
        pp = Path(p)
        if pp.is_dir():
            QtWidgets.QMessageBox.information(self, "Single track only", "Music conversion is single-track only. Drop an audio file, not a folder.")
            return

        if not pp.suffix.lower() in AUDIO_EXTS:
            QtWidgets.QMessageBox.information(self, "Unsupported file", "Please drop a supported audio file (.wav/.mp3/.flac/.m4a/.ogg).")
            return

        self.selected_file = str(pp)
        self.status.setText(f"Selected: {pp.name}")
        self.selected_file_label.setText(f"({pp.name})")

        self._refresh_convert_enabled()

    def _browse_file(self) -> None:
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select one audio file",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.m4a *.ogg)",
        )
        if file:
            self.selected_file = file
            self.status.setText(f"Selected: {Path(file).name}")
            self.selected_file_label.setText(f"({Path(file).name})")
            self._refresh_convert_enabled()

    def _browse_cover(self) -> None:
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select cover image (optional)",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if file:
            self.cover_path.setText(file)

    def _browse_outdir(self) -> None:
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_dir.text() or str(Path.home()))
        if d:
            self.output_dir.setText(d)

    def _refresh_convert_enabled(self) -> None:
        d = load_defaults()
        has_defaults = bool(d.creator_name.strip()) and bool(d.creator_email.strip())
        has_file = bool(self.selected_file)
        req_ok = (
            bool(self.origin_platform.text().strip())
            and bool(self.origin_url.text().strip())
            and bool(self.ai_system.text().strip())
        )
        confirmed = self.confirm_cb.isChecked()

        self.convert_btn.setEnabled(bool(has_defaults and has_file and req_ok and confirmed))

    def run_convert(self) -> None:
        d = load_defaults()
        if not d.creator_name.strip() or not d.creator_email.strip():
            QtWidgets.QMessageBox.information(self, "Defaults required", "Set Creator Name and Email in Defaults first.")
            return
        if not self.selected_file:
            QtWidgets.QMessageBox.information(self, "No input", "Select one audio file first.")
            return
        if not self.convert_btn.isEnabled():
            QtWidgets.QMessageBox.information(self, "Missing required fields", "Fill required fields and check confirmation.")
            return

        srcp = Path(self.selected_file)
        title = srcp.stem
        outdir = Path(_abs(self.output_dir.text().strip() or d.default_output_dir))
        outdir.mkdir(parents=True, exist_ok=True)
        out_path = outdir / f"{title}.aifm"

        # Build AIFM inputs
        from core.conversion.aifm_converter import AIFMInputs

        cover = self.cover_path.text().strip()
        cover_path = Path(cover).expanduser() if cover else None

        inp = AIFMInputs(
            audio_path=srcp,
            title=title,
            creator_name=d.creator_name.strip(),
            creator_contact=d.creator_email.strip(),
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

        # Show validation summary (auto)
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

class PackAIFVPanel(QtWidgets.QWidget):
    def __init__(self, defaults: AppDefaults) -> None:
        super().__init__()
        self._defaults = defaults
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[PackAIFVWorker] = None

        self.video_path: Optional[str] = None
        self.thumb_path: Optional[str] = None

        layout = QtWidgets.QVBoxLayout(self)

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

        # --- Form
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        # Make the right column expand (important)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.work_title = QtWidgets.QLineEdit()
        self.creator_name = QtWidgets.QLineEdit(defaults.creator_name)
        self.creator_contact = QtWidgets.QLineEdit(defaults.creator_email)
        self.mode = QtWidgets.QLineEdit(defaults.default_mode)

        self.declaration = QtWidgets.QPlainTextEdit()
        self.declaration.setPlaceholderText("Human-authored declaration (required).")
        self.declaration.setMinimumHeight(160)  # make it feel intentional

        # Make inputs expand like the big declaration area
        for w in (self.work_title, self.creator_name, self.creator_contact, self.mode):
            w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            w.setMinimumWidth(520)  # tweak 500–650 to taste

        self.out_path = QtWidgets.QLineEdit()
        self.out_path.setPlaceholderText("Output .aifv path (e.g., ~/Desktop/MyVideo.aifv)")
        self.out_path.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        form.addRow("Title", self.work_title)
        form.addRow("Creator Name", self.creator_name)
        form.addRow("Creator Contact", self.creator_contact)
        form.addRow("Mode", self.mode)
        form.addRow("Declaration", self.declaration)

        # Output row with browse button
        self.out_btn = QtWidgets.QPushButton("Browse…")
        self.out_btn.setMinimumWidth(120)
        self.out_btn.clicked.connect(self._browse_out)

        out_row = QtWidgets.QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.addWidget(self.out_path, 1)
        out_row.addWidget(self.out_btn)

        form.addRow("Output .aifv", out_row)

        # --- Buttons
        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)

        self.pack_btn = QtWidgets.QPushButton("Package AIFV")
        self.pack_btn.setEnabled(False)
        btn_row.addStretch(1)
        btn_row.addWidget(self.pack_btn)

        self.pack_btn.clicked.connect(self.run_pack)

        # --- Results
        self.results = QtWidgets.QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setMinimumHeight(220)
        layout.addWidget(self.results)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("opacity: 0.85;")
        layout.addWidget(self.status)

        self._refresh_enabled()

        # Live refresh
        self.work_title.textChanged.connect(self._refresh_enabled)
        self.creator_name.textChanged.connect(self._refresh_enabled)
        self.creator_contact.textChanged.connect(self._refresh_enabled)
        self.out_path.textChanged.connect(self._refresh_enabled)
        self.declaration.textChanged.connect(self._refresh_enabled)

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

        # Only do this if your panel actually has a mode widget
        if hasattr(self, "mode"):
            try:
                self.mode.setText(d.default_mode)
            except Exception:
                pass

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
        ok = ok and bool(self.declaration.toPlainText().strip())
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
            declaration=self.declaration.toPlainText().strip(),
            mode=self.mode.text().strip() or "human-directed-ai",
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
        bg = "/Users/JaiSimon1/Desktop/aifxbackground.png"
        pm = QtGui.QPixmap(bg)
        pal = self.palette()
        pal.setBrush(QtGui.QPalette.Window, QtGui.QBrush(pm))
        self.setAutoFillBackground(True)
        self.setPalette(pal)

        self.setWindowTitle("AIFX Desktop (v0) — Converter + Validator")
        self.resize(980, 640)
        self.setStyleSheet("""
        /* Buttons (Browse, Save, Validate, etc.) */
        QPushButton {
            background: #3b3b3b;
            color: #f0f0f0;
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 10px;
            padding: 8px 12px;
        }
        QPushButton:hover {
            background: #454545;
            border: 1px solid rgba(255,255,255,0.35);
        }
        QPushButton:pressed {
            background: #2f2f2f;
            border: 1px solid rgba(255,255,255,0.30);
        }
        QPushButton:disabled {
            background: #262626;
            color: rgba(255,255,255,0.40);
            border: 1px solid rgba(255,255,255,0.12);
        }

        /* Inputs */
        QLineEdit, QTextEdit, QPlainTextEdit {
            background: #262626;
            color: #f2f2f2;
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 8px;
            padding: 6px 8px;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid rgba(255,255,255,0.32);
        }

        /* Right-click menu */
        QMenu {
            background: #2b2b2b;
            color: #f2f2f2;
            border: 1px solid rgba(255,255,255,0.25);
            padding: 6px;
        }
        QMenu::item {
            padding: 6px 24px 6px 18px;
            background: transparent;
        }
        QMenu::item:selected {
            background: rgba(255,255,255,0.14);
        }
        """)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root = QtWidgets.QHBoxLayout(central)

        # Sidebar
        sidebar = QtWidgets.QFrame()
        sidebar.setMinimumWidth(140)
        sidebar.setMaximumWidth(180)
        side = QtWidgets.QVBoxLayout(sidebar)
        side.setContentsMargins(10, 10, 10, 10)
        side.setSpacing(6)

        title = QtWidgets.QLabel("AIFX Desktop")
        title.setStyleSheet("font-size: 16px; font-weight: 800;")
        side.addWidget(title)
        side.addSpacing(8)

        self.btn_home = SidebarButton("Home")
        self.btn_defaults = SidebarButton("Defaults")
        self.btn_validate = SidebarButton("Validate")

        self.lbl_convert = QtWidgets.QLabel("Convert")
        self.lbl_convert.setStyleSheet("font-weight: 800; color: #888; padding: 6px 12px;")

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

        defaults = load_defaults()

        self.page_home = HomePanel()
        self.page_defaults = DefaultsPanel()
        self.page_validate = ValidatePanel()
        self.page_music = ConvertMusicPanel()
        self.page_video = PackAIFVPanel(defaults)

        # Until you build PackAIFI UI, keep this as placeholder
        self.page_image = PlaceholderPanel(
            "Convert → Image",
            "Use CLI for now: python -m aifx pack-aifi ...",
        )

        self.page_project = PlaceholderPanel(
            "Convert → Project",
            "Not implemented yet. AIFP packaging rules need design (entry point, include/exclude).",
        )

        self.pages.addWidget(self.page_home)      # 0
        self.pages.addWidget(self.page_defaults)  # 1
        self.pages.addWidget(self.page_validate)  # 2
        self.pages.addWidget(self.page_music)     # 3
        self.pages.addWidget(self.page_video)     # 4
        self.pages.addWidget(self.page_image)     # 5
        self.pages.addWidget(self.page_project)   # 6

        root.addWidget(sidebar)

        # Scroll area (keeps pages scrollable)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setWidget(self.pages)
        self.scroll.setStyleSheet("background: transparent;")
        self.pages.setStyleSheet("background: transparent;")

        # Content frame (gives us a background panel we can style)
        self.content_frame = QtWidgets.QFrame()
        self.content_frame.setObjectName("contentFrame")
        self.content_frame.setStyleSheet("""
        QFrame#contentFrame {
            background-color: rgba(45, 45, 45, 220);
            border-radius: 12px;
        }
        """)

        content_layout = QtWidgets.QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.scroll)

        root.addWidget(self.content_frame, 1)

        self.content_frame.setStyleSheet("""
        QFrame#contentFrame {
            background: #3a3a3a;
            border-radius: 10px;
        }
        """)

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
        
        # Landing
        self._go(0, self.btn_home)

    def _set_content_style(self, active: bool) -> None:
        if active:
            self.content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b3b3b,
                    stop:1 #2e2e2e
                );
                border-radius: 10px;
            }

            /* Light satin inputs on dark metal */
            QLineEdit, QTextEdit, QPlainTextEdit {
                   background: #555;
                   color: #ffffff;
                   border: 1px solid #6a6a6a;
                   border-radius: 6px;
                   padding: 6px 8px;
            }

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                background: #606060;
                border: 1px solid #9a9a9a;
            }

            QLineEdit::placeholder, QTextEdit::placeholder, QPlainTextEdit::placeholder {
                color: rgba(255, 255, 255, 0.55);
            }
            """)
        else:
            self.content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background: #2b2b2b;
                border-radius: 10px;
            }  

            QLineEdit, QTextEdit, QPlainTextEdit {
                background: #444;
                color: #eee;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 6px 8px;
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
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 #3c3c3c,
                stop:0.5 #343434,
                stop:1 #2a2a2a
            );
            border-radius: 10px;
        }
        """)


def main() -> None:
    # Must be set BEFORE QApplication is created
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.AA_DontShowIconsInMenus, True
    )

    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
