# core/packaging/aifi_packager.py
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Optional
from core.provenance.sda_templates import AIFX_SDA_001_TEXT

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json_bytes(obj: dict) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_aifi(
    image_path: Path,
    out_path: Path,
    title: str,
    creator_name: str,
    creator_contact: str,
    mode: str = "human-directed-ai",
    *,
    aifx_version: str = "0.1",
    primary_tool: Optional[str] = None,
    supporting_tools: Optional[list[str]] = None,
) -> Path:
    image_path = image_path.expanduser().resolve()
    out_path = out_path.expanduser().resolve()

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    ext = image_path.suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported image type: {ext} (allowed: {sorted(ALLOWED_EXTS)})")

    if not out_path.name.lower().endswith(".aifi"):
        raise ValueError("Output file must end with .aifi")

    if not title.strip():
        raise ValueError("title must be non-empty")
    if not creator_name.strip():
        raise ValueError("creator_name must be non-empty")
    if not creator_contact.strip():
        raise ValueError("creator_contact must be non-empty")
    ptool = (primary_tool or "").strip()
    supporting = [s.strip() for s in (supporting_tools or []) if s and s.strip()]
    if not ptool:
        raise ValueError("provenance.primary_tool is required")
    if len(supporting) > 3:
        raise ValueError("provenance.supporting_tools cannot exceed 3")

    tmp_dir = out_path.parent / f".aifi_build_{out_path.stem}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        assets_dir = tmp_dir / "assets"
        assets_dir.mkdir()

        canonical_name = f"image{ext}"
        rel_image = f"assets/{canonical_name}"

        image_dest = assets_dir / canonical_name
        shutil.copy2(image_path, image_dest)

        image_hash = _sha256_file(image_dest)

        manifest: dict = {
            "aifx_version": aifx_version,
            "type": "AIFI",
            "work": {"title": title},
            "creator": {"name": creator_name, "contact": creator_contact},
            "mode": mode,
            "verification_tier": "SDA",
            "ai_generated": True,
            "declaration": AIFX_SDA_001_TEXT,
            "assets": {rel_image: {"sha256": image_hash}},
        }
        manifest["provenance"] = {"primary_tool": {"name": ptool}}
        if supporting:
            manifest["provenance"]["supporting_tools"] = [{"name": s} for s in supporting]

        manifest["integrity"] = {
            "algorithm": "sha256",
            "manifest_hash_mode": "canonical_excludes_self",
            "hashed_files": {
                rel_image: {"sha256": image_hash},
                "manifest.json": {"sha256": ""},
            },
        }

        manifest_for_hash = json.loads(json.dumps(manifest))
        hf = manifest_for_hash.get("integrity", {}).get("hashed_files", {})
        if isinstance(hf, dict):
            hf.pop("manifest.json", None)

        manifest_hash = _sha256_bytes(_canonical_json_bytes(manifest_for_hash))
        manifest["integrity"]["hashed_files"]["manifest.json"]["sha256"] = manifest_hash

        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()

        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(tmp_dir.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(tmp_dir))

        return out_path

    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
