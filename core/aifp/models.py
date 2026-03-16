from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ProjectRecord:
    project_id: str
    project_name: str
    project_root_name: str
    project_root_hint: str
    created_utc: str
    last_scanned_utc: str
    creator_name: str = ""
    creator_contact: str = ""
    mode: str = "human-directed-ai"
    status: str = "working"
    notes: str = ""
    history_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotRecord:
    snapshot_id: str
    project_id: str
    version_label_raw: str
    version_label_slug: str
    snapshot_kind: str
    created_utc: str
    scan_started_utc: str
    scan_completed_utc: str
    source_root_fingerprint: str
    file_count: int
    total_bytes: int
    asset_counts_by_type: dict[str, int] = field(default_factory=dict)
    primary_candidates: list[str] = field(default_factory=list)
    tree_stats: dict[str, Any] = field(default_factory=dict)
    compare_to_snapshot_id: str = ""
    diff_summary_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileInventoryEntry:
    relpath: str
    path_parts: list[str]
    entry_type: str
    size_bytes: int
    mtime_utc: str
    mtime_ns: int
    birth_utc_optional: Optional[str]
    sha256_optional: Optional[str]
    extension: str
    category: str
    hidden: bool
    excluded: bool
    read_error_optional: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiffSummary:
    base_snapshot_id: str
    target_snapshot_id: str
    added_paths: list[str] = field(default_factory=list)
    removed_paths: list[str] = field(default_factory=list)
    modified_paths: list[str] = field(default_factory=list)
    metadata_changed_paths: list[str] = field(default_factory=list)
    unchanged_count: int = 0
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    metadata_changed_count: int = 0
    human_summary: str = "Initial snapshot."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectScanResult:
    project: ProjectRecord
    snapshot: SnapshotRecord
    files: list[FileInventoryEntry]
    tree: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    diff: Optional[DiffSummary] = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "project": self.project.to_dict(),
            "snapshot": self.snapshot.to_dict(),
            "files": [item.to_dict() for item in self.files],
            "tree": self.tree,
            "warnings": list(self.warnings),
        }
        if self.diff is not None:
            data["diff"] = self.diff.to_dict()
        return data
