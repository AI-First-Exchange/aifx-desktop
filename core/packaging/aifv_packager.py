from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import zipfile


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_manifest_bytes(manifest: dict) -> bytes:
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


@dataclass
class AIFVInputs:
    video_path: Path
    thumb_path: Path
    out_path: Path
    title: str
    creator_name: str
    creator_contact: str
    declaration: str
    mode: str = "ai-generated"
    aifx_version: str = "0.1"
    # optional informational video facts (warning-only in v0)
    video_facts: Optional[Dict[str, Any]] = None


def build_aifv(inputs: AIFVInputs) -> Path:
    video_path = inputs.video_path
    thumb_path = inputs.thumb_path
    out_path = inputs.out_path

    if not video_path.is_file():
        raise FileNotFoundError(f"video not found: {video_path}")
    if not thumb_path.is_file():
        raise FileNotFoundError(f"thumbnail not found: {thumb_path}")

    title = (inputs.title or "").strip()
    creator_name = (inputs.creator_name or "").strip()
    creator_contact = (inputs.creator_contact or "").strip()
    declaration = (inputs.declaration or "").strip()
    mode = (inputs.mode or "").strip()

    if not title:
        raise ValueError("work.title required")
    if not creator_name:
        raise ValueError("creator.name required")
    if not creator_contact:
        raise ValueError("creator.contact required")
    if not declaration:
        raise ValueError("declaration required")
    if not mode:
        raise ValueError("mode required")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine extension and normalized asset path
    ext = video_path.suffix.lower().lstrip(".") or "mp4"
    asset_video_rel = f"assets/video.{ext}"
    asset_thumb_rel = "assets/thumb.jpg"

    video_bytes = video_path.read_bytes()
    thumb_bytes = thumb_path.read_bytes()

    # Minimal manifest base (aligns with your validator + governance)
    manifest: Dict[str, Any] = {
        "aifx": {"version": inputs.aifx_version},
        "work": {"title": title},
        "creator": {"name": creator_name, "contact": creator_contact},
        "mode": mode,
        "ai_generated": True,
        "verification_tier": "SDA",
        "declaration": declaration,
        # informational in v0
        "video": inputs.video_facts or {},
        "integrity": {
            "algorithm": "sha256",
            "manifest_hash_mode": "canonical_excludes_self",
            "hashed_files": {
                asset_video_rel: {"sha256": _sha256_bytes(video_bytes)},
                asset_thumb_rel: {"sha256": _sha256_bytes(thumb_bytes)},
                # manifest.json hash filled after canonicalization (excluding itself)
                "manifest.json": {"sha256": ""},
            },
        },
    }

    # Compute manifest.json hash canonically excluding itself
    m2 = json.loads(json.dumps(manifest))
    hf = (m2.get("integrity") or {}).get("hashed_files") or {}
    if "manifest.json" in hf:
        del hf["manifest.json"]
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


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Build an AIFV v0 package (.aifv) (packaging-only)")
    p.add_argument("--video", required=True, help="Path to input video file (e.g., mp4)")
    p.add_argument("--thumb", required=True, help="Path to thumbnail jpg")
    p.add_argument("--out", required=True, help="Output .aifv path")
    p.add_argument("--title", required=True, help="work.title")
    p.add_argument("--creator-name", required=True, help="creator.name")
    p.add_argument("--creator-contact", required=True, help="creator.contact (email)")
    p.add_argument("--declaration", required=True, help="Authorship declaration text")
    p.add_argument("--mode", default="ai-generated", help="mode (default: ai-generated)")
    args = p.parse_args()

    build_aifv(
        AIFVInputs(
            video_path=Path(args.video),
            thumb_path=Path(args.thumb),
            out_path=Path(args.out),
            title=args.title,
            creator_name=args.creator_name,
            creator_contact=args.creator_contact,
            declaration=args.declaration,
            mode=args.mode,
        )
    )
    print(f"OK: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
