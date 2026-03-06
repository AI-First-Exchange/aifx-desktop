#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

APP_NAME="AIFX Desktop"
APP_BUNDLE="$APP_NAME.app"
SPEC_FILE="packaging/aifx_desktop.spec"
ICON_FILE="ui/desktop/assets/AIFX.icns"

APP_ARM_DIR="dist_arm64/$APP_BUNDLE"
APP_X86_DIR="dist_x86_64/$APP_BUNDLE"
APP_UNI_DIR="dist/$APP_BUNDLE"

clean_artifacts() {
  rm -rf \
    build \
    dist \
    dist_arm64 \
    dist_x86_64 \
    "dist/$APP_NAME-rw.dmg" \
    "dist/$APP_NAME.dmg"
}

run_pyinstaller_arm64() {
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export AIFX_PROJECT_ROOT="$REPO_ROOT"
  export AIFX_TARGET_ARCH=arm64
  pyinstaller --noconfirm --clean \
    --distpath dist_arm64 \
    --workpath build/arm64 \
    "$SPEC_FILE"
  deactivate
}

run_pyinstaller_x86_64() {
  local x86_cmd
  read -r -d '' x86_cmd <<CMD || true
set -euo pipefail
source .venv-x86/bin/activate
export AIFX_PROJECT_ROOT="$REPO_ROOT"
export AIFX_TARGET_ARCH=x86_64
pyinstaller --noconfirm --clean \
  --distpath dist_x86_64 \
  --workpath build/x86_64 \
  packaging/aifx_desktop.spec
CMD

  if [[ "$(uname -m)" == "arm64" ]]; then
    arch -x86_64 /bin/zsh -lc "$x86_cmd"
  else
    /bin/zsh -lc "$x86_cmd"
  fi
}

is_macho() {
  local f="$1"
  file -b "$f" | grep -q "Mach-O"
}

merge_universal_app() {
  [[ -d "$APP_ARM_DIR" ]] || { echo "Missing arm64 app at $APP_ARM_DIR" >&2; exit 1; }
  [[ -d "$APP_X86_DIR" ]] || { echo "Missing x86_64 app at $APP_X86_DIR" >&2; exit 1; }

  mkdir -p dist
  rm -rf "$APP_UNI_DIR"
  cp -R "$APP_ARM_DIR" "$APP_UNI_DIR"

  while IFS= read -r -d '' arm_file; do
    local rel x86_file out_file
    rel="${arm_file#"$APP_ARM_DIR"/}"
    x86_file="$APP_X86_DIR/$rel"
    out_file="$APP_UNI_DIR/$rel"

    if [[ -f "$x86_file" ]] && is_macho "$arm_file" && is_macho "$x86_file"; then
      lipo -create "$arm_file" "$x86_file" -output "$out_file"
    fi
  done < <(find "$APP_ARM_DIR" -type f -print0)
}

verify_universal() {
  local bin_path
  bin_path="$APP_UNI_DIR/Contents/MacOS/$APP_NAME"
  [[ -f "$bin_path" ]] || { echo "Missing app executable: $bin_path" >&2; exit 1; }
  echo "App binary info:"
  file "$bin_path"
  echo "Architectures: $(lipo -archs "$bin_path")"

  local plist
  plist="$APP_UNI_DIR/Contents/Info.plist"
  [[ -f "$plist" ]] || { echo "Missing Info.plist" >&2; exit 1; }
  /usr/libexec/PlistBuddy -c 'Print :CFBundleIconFile' "$plist" || true

  [[ -f "$ICON_FILE" ]] || { echo "Missing icon file: $ICON_FILE" >&2; exit 1; }
}

main() {
  [[ -f "$SPEC_FILE" ]] || { echo "Missing spec file: $SPEC_FILE" >&2; exit 1; }
  [[ -f "$ICON_FILE" ]] || { echo "Missing app icon: $ICON_FILE" >&2; exit 1; }
  [[ -f .venv/bin/activate ]] || { echo "Missing arm64 venv: .venv" >&2; exit 1; }
  [[ -f .venv-x86/bin/activate ]] || { echo "Missing x86_64 venv: .venv-x86" >&2; exit 1; }

  clean_artifacts
  run_pyinstaller_arm64
  run_pyinstaller_x86_64
  merge_universal_app
  verify_universal
  "$SCRIPT_DIR/create_dmg.sh"
}

main "$@"
