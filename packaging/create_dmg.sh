#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

APP_PATH="dist/AIFX Desktop.app"
RW_DMG="dist/AIFX Desktop-rw.dmg"
FINAL_DMG="dist/AIFX Desktop.dmg"

[[ -d "$APP_PATH" ]] || { echo "Missing app: $APP_PATH"; exit 1; }

# background source (prefer DMG-specific)
if [[ -f "ui/desktop/assets/AIFX_dmg.png" ]]; then
  DMG_BG_SRC="ui/desktop/assets/AIFX_dmg.png"
elif [[ -f "ui/desktop/assets/aifxbackground.png" ]]; then
  DMG_BG_SRC="ui/desktop/assets/aifxbackground.png"
else
  echo "Missing background image (AIFX_dmg.png preferred)."
  exit 1
fi

VOLUME_ICON_SRC="ui/desktop/assets/aifx_dmg.icns"
[[ -f "$VOLUME_ICON_SRC" ]] || { echo "Missing volume icon: $VOLUME_ICON_SRC"; exit 1; }

rm -f "$RW_DMG" "$FINAL_DMG"

# detach stale mounts
for v in "/Volumes/AIFX Desktop" "/Volumes/AIFX Desktop 1" "/Volumes/AIFX Desktop 2"; do
  hdiutil detach "$v" 2>/dev/null || true
done

echo "Creating RW DMG..."
hdiutil create -volname "AIFX Desktop" -srcfolder "$APP_PATH" -ov -format UDRW "$RW_DMG" >/dev/null

echo "Attaching..."
ATTACH_OUT="$(hdiutil attach "$RW_DMG" -nobrowse)"
MOUNT="$(echo "$ATTACH_OUT" | sed -n 's|.*\(/Volumes/.*\)$|\1|p' | head -n 1)"
[[ -n "$MOUNT" ]] || { echo "Could not determine mountpoint."; echo "$ATTACH_OUT"; exit 1; }
echo "Mounted at: $MOUNT"

# add Applications link
ln -sf /Applications "$MOUNT/Applications"

# add background + volume icon (no SetFile / no osascript)
mkdir -p "$MOUNT/.background"
cp "$DMG_BG_SRC" "$MOUNT/.background/background.png"
cp "$VOLUME_ICON_SRC" "$MOUNT/.VolumeIcon.icns"

sync || true

echo "Detaching..."
for _ in 1 2 3 4 5; do
  if hdiutil detach "$MOUNT" >/dev/null 2>&1; then
    break
  fi
  sleep 0.7
done

echo "Converting to compressed DMG..."
hdiutil convert "$RW_DMG" -format UDZO -ov -o "$FINAL_DMG" >/dev/null

echo "✅ DMG created: $FINAL_DMG"