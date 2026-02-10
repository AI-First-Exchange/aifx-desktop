from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json
import zipfile
import hashlib


class ValidationError(Exception):
    pass


def _get_aifx_version(manifest: Dict[str, Any]) -> str:
    aifx = manifest.get("aifx") or {}
    ver = aifx.get("version") or manifest.get("version") or ""
    return str(ver).strip()


def _bool_is_true(v: Any) -> bool:
    # strict boolean, not "true" string
    return v is True


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_manifest_bytes(manifest: dict) -> bytes:
    # Canonical JSON: stable keys, compact separators, UTF-8
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _verify_integrity(z: zipfile.ZipFile, manifest: dict) -> None:
    integrity = (manifest.get("integrity") or {})
    algo = (integrity.get("algorithm") or "").lower()
    hashed_files = integrity.get("hashed_files") or {}
    mode = integrity.get("manifest_hash_mode") or ""

    if not integrity:
        raise ValidationError("manifest.integrity missing")
    if algo != "sha256":
        raise ValidationError(f"Unsupported integrity.algorithm: {algo!r}")
    if not isinstance(hashed_files, dict) or not hashed_files:
        raise ValidationError("integrity.hashed_files missing or empty")

    # Verify every file listed (except manifest.json handled below)
    for relpath, meta in hashed_files.items():
        if not isinstance(meta, dict):
            raise ValidationError(f"integrity.hashed_files[{relpath!r}] is not an object")
        expected = meta.get("sha256")
        if not expected:
            raise ValidationError(f"Missing sha256 for {relpath}")

        if relpath == "manifest.json":
            continue

        try:
            data = z.read(relpath)
        except KeyError:
            raise ValidationError(f"File not found in package: {relpath}")

        actual = _sha256_bytes(data)
        if actual != expected:
            raise ValidationError(f"Hash mismatch for {relpath}: expected {expected}, got {actual}")

    # Verify manifest.json hash
    if "manifest.json" not in hashed_files:
        raise ValidationError("integrity.hashed_files['manifest.json'] missing")

    expected_manifest_hash = (hashed_files["manifest.json"] or {}).get("sha256")
    if not expected_manifest_hash:
        raise ValidationError("integrity.hashed_files['manifest.json'].sha256 missing")

    if mode == "canonical_excludes_self":
        # Canonicalize manifest WITHOUT the manifest.json entry to avoid circular dependency
        m2 = json.loads(json.dumps(manifest))
        hf = (m2.get("integrity") or {}).get("hashed_files") or {}
        if "manifest.json" in hf:
            del hf["manifest.json"]
        canon = _canonical_manifest_bytes(m2)
        actual_manifest_hash = _sha256_bytes(canon)
    else:
        # fallback: hash actual manifest.json bytes in the zip
        data = z.read("manifest.json")
        actual_manifest_hash = _sha256_bytes(data)

    if actual_manifest_hash != expected_manifest_hash:
        raise ValidationError(
            f"Hash mismatch for manifest.json: expected {expected_manifest_hash}, got {actual_manifest_hash}"
        )


def validate_aifx_package(
    package_path: Path,
    *,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Canonical AIFX package validator (structure + integrity).

    All callers (CLI/UI/MCP) should call this function.
    """

    if not package_path.exists():
        raise ValidationError("Package does not exist")

    if not zipfile.is_zipfile(package_path):
        raise ValidationError("Not a valid AIFX archive")

    results: Dict[str, Any] = {
        "package": str(package_path),
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {},
        "dry_run": dry_run,
    }

    try:
        with zipfile.ZipFile(package_path, "r") as z:
            if "manifest.json" not in z.namelist():
                results["valid"] = False
                results["errors"].append("manifest.json missing")
                results["checks"]["manifest"] = "missing"
                return results

            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
            results["checks"]["manifest"] = "ok"

            # --- Basic version ---
            aifx_version = _get_aifx_version(manifest)
            results["checks"]["aifx_version"] = aifx_version or "unknown"

            # --- Author / Creator ---
            author = (manifest.get("author") or "").strip() if isinstance(manifest.get("author"), str) else ""
            creator = manifest.get("creator") or {}
            creator_name = (creator.get("name") or "").strip() if isinstance(creator, dict) else ""
            creator_contact = (creator.get("contact") or "").strip() if isinstance(creator, dict) else ""

            # --- AIFM REQUIRED IDENTITY ---
            work = manifest.get("work") or {}
            title = (work.get("title") or "").strip() if isinstance(work, dict) else ""

            title_ok = bool(title)
            results["checks"]["work.title"] = title_ok
            if not title_ok:
                results["errors"].append("work.title missing (required)")

            author_ok = bool(author or creator_name)
            results["checks"]["author"] = author_ok
            if not author_ok:
                results["errors"].append("author missing (expected 'author' or 'creator.name')")

            # Contact anchor (your canon rule)
            contact_ok = bool(creator_contact)
            results["checks"]["contact"] = contact_ok
            if not contact_ok:
                results["errors"].append("creator.contact missing (email required)")

            # --- AI declaration ---
            ai_generated = manifest.get("ai_generated", None)
            mode = (manifest.get("mode") or "").strip()

            ai_ok = _bool_is_true(ai_generated) or mode in {
                "human-directed-ai",
                "ai-assisted",
                "ai-generated",
            }
            results["checks"]["ai_declared"] = ai_ok
            if not ai_ok:
                results["errors"].append(
                    "ai declaration missing (expected ai_generated:true or mode in {human-directed-ai, ai-assisted, ai-generated})"
                )

            # --- Integrity verification (this is what was missing) ---
            try:
                _verify_integrity(z, manifest)
                results["checks"]["integrity"] = "ok"
            except ValidationError as e:
                results["checks"]["integrity"] = "fail"
                results["errors"].append(str(e))

    except Exception as e:
        results["valid"] = False
        results["checks"]["manifest"] = "failed"
        results["errors"].append(f"manifest: failed ({e})")
        return results

    results["valid"] = len(results["errors"]) == 0
    return results
