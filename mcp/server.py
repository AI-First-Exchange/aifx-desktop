"""
AIFX / aiRX MCP Server (stdio)
Tier-1 tools: read-only + dry-run only
"""

from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"))

from core.validation.validator import validate_aifx_package, ValidationError

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from fastmcp import FastMCP


# -------------------------------------------------------------------
# Settings (LAZY – resolved at runtime, not import time)
# -------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    aifx_allowed_root: Path
    airx_ingest_root: Path
    airx_nowplaying_path: Path
    audit_log_path: Path
    tier: str


def get_settings() -> Settings:
    return Settings(
        aifx_allowed_root=Path(os.environ.get("AIFX_ALLOWED_ROOT", "/")).resolve(),
        airx_ingest_root=Path(os.environ.get("AIRX_INGEST_ROOT", "/airx/ingest")).resolve(),
        airx_nowplaying_path=Path(os.environ.get("AIRX_NOWPLAYING_PATH", "/airx/nowplaying.json")).resolve(),
        audit_log_path=Path(os.environ.get("MCP_AUDIT_LOG", "/tmp/aifx_mcp_audit.log")).resolve(),
        tier=os.environ.get("MCP_TIER", "internal").lower(),
    )


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

def _audit(tool: str, ok: bool, note: str = "") -> None:
    try:
        S = get_settings()
        rec = {
            "ts": int(time.time()),
            "tool": tool,
            "ok": ok,
            "note": note[:500],
            "tier": S.tier,
        }
        S.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with S.audit_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _safe_resolve(root: Path, user_path: str) -> Path:
    p = Path(user_path).expanduser().resolve()
    if root != Path("/") and root not in p.parents and p != root:
        raise ValueError(f"Path not allowed: {p}")
    if not p.exists():
        raise FileNotFoundError(p)
    return p


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _open_package(path: Path) -> Tuple[str, Any]:
    if path.is_dir():
        return "dir", path
    try:
        zf = zipfile.ZipFile(path)
        zf.namelist()
        return "zip", zf
    except zipfile.BadZipFile:
        raise ValueError("Unsupported package format")


def _read_manifest(kind: str, obj: Any) -> Dict[str, Any]:
    if kind == "dir":
        p = obj / "manifest.json"
        if not p.exists():
            raise FileNotFoundError("manifest.json not found")
        return json.loads(p.read_text())
    else:
        zf: zipfile.ZipFile = obj
        for n in zf.namelist():
            if n.lower().endswith("manifest.json"):
                return json.loads(zf.read(n))
        raise FileNotFoundError("manifest.json not found")


# -------------------------------------------------------------------
# MCP Server
# -------------------------------------------------------------------

mcp = FastMCP(
    name="AIFX + aiRX (MCP)",
    instructions="Read-only MCP tools for AIFX validation and aiRX operations.",
)


# -------------------------------------------------------------------
# TOOLS
# -------------------------------------------------------------------

@mcp.tool(name="aifx.validate_package")
async def validate_package(package_path: str) -> Dict[str, Any]:
    try:
        S = get_settings()

        # Keep your allowlist + existence checks
        pkg = _safe_resolve(S.aifx_allowed_root, package_path)

        # Call canonical validator (single source of truth)
        result = validate_aifx_package(Path(pkg), dry_run=True)

        _audit("aifx.validate_package", True, "PASS" if result.get("valid") else "FAIL")
        return result

    except ValidationError as e:
        _audit("aifx.validate_package", False, str(e))
        return {
            "package": str(package_path),
            "valid": False,
            "errors": [str(e)],
            "warnings": [],
            "checks": {},
            "dry_run": True,
        }

    except Exception as e:
        _audit("aifx.validate_package", False, str(e))
        return {
            "package": str(package_path),
            "valid": False,
            "errors": [str(e)],
            "warnings": [],
            "checks": {},
            "dry_run": True,
        }


@mcp.tool(name="aifx.inspect_manifest")
async def inspect_manifest(package_path: str) -> Dict[str, Any]:
    try:
        S = get_settings()
        pkg = _safe_resolve(S.aifx_allowed_root, package_path)
        kind, obj = _open_package(pkg)
        manifest = _read_manifest(kind, obj)
        _audit("aifx.inspect_manifest", True)
        return {"manifest": manifest}
    except Exception as e:
        _audit("aifx.inspect_manifest", False, str(e))
        return {"error": str(e)}


@mcp.tool(name="aifx.verify_checksums")
async def verify_checksums(package_path: str) -> Dict[str, Any]:
    try:
        S = get_settings()
        pkg = _safe_resolve(S.aifx_allowed_root, package_path)
        kind, obj = _open_package(pkg)
        manifest = _read_manifest(kind, obj)

        declared = manifest.get("checksums", {})
        results = []
        ok = True

        if kind == "dir":
            base: Path = obj
            for rel, expected in declared.items():
                f = base / rel
                actual = _sha256_file(f) if f.exists() else None
                match = actual == expected
                ok &= bool(match)
                results.append({"path": rel, "match": match})
        else:
            zf: zipfile.ZipFile = obj
            for rel, expected in declared.items():
                actual = hashlib.sha256(zf.read(rel)).hexdigest() if rel in zf.namelist() else None
                match = actual == expected
                ok &= bool(match)
                results.append({"path": rel, "match": match})

        _audit("aifx.verify_checksums", True)
        return {"ok": ok, "files": results}

    except Exception as e:
        _audit("aifx.verify_checksums", False, str(e))
        return {"ok": False, "error": str(e)}


@mcp.tool(name="airx.now_playing")
async def now_playing() -> Dict[str, Any]:
    try:
        S = get_settings()
        if S.airx_nowplaying_path.exists():
            data = json.loads(S.airx_nowplaying_path.read_text())
            return {"track": data}
        return {"track": None}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(name="airx.ingest_status")
async def ingest_status() -> Dict[str, Any]:
    S = get_settings()
    root = S.airx_ingest_root

    def count(p: Path) -> int:
        return len([x for x in p.iterdir() if x.is_dir()]) if p.exists() else 0

    return {
        "paths": {
            "ingest_root": str(root),
            "inbox": str(root / "inbox"),
            "quarantine": str(root / "quarantine"),
            "accepted": str(root / "accepted"),
            "rejected": str(root / "rejected"),
        },
        "counts": {
            "inbox": count(root / "inbox"),
            "quarantine": count(root / "quarantine"),
            "accepted": count(root / "accepted"),
            "rejected": count(root / "rejected"),
        },
    }


@mcp.tool(name="airx.quarantine_list")
async def quarantine_list(limit: int = 25) -> Dict[str, Any]:
    S = get_settings()
    qroot = S.airx_ingest_root / "quarantine"
    items = []

    if qroot.exists():
        for d in sorted(qroot.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            sub = d / "submission.json"
            if sub.exists():
                items.append(json.loads(sub.read_text()))
            else:
                items.append({"id": d.name, "reason": "submission.json missing"})

    return {"items": items}


# -------------------------------------------------------------------
# Entrypoint
# -------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

