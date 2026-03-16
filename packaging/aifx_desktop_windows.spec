# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).resolve().parent
icon_path = project_root / "ui" / "desktop" / "assets" / "AIFX.ico"

a = Analysis(
    [str(project_root / "ui" / "desktop" / "app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / "ui" / "desktop" / "assets"), "ui/desktop/assets")],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name="AIFX Desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(icon_path),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AIFX Desktop",
)
