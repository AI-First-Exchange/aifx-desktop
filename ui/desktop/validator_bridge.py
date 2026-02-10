from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict


def _ensure_repo_root_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]  # aifx/
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _normalize_result(package_path: Path, raw: Any) -> Dict[str, Any]:
    """
    Normalize any validator output into the exact dict shape the UI expects.
    """
    result: Dict[str, Any] = {
        "package": str(package_path),
        "valid": False,
        "errors": [],
        "warnings": [],
        "checks": {},
        "dry_run": True,
    }

    def _to_list(x: Any) -> list:
        if x is None:
            return []
        if isinstance(x, list):
            return x
        return [x]

    if isinstance(raw, dict):
        result["package"] = raw.get("package", result["package"])
        result["valid"] = bool(raw.get("valid", False))
        result["errors"] = _to_list(raw.get("errors"))
        result["warnings"] = _to_list(raw.get("warnings"))
        result["checks"] = dict(raw.get("checks", {}))
        result["dry_run"] = bool(raw.get("dry_run", True))

    return result


def validate_package_local(package_path: str) -> Dict[str, Any]:
    _ensure_repo_root_on_path()

    p = Path(package_path).expanduser().resolve()

    if not p.exists():
        return _normalize_result(p, {"errors": [f"File not found: {p}"], "valid": False})

    if p.is_dir():
        return _normalize_result(p, {"errors": [f"Expected a file, got a folder: {p}"], "valid": False})

    try:
        from core.validation.validator import validate_aifx_package
        raw = validate_aifx_package(p, dry_run=True)
        return _normalize_result(p, raw)
    except Exception as e:
        return _normalize_result(
            p,
            {"errors": [f"Local validator import/call failed: {e}"], "valid": False},
        )

