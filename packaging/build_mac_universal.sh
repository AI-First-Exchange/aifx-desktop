#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "Error: missing virtualenv activation script at .venv/bin/activate" >&2
  exit 1
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"

rm -rf build dist *.spec

pyinstaller \
  --windowed \
  --name "AIFX Desktop" \
  --target-architecture universal2 \
  --icon "ui/desktop/assets/AIFX.icns" \
  --add-data "ui/desktop/assets:ui/desktop/assets" \
  -p . \
  ui/desktop/app.py

file "dist/AIFX Desktop.app/Contents/MacOS/AIFX Desktop"
lipo -archs "dist/AIFX Desktop.app/Contents/MacOS/AIFX Desktop"

echo "Success: Universal2 app built at dist/AIFX Desktop.app"
