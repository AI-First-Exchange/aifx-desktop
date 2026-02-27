from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.provenance.sda_templates import AIFX_SDA_001_TEXT

# ----------------------------
# Allowed extension enforcement (v0)
# ----------------------------
ALLOWED_VIDEO_EXTS = {"mp4", "mov", "webm", "m4v"}
ALLOWED_THUMB_EXTS = {"jpg", "jpeg", "png", "webp"}

# ----------------------------
# Canonical hashing helpers
# ----------------------------

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_manifest_bytes(manifest: dict) -> bytes:
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


# ----------------------------
# Provenance + Attestation
# ----------------------------

@dataclass
class ProvenanceTool:
    name: str
    version: Optional[str] = None

    def to_json(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": (self.name or "").strip()}
        if self.version:
            d["version"] = (self.version or "").strip()
        return d


@dataclass
class Attestation:
    template_id: str
    initials: str
    accepted_at: str  # ISO timestamp (UTC)

    def to_json(self) -> Dict[str, Any]:
        return {
            "template_id": (self.template_id or "").strip(),
            "initials": (self.initials or "").strip(),
            "accepted_at": (self.accepted_at or "").strip(),
        }


# ----------------------------
# Inputs
# ----------------------------

@dataclass
class AIFVInputs:
    video_path: Path
    thumb_path: Path
    out_path: Path
    title: str
    creator_name: str
    creator_contact: str

    mode: str = "human-directed-ai"
    aifx_version: str = "0.1"

    # Optional informational video facts (warning-only in v0)
    video_facts: Optional[Dict[str, Any]] = None

    # Provenance (new reality)
    primary_tool: Optional[ProvenanceTool] = None                # REQUIRED (we enforce below)
    supporting_tools: Optional[List[ProvenanceTool]] = None      # up to 3 optional
    origin_url: Optional[str] = None                              # optional

    # Optional attestation (checkbox flow later)
    attestation: Optional[Attestation] = None


# ----------------------------
# Builder
# ----------------------------

def build_aifv(inputs: AIFVInputs) -> Path:
    video_path = inputs.video_path.expanduser().resolve()
    thumb_path = inputs.thumb_path.expanduser().resolve()
    out_path = inputs.out_path.expanduser().resolve()

    if not video_path.is_file():
        raise FileNotFoundError(f"video not found: {video_path}")
    if not thumb_path.is_file():
        raise FileNotFoundError(f"thumbnail not found: {thumb_path}")

    title = (inputs.title or "").strip()
    creator_name = (inputs.creator_name or "").strip()
    creator_contact = (inputs.creator_contact or "").strip()
    mode = (inputs.mode or "").strip()

    if not title:
        raise ValueError("work.title required")
    if not creator_name:
        raise ValueError("creator.name required")
    if not creator_contact:
        raise ValueError("creator.contact required")
    if not mode:
        raise ValueError("mode required")

    # --- Provenance enforcement (Phase 2 direction) ---
    if inputs.primary_tool is None or not (inputs.primary_tool.name or "").strip():
        raise ValueError("provenance.primary_tool.name required (Phase 2)")

    supporting_tools: List[ProvenanceTool] = list(inputs.supporting_tools or [])
    if len(supporting_tools) > 3:
        raise ValueError("provenance.supporting_tools cannot exceed 3")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine extension and normalized asset path
    vext = video_path.suffix.lower().lstrip(".") or "mp4"
    thumb_ext = thumb_path.suffix.lower().lstrip(".") or "jpg"

    if vext not in ALLOWED_VIDEO_EXTS:
        raise ValueError(f"unsupported video type: .{vext}")

    if thumb_ext not in ALLOWED_THUMB_EXTS:
        raise ValueError(f"unsupported thumbnail type: .{thumb_ext}")

    asset_video_rel = f"assets/video.{vext}"
    asset_thumb_rel = f"assets/thumb.{thumb_ext}"

    video_bytes = video_path.read_bytes()
    thumb_bytes = thumb_path.read_bytes()

    video_sha = _sha256_bytes(video_bytes)
    thumb_sha = _sha256_bytes(thumb_bytes)

    provenance: Dict[str, Any] = {
        "primary_tool": inputs.primary_tool.to_json(),
    }
    if supporting_tools:
        provenance["supporting_tools"] = [t.to_json() for t in supporting_tools]

    # Minimal manifest base (standardized SDA declaration)
    manifest: Dict[str, Any] = {
        "aifx_version": inputs.aifx_version,
        "type": "AIFV",
        "work": {"title": title},
        "creator": {"name": creator_name, "contact": creator_contact},
        "mode": mode,
        "verification_tier": "SDA",
        "ai_generated": True,
        "declaration": AIFX_SDA_001_TEXT,

        # provenance + optional origin
        "provenance": provenance,
    }

    # Optional origin_url (string)
    if inputs.origin_url and (inputs.origin_url or "").strip():
        manifest["origin_url"] = (inputs.origin_url or "").strip()

    # Optional attestation (checkbox later; packer supports now)
    if inputs.attestation is not None:
        att = inputs.attestation.to_json()
        # If present, enforce minimum sanity now
        if not att.get("template_id"):
            raise ValueError("attestation.template_id required if attestation provided")
        if not att.get("initials"):
            raise ValueError("attestation.initials required if attestation provided")
        if not att.get("accepted_at"):
            raise ValueError("attestation.accepted_at required if attestation provided")
        manifest["attestation"] = att

    # informational in v0 (warning-only)
    manifest["video"] = inputs.video_facts or {}

    # Canonical integrity block
    manifest["integrity"] = {
        "algorithm": "sha256",
        "manifest_hash_mode": "canonical_excludes_self",
        "hashed_files": {
            asset_video_rel: {"sha256": video_sha},
            asset_thumb_rel: {"sha256": thumb_sha},
            "manifest.json": {"sha256": ""},  # placeholder
        },
    }

    # Compute manifest.json hash canonically excluding itself
    m2 = json.loads(json.dumps(manifest))
    hf = (m2.get("integrity") or {}).get("hashed_files") or {}
    hf.pop("manifest.json", None)

    canon = _canonical_manifest_bytes(m2)
    manifest_hash = _sha256_bytes(canon)
    manifest["integrity"]["hashed_files"]["manifest.json"]["sha256"] = manifest_hash

    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")

    # Write ZIP container
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest_bytes)
        z.writestr(asset_video_rel, video_bytes)
        z.writestr(asset_thumb_rel, thumb_bytes)

    return out_path


