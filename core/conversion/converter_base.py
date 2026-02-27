# core/conversion/converter_base.py
from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


class ConversionError(RuntimeError):
    pass


class SymlinkNotAllowedError(ConversionError):
    pass


@dataclass(frozen=True)
class PackageBuild:
    """
    Inputs to the base packager.

    staging_root layout is decided by the caller (e.g. payload/, metadata/ etc).
    Base will:
      - write manifest.json
      - compute integrity hashes (canonical_excludes_self)
      - write final manifest.json (with hashed_files populated)
      - create .aif* zip deterministically (stable order)

    This mirrors your current AIFM alpha behavior exactly.
    """
    format_name: str                   # e.g. "AIFM"
    format_version: str                # e.g. "0.3"
    staging_root: Path                 # temp folder containing files to be packaged
    manifest: Dict[str, Any]           # manifest dict WITHOUT final hashed_files
    out_path: Path                     # target .aifm/.aifv path
    cleanup: bool = True               # delete staging after zip


def sha256_file(p: Path) -> Tuple[str, int]:
    h = sha256()
    size = 0
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def ensure_no_symlinks(root: Path) -> None:
    # v0 rule: reject symlinks outright
    for p in root.rglob("*"):
        try:
            if p.is_symlink():
                raise SymlinkNotAllowedError(f"Symlink not allowed in staging: {p}")
        except OSError:
            raise SymlinkNotAllowedError(f"Cannot verify symlink safety: {p}")


def write_manifest(staging_root: Path, manifest: Dict[str, Any]) -> Path:
    mp = staging_root / "manifest.json"
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return mp


def compute_integrity_canonical_excludes_self(staging_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produces the hashed_files map in the same shape you use today:
      hashed_files[path] = {"sha256": <hex>, "bytes": <int>}

    manifest.json hash is computed as sha256(canonical_json(manifest_with_hashed_files_excluding_manifest_entry))
    """
    hashed: Dict[str, Any] = {}

    # 1) hash all files except manifest.json
    files = sorted([p for p in staging_root.rglob("*") if p.is_file()])
    for p in files:
        rel = str(p.relative_to(staging_root)).replace("\\", "/")
        if rel == "manifest.json":
            continue
        dig, size = sha256_file(p)
        hashed[rel] = {"sha256": dig, "bytes": size}

    # 2) compute canonical manifest hash excluding its own entry
    manifest_for_hash = dict(manifest)
    integrity_for_hash = dict(manifest_for_hash.get("integrity") or {})
    integrity_for_hash["hashed_files"] = dict(hashed)  # no manifest.json entry
    manifest_for_hash["integrity"] = integrity_for_hash

    canonical_bytes = json.dumps(
        manifest_for_hash,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")

    mh = sha256(canonical_bytes).hexdigest()
    hashed["manifest.json"] = {"sha256": mh, "bytes": len(canonical_bytes)}
    return hashed


def write_zip_deterministic(out_path: Path, staging_root: Path) -> None:
    """
    Deterministic-ish zip:
    - stable file iteration order
    - fixed ZipInfo timestamp to avoid per-run differences
    """
    fixed_dt = (1980, 1, 1, 0, 0, 0)

    files = sorted([p for p in staging_root.rglob("*") if p.is_file()])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            arc = str(p.relative_to(staging_root)).replace("\\", "/")
            zi = zipfile.ZipInfo(arc, date_time=fixed_dt)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            with p.open("rb") as f:
                z.writestr(zi, f.read())

    if out_path.exists():
        out_path.unlink()
    tmp.rename(out_path)


def build_package(build: PackageBuild) -> Path:
    staging = build.staging_root

    if not staging.exists() or not staging.is_dir():
        raise ConversionError(f"staging_root does not exist: {staging}")

    ensure_no_symlinks(staging)

    # 1) Write preliminary manifest.json (no hashed_files populated yet)
    manifest_path = write_manifest(staging, build.manifest)

    # 2) Compute integrity map (canonical_excludes_self) and write final manifest
    hashed_files = compute_integrity_canonical_excludes_self(staging, build.manifest)
    final_manifest = dict(build.manifest)
    final_manifest.setdefault("integrity", {})
    final_manifest["integrity"]["hashed_files"] = hashed_files

    manifest_path.write_text(json.dumps(final_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 3) Zip deterministically
    out = build.out_path.expanduser().resolve()
    write_zip_deterministic(out, staging)

    # 4) Cleanup
    if build.cleanup:
        shutil.rmtree(staging, ignore_errors=True)

    return out
