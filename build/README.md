# AIFX Desktop macOS arm64 Build

## Prerequisites

- macOS on Apple Silicon (`arm64`)
- Repo checkout at `/Users/JaiSimon1/Desktop/Projects/AIFX-local/aifx`
- Virtualenv at `.venv` with project dependencies

## Build Commands

```bash
cd /Users/JaiSimon1/Desktop/Projects/AIFX-local/aifx
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pyinstaller
bash build/build_mac_arm64.sh
```

Expected output artifact:

- `dist/AIFX Desktop.app` (unsigned)

## Run The App

```bash
open "dist/AIFX Desktop.app"
```

Optional direct launch for logs:

```bash
./dist/AIFX\ Desktop.app/Contents/MacOS/AIFX\ Desktop > /tmp/aifx-desktop.log 2>&1 &
```

## Validate Smoke Test

1. Open the **Validate** tab in the app.
2. Validate these sample files:
- `tests/out/Boardwalk.aifm`
- `tests/out/007Pilot.aifv`
- `tests/out/007-intro.aifi`
3. Confirm results are shown with PASS/FAIL output.

## Troubleshooting

### Qt platform plugin (cocoa) error

If launch fails with a Qt platform plugin error, verify the platform plugin exists:

```bash
find "dist/AIFX Desktop.app" -name "libqcocoa*.dylib"
```

Rebuild with:

```bash
bash build/build_mac_arm64.sh
```

### Architecture mismatch (Rosetta/x86_64)

Check architecture:

```bash
uname -m
.venv/bin/python -c "import platform; print(platform.machine())"
```

Both must report `arm64`.

### Unsigned app blocked by Gatekeeper/quarantine

If needed for local testing:

```bash
xattr -dr com.apple.quarantine "dist/AIFX Desktop.app"
```

## Optional Packaging (No Notarization Required)

### Zip

```bash
cd dist
ditto -c -k --sequesterRsrc --keepParent "AIFX Desktop.app" "AIFX Desktop-mac-arm64.zip"
```

### DMG (optional)

```bash
hdiutil create -volname "AIFX Desktop" -srcfolder "dist/AIFX Desktop.app" -ov -format UDZO "dist/AIFX Desktop-mac-arm64.dmg"
```

Notarization/signing is not required for this milestone.
