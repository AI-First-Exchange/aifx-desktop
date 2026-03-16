from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

try:
    from platformdirs import user_config_dir
except Exception:
    def user_config_dir(appname: str, appauthor: str) -> str:
        return str((Path.home() / ".config" / appname).expanduser())


class AIFPHistoryStore:
    def __init__(self) -> None:
        self.base_dir = Path(user_config_dir("AIFX", "AI-First-Exchange")).expanduser() / "aifp_history"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "aifp_history_index.json"

    def _load_index(self) -> dict[str, str]:
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def _save_index(self, data: dict[str, str]) -> None:
        self.index_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _project_path(self, project_id: str) -> Path:
        return self.base_dir / f"{project_id}.json"

    def load_for_root(self, root_path: str | Path) -> Optional[dict[str, Any]]:
        root = str(Path(root_path).expanduser().resolve())
        project_id = self._load_index().get(root)
        if not project_id:
            return None
        path = self._project_path(project_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None

    def save_snapshot(
        self,
        *,
        root_path: str | Path,
        scan_result: dict[str, Any],
        export_path: str,
    ) -> None:
        root = str(Path(root_path).expanduser().resolve())
        project = scan_result.get("project", {})
        project_id = str(project.get("project_id", ""))
        if not project_id:
            raise ValueError("scan_result.project.project_id missing")

        index = self._load_index()
        index[root] = project_id
        self._save_index(index)

        existing = self.load_for_root(root) or {"exports": []}
        exports = list(existing.get("exports", []))
        exports.append(
            {
                "snapshot_id": scan_result.get("snapshot", {}).get("snapshot_id", ""),
                "snapshot_kind": scan_result.get("snapshot", {}).get("snapshot_kind", ""),
                "export_path": export_path,
                "created_utc": scan_result.get("snapshot", {}).get("created_utc", ""),
            }
        )
        existing.update(
            {
                "project_id": project_id,
                "root_path": root,
                "last_export_path": export_path,
                "latest": scan_result,
                "exports": exports[-10:],
            }
        )
        self._project_path(project_id).write_text(
            json.dumps(existing, indent=2, sort_keys=True),
            encoding="utf-8",
        )