# ----------------------------
# Optional CLI runner (dev only)
# ----------------------------

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Build an AIFV v0 package (.aifv) (packaging-only)")
    p.add_argument("--video", required=True, help="Path to input video file (e.g., mp4)")
    p.add_argument("--thumb", required=True, help="Path to thumbnail (jpg/png/webp)")
    p.add_argument("--out", required=True, help="Output .aifv path")
    p.add_argument("--title", required=True, help="work.title")
    p.add_argument("--creator-name", required=True, help="creator.name")
    p.add_argument("--creator-contact", required=True, help="creator.contact (email)")
    p.add_argument("--mode", default="human-directed-ai", help="mode (default: human-directed-ai)")

    # provenance (Phase 2)
    p.add_argument("--primary-tool", required=True, help="Primary AI tool used (required)")
    p.add_argument("--primary-tool-version", default=None, help="Primary tool version (optional)")
    p.add_argument("--supporting-tool", action="append", default=[], help="Supporting tool name (repeat up to 3)")
    p.add_argument("--origin-url", default=None, help="Optional origin URL (project link / page)")

    # attestation (optional)
    p.add_argument("--attest", action="store_true", help="Include attestation block")
    p.add_argument("--initials", default=None, help="Initials for attestation (required if --attest)")
    p.add_argument("--template-id", default="AIFX-SDA-001", help="Attestation template id (default AIFX-SDA-001)")

    args = p.parse_args()

    supporting = []
    for name in (args.supporting_tool or [])[:3]:
        n = (name or "").strip()
        if n:
            supporting.append(ProvenanceTool(name=n))

    att: Optional[Attestation] = None
    if args.attest:
        ini = (args.initials or "").strip()
        if not ini:
            raise SystemExit("ERROR: --initials required when using --attest")
        att = Attestation(
            template_id=(args.template_id or "AIFX-SDA-001").strip(),
            initials=ini,
            accepted_at=datetime.now(timezone.utc).isoformat(),
        )

    build_aifv(
        AIFVInputs(
            video_path=Path(args.video),
            thumb_path=Path(args.thumb),
            out_path=Path(args.out),
            title=args.title,
            creator_name=args.creator_name,
            creator_contact=args.creator_contact,
            mode=args.mode,
            primary_tool=ProvenanceTool(
                name=(args.primary_tool or "").strip(),
                version=(args.primary_tool_version or None),
            ),
            supporting_tools=supporting,
            origin_url=args.origin_url,
            attestation=att,
        )
    )
    print(f"OK: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
