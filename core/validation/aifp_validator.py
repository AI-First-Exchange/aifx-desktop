from __future__ import annotations

from typing import Any, Dict, List, Tuple
import zipfile


def validate_aifp(z: zipfile.ZipFile, manifest: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
    checks: Dict[str, Any] = {}
    errors: List[str] = []
    warnings: List[str] = []

    required = [
        "manifest.json",
        "manifests/project.json",
        "manifests/snapshot.json",
        "manifests/files.json",
        "manifests/tree.json",
    ]
    names = set(z.namelist())
    for relpath in required:
        present = relpath in names
        checks[f"files.{relpath}"] = present
        if not present:
            errors.append(f"{relpath} missing (required)")

    type_ok = manifest.get("type") == "AIFP"
    checks["manifest.type"] = type_ok
    if not type_ok:
        errors.append("manifest.type must be 'AIFP'")

    project = manifest.get("project") if isinstance(manifest.get("project"), dict) else {}
    locked = project.get("locked") is True
    status = project.get("status")
    snapshot_kind = project.get("snapshot_kind")
    metadata_refs = manifest.get("metadata_refs") if isinstance(manifest.get("metadata_refs"), dict) else {}

    checks["manifest.project.status"] = status in {"working", "final"}
    if not checks["manifest.project.status"]:
        errors.append("manifest.project.status must be 'working' or 'final'")

    checks["manifest.project.snapshot_kind"] = snapshot_kind in {"working", "final"}
    if not checks["manifest.project.snapshot_kind"]:
        errors.append("manifest.project.snapshot_kind must be 'working' or 'final'")

    lifecycle_ok = (locked and status == "final" and snapshot_kind == "final") or (
        not locked and status == "working" and snapshot_kind == "working"
    )
    checks["manifest.project.lifecycle"] = lifecycle_ok
    if not lifecycle_ok:
        errors.append("manifest.project lifecycle fields are inconsistent")

    files_embedded = project.get("assets_embedded")
    checks["manifest.project.assets_embedded"] = files_embedded is False
    if files_embedded is not False:
        errors.append("AIFP v1 must declare assets_embedded as false")

    refs_ok = metadata_refs.get("project") == "manifests/project.json"
    refs_ok = refs_ok and metadata_refs.get("snapshot") == "manifests/snapshot.json"
    refs_ok = refs_ok and metadata_refs.get("files") == "manifests/files.json"
    refs_ok = refs_ok and metadata_refs.get("tree") == "manifests/tree.json"
    checks["manifest.metadata_refs"] = refs_ok
    if not refs_ok:
        errors.append("manifest.metadata_refs missing required AIFP manifest links")

    if locked:
        final_ok = bool(project.get("finalized_utc")) and "final_label" in project
        checks["manifest.project.finalization"] = final_ok
        if not final_ok:
            errors.append("Final AIFP must include finalized_utc and final_label")
    else:
        if "manifests/diff.json" not in names:
            warnings.append("Working snapshot has no diff manifest; treated as initial snapshot.")

    return checks, errors, warnings
