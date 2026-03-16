#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

SPEC_FILE="packaging/aifx_desktop_macos.spec"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "Error: missing virtualenv activation script at .venv/bin/activate" >&2
  exit 1
fi

[[ -f "$SPEC_FILE" ]] || { echo "Error: missing spec file at $SPEC_FILE" >&2; exit 1; }

# shellcheck disable=SC1091
source ".venv/bin/activate"

rm -rf build dist

export AIFX_PROJECT_ROOT="$REPO_ROOT"
export AIFX_TARGET_ARCH=universal2

pyinstaller \
  --noconfirm \
  --clean \
  "$SPEC_FILE"

file "dist/AIFX Desktop.app/Contents/MacOS/AIFX Desktop"
lipo -archs "dist/AIFX Desktop.app/Contents/MacOS/AIFX Desktop"

echo "Success: Universal2 app built at dist/AIFX Desktop.app"
