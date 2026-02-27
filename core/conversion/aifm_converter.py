# core/conversion/aifm_converter.py
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.conversion.converter_base import PackageBuild, build_package

ALLOWED_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
MIME_BY_EXT = {
    ".wav": "audio/x-wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
}

AIFX_STANDARD = "AI-First-Exchange"
AIFX_REPO = "https://github.com/ai-first-exchange"
FORMAT_NAME = "AIFM"
FORMAT_VERSION = "0.3"

ALLOWED_MODES = {"human-directed-ai", "ai-assisted", "ai-generated"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(p: Path) -> tuple[str, int]:
    h = sha256()
    size = 0
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_text(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")


def _is_email(s: str) -> bool:
    # Not “verification”, just syntax sanity.
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s.strip()))


def _default_declaration(
    *,
    creator_name: str,
    creator_contact: str,
    mode: str,
    ai_system: str | None,
    origin_url: str | None,
) -> str:
    sys_name = ai_system or "Unknown"
    url = origin_url or ""
    return (
        "AIFX Declaration\n"
        f"Creator: {creator_name}\n"
        f"Contact: {creator_contact}\n"
        f"Mode: {mode}\n"
        f"AI System: {sys_name}\n"
        f"Origin URL: {url}\n"
        f"Declared UTC: {_utc_now_iso()}\n"
    )


@dataclass(frozen=True)
class AIFMInputs:
    audio_path: Path
    title: str
    creator_name: str
    creator_contact: str
    mode: str = "human-directed-ai"
    ai_system: Optional[str] = None
    origin_platform: Optional[str] = None
    origin_url: Optional[str] = None

    # Optional metadata attachments
    prompt_text: Optional[str] = None
    lyrics_text: Optional[str] = None
    persona_text: Optional[str] = None
    cover_image_path: Optional[Path] = None

    # Declaration: required, but may be auto-generated if None/blank
    declaration_text: Optional[str] = None

    verification_tier: str = "SDA"


def convert_to_aifm(inputs: AIFMInputs, output_path: Path) -> Path:
    audio = inputs.audio_path.expanduser().resolve()
    if not audio.exists():
        raise FileNotFoundError(f"Audio not found: {audio}")

    ext = audio.suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTS:
        raise ValueError(f"Unsupported audio extension: {ext} (allowed: {sorted(ALLOWED_AUDIO_EXTS)})")

    if not inputs.creator_name.strip():
        raise ValueError("creator_name is required")
    if not inputs.creator_contact.strip():
        raise ValueError("creator_contact is required")
    if not _is_email(inputs.creator_contact):
        raise ValueError("creator_contact must be a valid email syntax (no verification, just format)")

    mode = inputs.mode.strip()
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of: {sorted(ALLOWED_MODES)}")

    title = inputs.title.strip()
    if not title:
        raise ValueError("title is required")

    mime = MIME_BY_EXT.get(ext, "audio/*")

    # Stage build folder
    staging = (
        Path(os.path.expanduser("~"))
        / ".aifx_staging"
        / f"aifm_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{os.getpid()}"
    )
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    payload_dir = staging / "payload"
    meta_dir = staging / "metadata"
    _safe_mkdir(payload_dir)
    _safe_mkdir(meta_dir)

    # Payload normalized path
    payload_rel = Path("payload") / f"audio{ext}"
    shutil.copy2(audio, staging / payload_rel)

    # Declaration (required; auto-gen allowed)
    decl = (inputs.declaration_text or "").strip()
    if not decl:
        decl = _default_declaration(
            creator_name=inputs.creator_name.strip(),
            creator_contact=inputs.creator_contact.strip(),
            mode=mode,
            ai_system=inputs.ai_system,
            origin_url=inputs.origin_url,
        )
    _write_text(meta_dir / "declaration.txt", decl)

    # Optional metadata files
    if (inputs.prompt_text or "").strip():
        _write_text(meta_dir / "prompt.txt", inputs.prompt_text.strip())
    if (inputs.lyrics_text or "").strip():
        _write_text(meta_dir / "lyrics.txt", inputs.lyrics_text.strip())
    if (inputs.persona_text or "").strip():
        _write_text(meta_dir / "persona.txt", inputs.persona_text.strip())

    if inputs.cover_image_path:
        cp = inputs.cover_image_path.expanduser().resolve()
        if cp.exists():
            # Preserve extension but normalize name
            shutil.copy2(cp, meta_dir / f"cover{cp.suffix.lower()}")

    # Manifest (v0.3 canon)
    manifest: dict[str, Any] = {
        "aifx": {
            "governance": {"standard": AIFX_STANDARD, "repo": AIFX_REPO},
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
        },
        "created_utc": _utc_now_iso(),
        "origin": {
            "ai_platform": (inputs.origin_platform or ""),
            "primary_url": (inputs.origin_url or ""),
        },
        "work": {"title": title, "type": "music"},
        "creator": {"name": inputs.creator_name.strip(), "contact": inputs.creator_contact.strip()},
        "ai": {"system": (inputs.ai_system or inputs.origin_platform or "")},
        "mode": mode,
        "verification": {"tier": inputs.verification_tier},
        "payload": {"primary": str(payload_rel).replace("\\", "/"), "mime": mime},
        "links": [],
        "metadata_refs": {"declaration_text": "metadata/declaration.txt"},
        "integrity": {"algorithm": "sha256", "hashed_files": {}, "manifest_hash_mode": "canonical_excludes_self"},
    }

    # Optional refs if present
    if (meta_dir / "prompt.txt").exists():
        manifest["metadata_refs"]["prompt"] = "metadata/prompt.txt"
    if (meta_dir / "lyrics.txt").exists():
        manifest["metadata_refs"]["lyrics"] = "metadata/lyrics.txt"
    if (meta_dir / "persona.txt").exists():
        manifest["metadata_refs"]["persona"] = "metadata/persona.txt"

    cover_candidates = list(meta_dir.glob("cover.*"))
    if cover_candidates:
        manifest["metadata_refs"]["cover_image"] = f"metadata/{cover_candidates[0].name}"

    # Output path normalization
    out = output_path.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() != ".aifm":
        out = out.with_suffix(".aifm")

    # --- REQUIRED AIFM IDENTITY ---
    # Title is identity; filename is fallback only
    title = (inputs.title or "").strip() or input_audio_path.stem

    manifest.setdefault("work", {})
    manifest["work"]["type"] = "music"
    manifest["work"]["title"] = title

    pkg = PackageBuild(
        format_name=FORMAT_NAME,
        format_version=FORMAT_VERSION,
        staging_root=staging,
        manifest=manifest,     # base will compute integrity + rewrite manifest.json
        out_path=out,
        cleanup=True,
    )
    return build_package(pkg)
