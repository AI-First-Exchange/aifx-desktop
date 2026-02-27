from __future__ import annotations

# --- stdlib ---
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- project ---
from core.packaging.aifi_packager import build_aifi
from core.packaging.aifm_packager import build_aifm
from core.packaging.aifv_packager import build_aifv
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
    quiet = bool(getattr(ns, "quiet", False))

    # If emitting JSON to stdout, suppress human output so redirects stay valid JSON
    if getattr(ns, "json", False) and not getattr(ns, "json_path", None):
        quiet = True

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
            if not quiet:
                print(f"[PASS] {p}")
        else:
            fails += 1
            if not quiet:
                print(f"[FAIL] {p}")
                for e in (r.get("errors") or []):
                    print(f"  - {e}")

        if ns.show_warnings and not quiet:
            for w in (r.get("warnings") or []):
                print(f"  ~ {w}")

        if ns.show_checks and not quiet and (r.get("checks") or {}):
            print("  Checks:")
            checks = r.get("checks") or {}
            for k in sorted(checks.keys()):
                print(f"    - {k}: {checks[k]}")

        if not quiet:
            print("")

    if not quiet:
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
    from pathlib import Path
    from datetime import datetime, timezone
    from core.packaging.aifv_packager import (
        build_aifv,
        AIFVInputs,
        ProvenanceTool,
        Attestation,
    )

    out_path = Path(ns.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ----------------------------
    # Primary tool (REQUIRED)
    # ----------------------------
    primary_name = (ns.primary_tool or "").strip()
    if not primary_name:
        raise SystemExit("ERROR: --primary-tool is required")

    primary_tool = ProvenanceTool(
        name=primary_name,
        version=(ns.primary_tool_version.strip() if ns.primary_tool_version else None),
    )

    # ----------------------------
    # Supporting tools (max 3)
    # ----------------------------
    supporting_tools = []
    for tool_name in (ns.supporting_tool or [])[:3]:
        t = (tool_name or "").strip()
        if t:
            supporting_tools.append(ProvenanceTool(name=t))

    # ----------------------------
    # Optional attestation
    # ----------------------------
    attestation = None
    if getattr(ns, "attest", False):
        initials = (ns.initials or "").strip()
        if not initials:
            raise SystemExit("ERROR: --initials required when using --attest")

        attestation = Attestation(
            template_id=(ns.template_id or "AIFX-SDA-001").strip(),
            initials=initials,
            accepted_at=datetime.now(timezone.utc).isoformat(),
        )

    # ----------------------------
    # Build inputs
    # ----------------------------
    inputs = AIFVInputs(
        video_path=Path(ns.video).expanduser().resolve(),
        thumb_path=Path(ns.thumb).expanduser().resolve(),
        out_path=out_path,
        title=str(ns.title),
        creator_name=str(ns.creator_name),
        creator_contact=str(ns.creator_contact),
        mode=str(ns.mode),

        primary_tool=primary_tool,
        supporting_tools=supporting_tools,
        origin_url=(ns.origin_url.strip() if ns.origin_url else None),
        attestation=attestation,
    )

    built = build_aifv(inputs)

    print(f"[OK] Built AIFV: {built}")
    return 0

def cmd_pack_aifm(ns: argparse.Namespace) -> int:
    from pathlib import Path
    from core.packaging.aifm_packager import build_aifm

    out_path = Path(ns.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    build_aifm(
        audio_path=Path(ns.audio).expanduser().resolve(),
        out_path=out_path,
        title=str(ns.title),
        creator_name=str(ns.creator_name),
        creator_contact=str(ns.creator_contact),
        mode=str(ns.mode),
        cover_path=Path(ns.cover).expanduser().resolve() if getattr(ns, "cover", None) else None,
    )

    print(f"[OK] Built AIFM: {out_path}")
    return 0

def cmd_pack_aifi(ns: argparse.Namespace) -> int:
    from pathlib import Path
    from core.packaging.aifi_packager import build_aifi

    out_path = Path(ns.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    built = build_aifi(
        image_path=Path(ns.image).expanduser().resolve(),
        out_path=out_path,
        title=str(ns.title),
        creator_name=str(ns.creator_name),
        creator_contact=str(ns.creator_contact),
        mode=str(ns.mode),
    )

    print(f"[OK] Built AIFI: {built}")
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
    p_val.add_argument("--quiet", action="store_true", help="Suppress human-readable output")
    
    p_val.set_defaults(fn=cmd_validate)

    p_aifv = sub.add_parser("pack-aifv", help="Package a video+thumb into .aifv (no transcoding)")
    p_aifv.add_argument("--video", required=True, help="Path to source video")
    p_aifv.add_argument("--thumb", required=True, help="Path to thumbnail (jpg/jpeg/png/webp)")
    p_aifv.add_argument("--out", required=True, help="Output .aifv path")
    p_aifv.add_argument("--title", required=True, help="work.title")
    p_aifv.add_argument("--creator-name", required=True, help="creator.name")
    p_aifv.add_argument("--creator-contact", required=True, help="creator.contact (email)")
    p_aifv.add_argument("--mode", default="human-directed-ai", help="mode (default: human-directed-ai)")

    # ----------------------------
    # Phase 2: Provenance (1 required + up to 3 optional)
    # ----------------------------
    p_aifv.add_argument(
        "--primary-tool",
        required=True,
        help="Primary AI tool used (required). Example: Meta, Veo, Runway, Pika, etc."
    )
    p_aifv.add_argument(
        "--primary-tool-version",
        default=None,
        help="Primary tool version (optional)"
    )
    p_aifv.add_argument(
        "--supporting-tool",
        action="append",
        default=[],
        help="Supporting tool name (repeat up to 3). Example: DALL·E, ElevenLabs, DaVinci, etc."
    )

    # Optional (no URLs required in v0, but allowed)
    p_aifv.add_argument(
        "--origin-url",
        default=None,
        help="Optional origin URL (not required in v0)"
    )

    # ----------------------------
    # Phase 2: Attestation (template + initials, timestamp auto)
    # ----------------------------
    p_aifv.add_argument(
        "--attest",
        action="store_true",
        help="Include an attestation block (requires --initials)"
    )
    p_aifv.add_argument(
        "--initials",
        default=None,
        help="Your initials for attestation (required if --attest)"
    )
    p_aifv.add_argument(
        "--template-id",
        default="AIFX-SDA-001",
        help="Attestation template ID (default: AIFX-SDA-001)"
    )

    p_aifv.set_defaults(fn=cmd_pack_aifv)

    p_aifm = sub.add_parser("pack-aifm", help="Package a single audio track into .aifm")
    p_aifm.add_argument("--audio", required=True, help="Path to audio (.wav/.mp3/.flac/.m4a/.ogg)")
    p_aifm.add_argument("--out", required=True, help="Output .aifm path")
    p_aifm.add_argument("--title", required=True, help="work.title")
    p_aifm.add_argument("--creator-name", required=True, help="creator.name")
    p_aifm.add_argument("--creator-contact", required=True, help="creator.contact (email)")
    p_aifm.add_argument("--mode", default="human-directed-ai", help="mode (default: human-directed-ai)")
    p_aifm.add_argument("--cover", default=None, help="optional cover image path")
    p_aifm.set_defaults(fn=cmd_pack_aifm)

    p_aifi = sub.add_parser("pack-aifi", help="Package a single image into .aifi")
    p_aifi.add_argument("--image", required=True, help="Path to image (.png/.jpg/.webp)")
    p_aifi.add_argument("--out", required=True, help="Output .aifi path")
    p_aifi.add_argument("--title", required=True, help="work.title")
    p_aifi.add_argument("--creator-name", required=True, help="creator.name")
    p_aifi.add_argument("--creator-contact", required=True, help="creator.contact (email)")
    p_aifi.add_argument("--mode", default="human-directed-ai", help="mode")
    p_aifi.set_defaults(fn=cmd_pack_aifi)

    ns = parser.parse_args(argv)
    return int(ns.fn(ns))

if __name__ == "__main__":
    raise SystemExit(main())
