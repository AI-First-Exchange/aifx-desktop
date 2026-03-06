# -*- mode: python ; coding: utf-8 -*-

import os

PROJECT_ROOT = os.environ.get("AIFX_PROJECT_ROOT", os.getcwd())

ICON_PATH = os.path.join(PROJECT_ROOT, "ui", "desktop", "assets", "AIFX.ico")
ASSETS_PATH = os.path.join(PROJECT_ROOT, "ui", "desktop", "assets")
ENTRY_SCRIPT = os.path.join(PROJECT_ROOT, "ui", "desktop", "app.py")

analysis = Analysis(
    [ENTRY_SCRIPT],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[(ASSETS_PATH, "ui/desktop/assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="AIFX Desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=ICON_PATH,
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AIFX Desktop",
)
