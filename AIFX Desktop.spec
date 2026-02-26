# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import PySide6
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

project_root = Path(SPECPATH).resolve().parent

pyside_datas, pyside_binaries, pyside_hiddenimports = collect_all("PySide6")
pyside_binaries += collect_dynamic_libs("PySide6")
pyside_datas += collect_data_files("PySide6", include_py_files=False)

qt_platform_dir = Path(PySide6.__file__).resolve().parent / "Qt" / "plugins" / "platforms"
for plugin in qt_platform_dir.glob("libqcocoa*.dylib"):
    pyside_binaries.append((str(plugin), "PySide6/Qt/plugins/platforms"))

app_datas = [
    (str(project_root / "ui/desktop/assets/aifxbackground.png"), "ui/desktop/assets"),
]

hiddenimports = sorted(
    set(
        pyside_hiddenimports
        + [
            "core.conversion.aifm_converter",
            "core.packaging.aifv_packager",
            "core.validation.validator",
            "core.validation.aifv_validator",
            "ui.desktop.validator_bridge",
        ]
    )
)

a = Analysis(
    [str(project_root / "ui/desktop/app.py")],
    pathex=[str(project_root)],
    binaries=pyside_binaries,
    datas=pyside_datas + app_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AIFX Desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    target_arch="arm64",
    disable_windowed_traceback=False,
    argv_emulation=False,
)

app = BUNDLE(
    exe,
    name="AIFX Desktop.app",
    icon=None,
    bundle_identifier="com.aifx.desktop",
)
