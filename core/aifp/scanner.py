from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .diffing import diff_snapshots
from .models import FileInventoryEntry, ProjectRecord, ProjectScanResult, SnapshotRecord
from .naming import project_slug, version_slug

_DIR_EXCLUDES = {
    ".git",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}
_FILE_EXACT_EXCLUDES = {
    ".DS_Store",
    "Thumbs.db",
}
_FILE_SUFFIX_EXCLUDES = (
    ".swp",
    ".tmp",
    ".temp",
    ".bak",
)
_AIFX_OUTPUT_MARKERS = (".aifm", ".aifi", ".aifv", ".aifp", ".aifp-", ".aifx")

_CATEGORY_BY_EXT = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".svg": "image",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".m4v": "video",
    ".wav": "audio",
    ".mp3": "audio",
    ".flac": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
    ".txt": "text",
    ".md": "text",
    ".rtf": "document",
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
    ".zip": "archive",
    ".tar": "archive",
    ".gz": "archive",
    ".7z": "archive",
    ".json": "data",
    ".yaml": "data",
    ".yml": "data",
    ".csv": "data",
    ".tsv": "data",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".tsx": "code",
    ".jsx": "code",
    ".cpp": "code",
    ".c": "code",
    ".h": "code",
    ".rs": "code",
    ".go": "code",
    ".java": "code",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stat_time_to_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")


def _birth_time_iso(stat_result: os.stat_result) -> Optional[str]:
    created = getattr(stat_result, "st_birthtime", None)
    if created is None:
        return None
    try:
        return _stat_time_to_iso(float(created))
    except Exception:
        return None


def _is_hidden(parts: Iterable[str]) -> bool:
    return any(part.startswith(".") for part in parts if part)


def _should_exclude(rel_parts: list[str], is_dir: bool) -> bool:
    if not rel_parts:
        return False
    name = rel_parts[-1]
    if is_dir and any(part in _DIR_EXCLUDES for part in rel_parts):
        return True
    if name in _FILE_EXACT_EXCLUDES:
        return True
    if any(name.endswith(suffix) for suffix in _FILE_SUFFIX_EXCLUDES):
        return True
    lower_name = name.lower()
    return any(marker in lower_name for marker in _AIFX_OUTPUT_MARKERS)


