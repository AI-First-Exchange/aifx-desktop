# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ui/desktop/app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('ui/desktop/assets', 'ui/desktop/assets')],
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
    name='AIFX Desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='universal2',
    codesign_identity=None,
    entitlements_file=None,
    icon=['ui/desktop/assets/AIFX.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AIFX Desktop',
)
app = BUNDLE(
    coll,
    name='AIFX Desktop.app',
    icon='ui/desktop/assets/AIFX.icns',
    bundle_identifier=None,
)
