#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

APP_NAME="AIFX Desktop.app"
VOL_NAME="AIFX Desktop Installer"
APP_PATH="dist/$APP_NAME"
FINAL_DMG="dist/AIFX Desktop.dmg"
DMG_SRC_DIR="build/dmg_src"

BG_SRC="ui/desktop/assets/AIFX_dmg.png"
if [[ ! -f "$BG_SRC" ]]; then
  BG_SRC="ui/desktop/assets/aifxbackground.png"
fi
VOL_ICON_SRC="ui/desktop/assets/aifx_dmg.icns"

[[ -d "$APP_PATH" ]] || { echo "Missing app bundle: $APP_PATH" >&2; exit 1; }
[[ -f "$BG_SRC" ]] || { echo "Missing DMG background image in ui/desktop/assets" >&2; exit 1; }
[[ -f "$VOL_ICON_SRC" ]] || { echo "Missing DMG volume icon: $VOL_ICON_SRC" >&2; exit 1; }
command -v create-dmg >/dev/null || { echo "Missing required tool: create-dmg" >&2; exit 1; }

rm -f "$FINAL_DMG"
rm -rf "$DMG_SRC_DIR"
mkdir -p "$DMG_SRC_DIR"
cp -R "$APP_PATH" "$DMG_SRC_DIR/$APP_NAME"

create-dmg \
  --volname "$VOL_NAME" \
  --volicon "$VOL_ICON_SRC" \
  --background "$BG_SRC" \
  --window-pos 140 120 \
  --window-size 760 460 \
  --icon-size 128 \
  --text-size 14 \
  --icon "$APP_NAME" 180 230 \
  --hide-extension "$APP_NAME" \
  --app-drop-link 520 230 \
  --format UDZO \
  "$FINAL_DMG" \
  "$DMG_SRC_DIR"

echo "Created: $FINAL_DMG"
