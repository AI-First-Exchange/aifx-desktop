from __future__ import annotations

import posixpath
import re
import zipfile
from typing import Any, Dict, List, Tuple

PRIMARY_VIDEO_RE = re.compile(r"^assets/video\.[^/]+$")  # assets/video.*
THUMB_PATH = "assets/thumb.jpg"


def _is_unsafe_path(name: str) -> bool:
    """
    Zip-slip / unsafe path detection.
    Treat ZIP entries as POSIX paths.
    """
    if name.startswith("/") or name.startswith("\\"):
        return True

    name_norm = name.replace("\\", "/")

    # Reject drive-like prefixes (Windows), e.g. C:/...
    if re.match(r"^[A-Za-z]:/", name_norm):
        return True

    norm = posixpath.normpath(name_norm)
    if norm.startswith("../") or norm == "..":
        return True

    parts = [p for p in name_norm.split("/") if p]
    if any(p == ".." for p in parts):
        return True

    return False


def _zipinfo_is_symlink(zinfo: zipfile.ZipInfo) -> bool:
    """
    Best-effort symlink detection for ZIP entries created on Unix.
    """
    mode = (zinfo.external_attr >> 16) & 0o170000
    return mode == 0o120000  # symlink


def _nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def validate_aifv(z: zipfile.ZipFile, manifest: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    AIFV v0 format-specific validation.

    Returns:
      checks: dict
      errors: list[str]
      warnings: list[str]

    NOTE:
    - Integrity verification is handled by core/validation/validator.py via _verify_integrity().
    - This module enforces AIFV structure + security + strict governance fields.
    """
    checks: Dict[str, Any] = {}
    errors: List[str] = []
    warnings: List[str] = []

    infos = z.infolist()
    names = set(z.namelist())

    # --- Security: safe paths + no symlinks ---
    safe_paths_ok = True
    no_symlinks_ok = True

    for zi in infos:
        if _is_unsafe_path(zi.filename):
            safe_paths_ok = False
        if _zipinfo_is_symlink(zi):
            no_symlinks_ok = False

    checks["security.safe_paths"] = safe_paths_ok
    if not safe_paths_ok:
        errors.append("security: unsafe path detected (possible zip-slip)")

    checks["security.no_symlinks"] = no_symlinks_ok
    if not no_symlinks_ok:
        errors.append("security: symlinks are not allowed")

    # --- Required files ---
    thumb_present = THUMB_PATH in names
    checks["files.thumbnail_present"] = thumb_present
    if not thumb_present:
        errors.append("assets/thumb.jpg missing (required)")

    primary_videos = [n for n in names if PRIMARY_VIDEO_RE.match(n)]
    primary_ok = (len(primary_videos) == 1)
    checks["files.primary_video_single"] = primary_ok
    if not primary_ok:
        if len(primary_videos) == 0:
            errors.append("primary video missing (expected exactly one file matching assets/video.*)")
        else:
            errors.append("multiple primary videos found (expected exactly one file matching assets/video.*)")

    # --- Manifest governance (AIFV strict) ---
    work = manifest.get("work") if isinstance(manifest.get("work"), dict) else {}
    creator = manifest.get("creator") if isinstance(manifest.get("creator"), dict) else {}

    title_ok = _nonempty_str(work.get("title"))
    checks["manifest.work.title"] = title_ok
    if not title_ok:
        errors.append("work.title missing (required)")

    cname_ok = _nonempty_str(creator.get("name"))
    checks["manifest.creator.name"] = cname_ok
    if not cname_ok:
        errors.append("creator.name missing (required)")

    ccontact_ok = _nonempty_str(creator.get("contact"))
    checks["manifest.creator.contact"] = ccontact_ok
    if not ccontact_ok:
        errors.append("creator.contact missing (email required)")

    mode_ok = _nonempty_str(manifest.get("mode"))
    checks["manifest.mode"] = mode_ok
    if not mode_ok:
        errors.append("mode missing (required)")

    # v0 lock: strict ai_generated must be true (no mode-only fallback)
    ai_ok = (manifest.get("ai_generated") is True)
    checks["manifest.ai_generated"] = ai_ok
    if not ai_ok:
        errors.append("ai_generated must be true (required)")

    tier_ok = (manifest.get("verification_tier") == "SDA")
    checks["manifest.verification_tier"] = tier_ok
    if not tier_ok:
        errors.append("verification_tier must be 'SDA' (required)")

    decl_ok = _nonempty_str(manifest.get("declaration"))
    checks["manifest.declaration"] = decl_ok
    if not decl_ok:
        errors.append("declaration missing (required)")

    # --- Informational: video facts (warning only) ---
    video_obj = manifest.get("video") if isinstance(manifest.get("video"), dict) else None
    facts_ok = isinstance(video_obj, dict) and any(
        k in video_obj for k in ("duration", "width", "height", "fps", "codec", "container")
    )
    checks["info.video_facts_present"] = facts_ok
    if not facts_ok:
        warnings.append("info: video facts missing (duration/resolution/fps/codecs) — not required in v0")

    return checks, errors, warnings
