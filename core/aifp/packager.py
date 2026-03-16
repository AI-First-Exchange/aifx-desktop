from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from core.conversion.converter_base import PackageBuild, build_package
from core.provenance.sda_templates import AIFX_SDA_001_TEXT

from .models import ProjectScanResult
from .naming import build_output_filename


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_aifp_package(
    *,
    scan_result: ProjectScanResult,
    output_dir: Path,
) -> Path:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    locked = scan_result.snapshot.snapshot_kind == "final"
    out_path = output_dir / build_output_filename(
        scan_result.project.project_name,
        scan_result.snapshot.version_label_raw,
        locked=locked,
    )

    staging_parent = (Path.home() / ".aifx_staging").expanduser()
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix="aifp_",
            dir=str(staging_parent),
        )
    )
    manifests_dir = staging / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    try:
        project_payload = scan_result.project.to_dict()
        snapshot_payload = scan_result.snapshot.to_dict()
        files_payload = [item.to_dict() for item in scan_result.files]
        tree_payload = scan_result.tree
        diff_payload = scan_result.diff.to_dict() if scan_result.diff else None

        _write_json(manifests_dir / "project.json", project_payload)
        _write_json(manifests_dir / "snapshot.json", snapshot_payload)
        _write_json(manifests_dir / "files.json", files_payload)
        _write_json(manifests_dir / "tree.json", tree_payload)
        if diff_payload is not None:
            _write_json(manifests_dir / "diff.json", diff_payload)

        manifest: dict[str, Any] = {
            "aifx_version": "0.1",
            "type": "AIFP",
            "work": {"title": scan_result.project.project_name, "type": "project"},
            "creator": {
                "name": scan_result.project.creator_name,
                "contact": scan_result.project.creator_contact,
            },
            "mode": scan_result.project.mode,
            "ai_generated": True,
            "verification_tier": "SDA",
            "declaration": AIFX_SDA_001_TEXT,
            "project": {
                "project_id": scan_result.project.project_id,
                "status": scan_result.project.status,
                "snapshot_kind": scan_result.snapshot.snapshot_kind,
                "version_label": scan_result.snapshot.version_label_raw,
                "version_slug": scan_result.snapshot.version_label_slug,
                "locked": locked,
                "assets_embedded": False,
                "source_root_name": scan_result.project.project_root_name,
                "source_root_fingerprint": scan_result.snapshot.source_root_fingerprint,
            },
            "metadata_refs": {
                "project": "manifests/project.json",
                "snapshot": "manifests/snapshot.json",
                "files": "manifests/files.json",
                "tree": "manifests/tree.json",
            },
            "integrity": {
                "algorithm": "sha256",
                "manifest_hash_mode": "canonical_excludes_self",
                "hashed_files": {},
            },
        }
        if diff_payload is not None:
            manifest["metadata_refs"]["diff"] = "manifests/diff.json"
        if locked:
            manifest["project"]["finalized_utc"] = scan_result.snapshot.created_utc
            manifest["project"]["final_label"] = scan_result.snapshot.version_label_raw

        build = PackageBuild(
            format_name="AIFP",
            format_version="0.1",
            staging_root=staging,
            manifest=manifest,
            out_path=out_path,
            cleanup=False,
        )
        return build_package(build)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
