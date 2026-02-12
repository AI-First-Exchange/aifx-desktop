from __future__ import annotations

import argparse
import json
import zipfile
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_manifest_bytes(manifest: dict) -> bytes:
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _ensure_file(p: Path, label: str) -> None:
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"{label} not found: {p}")


def build_aifm(
    *,
    audio_path: Path,
    out_path: Path,
    title: str,
    creator_name: str,
    creator_contact: str,
    declaration: str,
    mode: str = "human-directed-ai",
    cover_path: Optional[Path] = None,
) -> None:
    _ensure_file(audio_path, "audio")
    if cover_path is not None:
        _ensure_file(cover_path, "cover")

    if not out_path.name.lower().endswith(".aifm"):
        raise ValueError("out_path must end with .aifm")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    audio_ext = audio_path.suffix.lower().lstrip(".") or "bin"
    audio_rel = f"assets/audio.{audio_ext}"
    cover_rel = "assets/cover.jpg"  # normalize name regardless of input ext

    # Minimal governance-aligned manifest
    manifest: Dict[str, Any] = {
        "aifx": {"version": "0"},
        "work": {"title": str(title).strip()},
        "creator": {"name": str(creator_name).strip(), "contact": str(creator_contact).strip()},
        "mode": str(mode).strip(),
        "ai_generated": True,
        "verification_tier": "SDA",
        "declaration": str(declaration).strip(),
        "format": "AIFM",
        "assets": {
            "audio": audio_rel,
        },
    }

    if cover_path is not None:
        manifest["assets"]["cover"] = cover_rel

    # Prepare file bytes for hashing
    audio_bytes = audio_path.read_bytes()
    cover_bytes = cover_path.read_bytes() if cover_path is not None else None

    # Build hashed_files (manifest hash computed canonically excluding itself)
    hashed_files: Dict[str, Dict[str, str]] = {
        audio_rel: {"sha256": _sha256_bytes(audio_bytes)},
    }
    if cover_bytes is not None:
        hashed_files[cover_rel] = {"sha256": _sha256_bytes(cover_bytes)}

    manifest["integrity"] = {
        "algorithm": "sha256",
        "manifest_hash_mode": "canonical_excludes_self",
        "hashed_files": hashed_files,
    }

    # Canonical manifest hash excluding the manifest.json entry
    m2 = json.loads(json.dumps(manifest))
    hf = (m2.get("integrity") or {}).get("hashed_files") or {}
    if "manifest.json" in hf:
        del hf["manifest.json"]

    manifest_hash = _sha256_bytes(_canonical_manifest_bytes(m2))
    manifest["integrity"]["hashed_files"]["manifest.json"] = {"sha256": manifest_hash}

    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")

    # Write ZIP container
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest_bytes)
        z.writestr(audio_rel, audio_bytes)
        if cover_bytes is not None:
            z.writestr(cover_rel, cover_bytes)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="AIFM packager (v0) — packaging-only, no transcoding")
    ap.add_argument("--audio", required=True, help="Path to audio file")
    ap.add_argument("--out", required=True, help="Output .aifm path")
    ap.add_argument("--title", required=True, help="work.title")
    ap.add_argument("--creator-name", required=True, help="creator.name")
    ap.add_argument("--creator-contact", required=True, help="creator.contact")
    ap.add_argument("--declaration", required=True, help="authorship declaration")
    ap.add_argument("--mode", default="human-directed-ai", help="mode (default: human-directed-ai)")
    ap.add_argument("--cover", default=None, help="optional cover image path")

    ns = ap.parse_args(argv)

    build_aifm(
        audio_path=Path(ns.audio).expanduser().resolve(),
        out_path=Path(ns.out).expanduser().resolve(),
        title=ns.title,
        creator_name=ns.creator_name,
        creator_contact=ns.creator_contact,
        declaration=ns.declaration,
        mode=ns.mode,
        cover_path=Path(ns.cover).expanduser().resolve() if ns.cover else None,
    )
    print(f"OK: wrote {ns.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
