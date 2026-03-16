from __future__ import annotations

import re
from pathlib import Path


_DISALLOWED_CHARS = re.compile(r'[^A-Za-z0-9._ -]+')
_SPACE_RUN = re.compile(r"\s+")
_DASH_RUN = re.compile(r"-{2,}")


def sanitize_slug(value: str, *, default: str, allow_dots: bool = True) -> str:
    text = (value or "").strip()
    text = text.replace("\\", " ").replace("/", " ")
    text = _DISALLOWED_CHARS.sub("", text)
    if not allow_dots:
        text = text.replace(".", " ")
    text = _SPACE_RUN.sub("-", text)
    text = text.strip(" .-_")
    text = _DASH_RUN.sub("-", text)
    return text or default


def project_slug(project_name: str) -> str:
    return sanitize_slug(project_name, default="project", allow_dots=False).lower()


def version_slug(version_label: str) -> str:
    return sanitize_slug(version_label, default="snapshot", allow_dots=True).lower()


def build_output_filename(project_name: str, version_label: str, *, locked: bool) -> str:
    slug = project_slug(project_name)
    if locked:
        return f"{slug}.aifp"
    return f"{slug}.aifp-{version_slug(version_label)}"


def resolve_output_path(output_dir: str | Path, project_name: str, version_label: str, *, locked: bool) -> Path:
    return Path(output_dir).expanduser().resolve() / build_output_filename(
        project_name,
        version_label,
        locked=locked,
    )


def is_aifp_working_name(name: str) -> bool:
    lower = name.lower()
    return ".aifp-" in lower and not lower.endswith(".aifp")


def detect_package_kind(path: str | Path) -> str:
    name = Path(path).name.lower()
    if name.endswith(".aifm"):
        return "aifm"
    if name.endswith(".aifi"):
        return "aifi"
    if name.endswith(".aifv"):
        return "aifv"
    if name.endswith(".aifp") or ".aifp-" in name:
        return "aifp"
    if name.endswith(".aifx"):
        return "aifx"
    return ""


def is_aifx_package_path(path: str | Path) -> bool:
    return bool(detect_package_kind(path))
