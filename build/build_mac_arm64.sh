#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "ERROR: This build script must run on Apple Silicon (arm64)." >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python not found at $PYTHON_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"

"$PYTHON_BIN" -m pip install --upgrade pip
if ! "$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1; then
  "$PYTHON_BIN" -m pip install pyinstaller
fi

rm -rf "$ROOT_DIR/build/pyinstaller" "$ROOT_DIR/dist/AIFX Desktop.app"

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --workpath "$ROOT_DIR/build/pyinstaller" \
  --distpath "$ROOT_DIR/dist" \
  "$ROOT_DIR/build/AIFXDesktop.spec"

if [[ ! -d "$ROOT_DIR/dist/AIFX Desktop.app" ]]; then
  echo "ERROR: Build failed; expected artifact missing: dist/AIFX Desktop.app" >&2
  exit 1
fi

echo "Build complete: $ROOT_DIR/dist/AIFX Desktop.app"
echo "Run: open \"$ROOT_DIR/dist/AIFX Desktop.app\""
