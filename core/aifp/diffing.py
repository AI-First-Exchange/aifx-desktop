from __future__ import annotations

from typing import Optional

from .models import DiffSummary, FileInventoryEntry


def _same_content(old: FileInventoryEntry, new: FileInventoryEntry) -> bool:
    if old.sha256_optional and new.sha256_optional:
        return old.sha256_optional == new.sha256_optional
    return (
        old.size_bytes == new.size_bytes
        and old.mtime_ns == new.mtime_ns
        and old.entry_type == new.entry_type
    )


def diff_snapshots(
    old_files: list[FileInventoryEntry],
    new_files: list[FileInventoryEntry],
    *,
    base_snapshot_id: str = "",
    target_snapshot_id: str = "",
) -> Optional[DiffSummary]:
    if not old_files:
        return None

    old_map = {item.relpath: item for item in old_files}
    new_map = {item.relpath: item for item in new_files}

    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    modified: list[str] = []
    metadata_changed: list[str] = []
    unchanged = 0

    for relpath in sorted(set(old_map) & set(new_map)):
        old_item = old_map[relpath]
        new_item = new_map[relpath]
        if not _same_content(old_item, new_item):
            modified.append(relpath)
            continue

        if (
            old_item.mtime_ns != new_item.mtime_ns
            or old_item.birth_utc_optional != new_item.birth_utc_optional
            or old_item.category != new_item.category
            or old_item.hidden != new_item.hidden
        ):
            metadata_changed.append(relpath)
        else:
            unchanged += 1

    return DiffSummary(
        base_snapshot_id=base_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        added_paths=added,
        removed_paths=removed,
        modified_paths=modified,
        metadata_changed_paths=metadata_changed,
        unchanged_count=unchanged,
        added_count=len(added),
        removed_count=len(removed),
        modified_count=len(modified),
        metadata_changed_count=len(metadata_changed),
        human_summary=(
            f"{len(added)} files added, {len(removed)} removed, "
            f"{len(modified)} modified, {len(metadata_changed)} metadata-only changes."
        ),
    )
