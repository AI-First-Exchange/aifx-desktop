from __future__ import annotations

import argparse
import sys
import json
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from core.validation.validator import validate_aifx_package

AIFX_EXTS = (".aifx", ".aifm", ".aifv", ".aifi", ".aifp")


def _iter_packages(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    pkgs: list[Path] = []
    for p in path.rglob("*"):
        if p.is_file() and p.suffix.lower() in AIFX_EXTS:
            pkgs.append(p)
    return sorted(pkgs)

def _json_summary(input_path: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    passes = sum(1 for r in results if bool(r.get("valid")) and not (r.get("errors") or []))
    fails = len(results) - passes

    return {
        "tool": "aifx",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "totals": {"count": len(results), "pass": passes, "fail": fails},
        "results": results,
    }

def cmd_validate(ns: argparse.Namespace) -> int:
    target = Path(ns.path).expanduser().resolve()
    if not target.exists():
        print(f"ERROR: not found: {target}", file=sys.stderr)
        return 1

    pkgs = _iter_packages(target)
    if not pkgs:
        print(f"ERROR: no AIFX packages found in: {target}", file=sys.stderr)
        return 1

    passes = 0
    fails = 0

    results: list[dict[str, Any]] = []

    for p in pkgs:
        r = validate_aifx_package(p, dry_run=True)
        results.append(r)

        ok = bool(r.get("valid")) and not (r.get("errors") or [])
        if ok:
            passes += 1
            print(f"[PASS] {p}")
        else:
            fails += 1
            print(f"[FAIL] {p}")
            for e in (r.get("errors") or []):
                print(f"  - {e}")

        if ns.show_warnings:
            for w in (r.get("warnings") or []):
                print(f"  ~ {w}")

        if ns.show_checks and (r.get("checks") or {}):
            print("  Checks:")
            checks = r.get("checks") or {}
            for k in sorted(checks.keys()):
                print(f"    - {k}: {checks[k]}")
        print("")

    print(f"Done. PASS={passes} FAIL={fails}")

    if getattr(ns, "json", False):
        payload = _json_summary(target, results)
        blob = json.dumps(payload, indent=2, sort_keys=True)

        jp = getattr(ns, "json_path", None)
        if jp:
            Path(jp).expanduser().resolve().write_text(blob, encoding="utf-8")
        else:
            print(blob)

    return 0 if fails == 0 else 2


def cmd_pack_aifv(ns: argparse.Namespace) -> int:
    from core.packaging.aifv_packager import build_aifv

    out = Path(ns.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    build_aifv(
        video_path=Path(ns.video).expanduser().resolve(),
        thumb_path=Path(ns.thumb).expanduser().resolve(),
        out_path=out,
        title=ns.title,
        creator_name=ns.creator_name,
        creator_contact=ns.creator_contact,
        declaration=ns.declaration,
        mode=ns.mode,
    )
    print(f"OK: wrote {out}")
    return 0

def cmd_pack_aifm(ns: argparse.Namespace) -> int:
    from core.packaging.aifm_packager import build_aifm

    out = Path(ns.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    build_aifm(
        audio_path=Path(ns.audio).expanduser().resolve(),
        out_path=out,
        title=ns.title,
        creator_name=ns.creator_name,
        creator_contact=ns.creator_contact,
        declaration=ns.declaration,
        mode=ns.mode,
        cover_path=Path(ns.cover).expanduser().resolve() if ns.cover else None,
    )
    print(f"OK: wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aifx", description="AIFX Desktop CLI helpers (v0)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="Validate a package or a folder of packages")
    p_val.add_argument("path", help="Path to a .aif* file or a folder")
    p_val.add_argument("--show-checks", action="store_true", help="Print checks map")
    p_val.add_argument("--show-warnings", action="store_true", help="Print warnings")
    # --- E) JSON summary output (CI / automation) ---
    p_val.add_argument("--json", action="store_true", help="Emit machine-readable JSON summary")
    p_val.add_argument("--json-path", default=None, help="Write JSON summary to a file instead of stdout")

    p_val.set_defaults(fn=cmd_validate)

    p_aifv = sub.add_parser("pack-aifv", help="Package a video+thumb into .aifv (no transcoding)")
    p_aifv.add_argument("--video", required=True, help="Path to source video")
    p_aifv.add_argument("--thumb", required=True, help="Path to thumbnail (jpg/png)")
    p_aifv.add_argument("--out", required=True, help="Output .aifv path")
    p_aifv.add_argument("--title", required=True, help="work.title")
    p_aifv.add_argument("--creator-name", required=True, help="creator.name")
    p_aifv.add_argument("--creator-contact", required=True, help="creator.contact (email)")
    p_aifv.add_argument("--declaration", required=True, help="authorship declaration")
    p_aifv.add_argument("--mode", default="human-directed-ai", help="mode (default: human-directed-ai)")
    p_aifv.set_defaults(fn=cmd_pack_aifv)

    p_aifm = sub.add_parser("pack-aifm", help="Package a single audio track into .aifm")
    p_aifm.add_argument("--audio", required=True, help="Path to audio (.wav/.mp3/.flac/.m4a/.ogg)")
    p_aifm.add_argument("--out", required=True, help="Output .aifm path")
    p_aifm.add_argument("--title", required=True, help="work.title")
    p_aifm.add_argument("--creator-name", required=True, help="creator.name")
    p_aifm.add_argument("--creator-contact", required=True, help="creator.contact (email)")
    p_aifm.add_argument("--declaration", required=True, help="authorship declaration")
    p_aifm.add_argument("--mode", default="human-directed-ai", help="mode (default: human-directed-ai)")
    p_aifm.add_argument("--cover", default=None, help="optional cover image path")
    p_aifm.set_defaults(fn=cmd_pack_aifm)

    ns = parser.parse_args(argv)
    return int(ns.fn(ns))

if __name__ == "__main__":
    raise SystemExit(main())
