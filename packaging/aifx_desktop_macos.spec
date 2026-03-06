# -*- mode: python ; coding: utf-8 -*-

import os

TARGET_ARCH = os.environ.get("AIFX_TARGET_ARCH")
PROJECT_ROOT = os.environ.get("AIFX_PROJECT_ROOT", os.getcwd())

if TARGET_ARCH not in (None, "arm64", "x86_64", "universal2"):
    raise SystemExit(f"Unsupported AIFX_TARGET_ARCH: {TARGET_ARCH}")

ICON_PATH = os.path.join(PROJECT_ROOT, "ui/desktop/assets/AIFX.icns")
ASSETS_PATH = os.path.join(PROJECT_ROOT, "ui/desktop/assets")
ENTRY_SCRIPT = os.path.join(PROJECT_ROOT, "ui/desktop/app.py")

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
    argv_emulation=False,
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICON_PATH],
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

app = BUNDLE(
    collect,
    name="AIFX Desktop.app",
    icon=ICON_PATH,
    bundle_identifier="com.aifx.desktop",
)