def _normalize_relpath(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _category_for_path(path: Path) -> str:
    return _CATEGORY_BY_EXT.get(path.suffix.lower(), "other")


def _primary_candidates(files: list[FileInventoryEntry]) -> list[str]:
    ranked = sorted(
        (
            item for item in files
            if item.entry_type == "file" and not item.excluded
        ),
        key=lambda item: (
            item.category not in {"video", "image", "audio", "document", "code"},
            -item.size_bytes,
            item.relpath,
        ),
    )
    return [item.relpath for item in ranked[:5]]


def _tree_from_entries(root_name: str, files: list[FileInventoryEntry]) -> dict:
    tree: dict = {"name": root_name, "type": "dir", "children": {}}
    for entry in sorted(files, key=lambda item: item.relpath):
        if entry.excluded:
            continue
        node = tree
        for index, part in enumerate(entry.path_parts):
            children = node.setdefault("children", {})
            is_leaf = index == len(entry.path_parts) - 1
            if part not in children:
                children[part] = {
                    "name": part,
                    "type": entry.entry_type if is_leaf else "dir",
                    "children": {},
                }
            node = children[part]
            if is_leaf:
                node["type"] = entry.entry_type

    def collapse(node: dict) -> dict:
        children = node.get("children", {})
        if children:
            node["children"] = [collapse(children[name]) for name in sorted(children)]
        else:
            node.pop("children", None)
        return node

    return collapse(tree)


def _root_fingerprint(files: list[FileInventoryEntry]) -> str:
    h = hashlib.sha256()
    for item in sorted(files, key=lambda x: x.relpath):
        h.update(item.relpath.encode("utf-8"))
        h.update(str(item.size_bytes).encode("utf-8"))
        h.update(str(item.mtime_ns).encode("utf-8"))
        if item.sha256_optional:
            h.update(item.sha256_optional.encode("utf-8"))
    return h.hexdigest()


def scan_project(
    root_path: Path,
    *,
    version_label: str,
    project_name: str = "",
    creator_name: str = "",
    creator_contact: str = "",
    mode: str = "human-directed-ai",
    notes: str = "",
    mark_complete: bool = False,
    previous_snapshot: Optional[dict] = None,
) -> ProjectScanResult:
    root = root_path.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Project folder not found: {root}")

    started_at = _utc_now_iso()
    prev_file_map: dict[str, FileInventoryEntry] = {}
    previous_snapshot_id = ""
    previous_files: list[FileInventoryEntry] = []
    if previous_snapshot:
        previous_snapshot_id = str(previous_snapshot.get("snapshot", {}).get("snapshot_id", ""))
        for item in previous_snapshot.get("files", []):
            entry = FileInventoryEntry(**item)
            prev_file_map[entry.relpath] = entry
            previous_files.append(entry)

    files: list[FileInventoryEntry] = []
    warnings: list[str] = []
    dir_count = 0

    for current_root, dirnames, filenames in os.walk(root, topdown=True):
        current_dir = Path(current_root)
        rel_dir = _normalize_relpath(root, current_dir) if current_dir != root else ""
        dir_parts = [part for part in rel_dir.split("/") if part]

        filtered_dirs: list[str] = []
        for dirname in sorted(dirnames):
            parts = dir_parts + [dirname]
            if _should_exclude(parts, True):
                warnings.append(f"Excluded directory: {'/'.join(parts)}")
                continue
            filtered_dirs.append(dirname)
        dirnames[:] = filtered_dirs

        if rel_dir:
            dir_count += 1
            files.append(
                FileInventoryEntry(
                    relpath=rel_dir,
                    path_parts=dir_parts,
                    entry_type="dir",
                    size_bytes=0,
                    mtime_utc="",
                    mtime_ns=0,
                    birth_utc_optional=None,
                    sha256_optional=None,
                    extension="",
                    category="directory",
                    hidden=_is_hidden(dir_parts),
                    excluded=False,
                )
            )

        for filename in sorted(filenames):
            path = current_dir / filename
            relpath = _normalize_relpath(root, path)
            rel_parts = [part for part in relpath.split("/") if part]
            hidden = _is_hidden(rel_parts)

            if _should_exclude(rel_parts, False):
                files.append(
                    FileInventoryEntry(
                        relpath=relpath,
                        path_parts=rel_parts,
                        entry_type="file",
                        size_bytes=0,
                        mtime_utc="",
                        mtime_ns=0,
                        birth_utc_optional=None,
                        sha256_optional=None,
                        extension=path.suffix.lower(),
                        category=_category_for_path(path),
                        hidden=hidden,
                        excluded=True,
                    )
                )
                continue

            if path.is_symlink():
                files.append(
                    FileInventoryEntry(
                        relpath=relpath,
                        path_parts=rel_parts,
                        entry_type="symlink",
                        size_bytes=0,
                        mtime_utc="",
                        mtime_ns=0,
                        birth_utc_optional=None,
                        sha256_optional=None,
                        extension=path.suffix.lower(),
                        category=_category_for_path(path),
                        hidden=hidden,
                        excluded=False,
                        read_error_optional="Symlink skipped in AIFP v1.",
                    )
                )
                warnings.append(f"Skipped symlink: {relpath}")
                continue

            try:
                stat_result = path.stat()
                mtime_ns = int(getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000)))
                reused = prev_file_map.get(relpath)
                sha256 = None
                if (
                    reused
                    and reused.sha256_optional
                    and reused.size_bytes == stat_result.st_size
                    and reused.mtime_ns == mtime_ns
                    and reused.entry_type == "file"
                ):
                    sha256 = reused.sha256_optional
                else:
                    sha256 = _sha256_file(path)

                files.append(
                    FileInventoryEntry(
                        relpath=relpath,
                        path_parts=rel_parts,
                        entry_type="file",
                        size_bytes=int(stat_result.st_size),
                        mtime_utc=_stat_time_to_iso(stat_result.st_mtime),
                        mtime_ns=mtime_ns,
                        birth_utc_optional=_birth_time_iso(stat_result),
                        sha256_optional=sha256,
                        extension=path.suffix.lower(),
                        category=_category_for_path(path),
                        hidden=hidden,
                        excluded=False,
                    )
                )
            except Exception as exc:
                files.append(
                    FileInventoryEntry(
                        relpath=relpath,
                        path_parts=rel_parts,
                        entry_type="unreadable",
                        size_bytes=0,
                        mtime_utc="",
                        mtime_ns=0,
                        birth_utc_optional=None,
                        sha256_optional=None,
                        extension=path.suffix.lower(),
                        category=_category_for_path(path),
                        hidden=hidden,
                        excluded=False,
                        read_error_optional=str(exc),
                    )
                )
                warnings.append(f"Unreadable file: {relpath} ({exc})")

    completed_at = _utc_now_iso()
    included_files = [item for item in files if item.entry_type == "file" and not item.excluded]

    category_counts: dict[str, int] = {}
    unreadable_count = 0
    excluded_count = 0
    symlink_count = 0
    total_bytes = 0
    for item in files:
        if item.excluded:
            excluded_count += 1
            continue
        if item.entry_type == "file":
            total_bytes += item.size_bytes
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        elif item.entry_type == "unreadable":
            unreadable_count += 1
        elif item.entry_type == "symlink":
            symlink_count += 1

    project_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    project_name = (project_name or "").strip() or root.name
    snapshot_id_seed = f"{project_id}:{completed_at}:{version_label}:{mark_complete}"
    snapshot_id = hashlib.sha256(snapshot_id_seed.encode("utf-8")).hexdigest()[:16]
    version_raw = version_label.strip()
    version_clean = "" if mark_complete else version_slug(version_raw)

    project = ProjectRecord(
        project_id=project_id,
        project_name=project_name,
        project_root_name=root.name,
        project_root_hint=root.name,
        created_utc=completed_at,
        last_scanned_utc=completed_at,
        creator_name=creator_name.strip(),
        creator_contact=creator_contact.strip(),
        mode=mode,
        status="final" if mark_complete else "working",
        notes=notes.strip(),
        history_ref=project_id,
    )

    snapshot = SnapshotRecord(
        snapshot_id=snapshot_id,
        project_id=project_id,
        version_label_raw=version_raw,
        version_label_slug=version_clean,
        snapshot_kind="final" if mark_complete else "working",
        created_utc=completed_at,
        scan_started_utc=started_at,
        scan_completed_utc=completed_at,
        source_root_fingerprint=_root_fingerprint(included_files),
        file_count=len(included_files),
        total_bytes=total_bytes,
        asset_counts_by_type=dict(sorted(category_counts.items())),
        primary_candidates=_primary_candidates(included_files),
        tree_stats={
            "directory_count": dir_count,
            "file_count": len(included_files),
            "unreadable_count": unreadable_count,
            "excluded_count": excluded_count,
            "symlink_count": symlink_count,
        },
        compare_to_snapshot_id=previous_snapshot_id,
        diff_summary_ref="manifests/diff.json" if previous_snapshot_id else "",
    )

    diff = diff_snapshots(
        previous_files,
        included_files,
        base_snapshot_id=previous_snapshot_id,
        target_snapshot_id=snapshot_id,
    )

    if diff is None:
        snapshot.compare_to_snapshot_id = ""
        snapshot.diff_summary_ref = ""

    tree = _tree_from_entries(root.name, files)
    return ProjectScanResult(
        project=project,
        snapshot=snapshot,
        files=files,
        tree=tree,
        warnings=warnings,
        diff=diff,
    )
