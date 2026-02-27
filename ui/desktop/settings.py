from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from platformdirs import user_config_dir


def default_downloads_dir() -> Path:
    return (Path.home() / "Downloads").expanduser().resolve()


def _config_path() -> Path:
    cfg_dir = Path(user_config_dir("AIFX", "AI-First-Exchange")).expanduser()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "desktop_settings.json"


@dataclass
class DesktopSettings:
    # New defaults (anchor fields)
    creator_name: str = ""
    creator_email: str = ""

    # Existing defaults
    default_mode: str = "human-directed-ai"
    default_output_dir: str = ""

    # Legacy / compatibility (keep so old settings files load)
    last_input_dir: str = ""
    open_folder_after_export: bool = False
    overwrite: bool = False


class SettingsStore:
    def __init__(self) -> None:
        self.path = _config_path()

    def load(self) -> DesktopSettings:
        d = default_downloads_dir()
        home = Path.home().resolve()

        if not self.path.exists():
            return DesktopSettings(
                default_output_dir=str(d),
                last_input_dir=str(home),
            )

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))

            return DesktopSettings(
                creator_name=str(data.get("creator_name", "")),
                creator_email=str(data.get("creator_email", "")),
                default_mode=str(data.get("default_mode", "human-directed-ai")),
                default_output_dir=str(Path(data.get("default_output_dir", str(d))).expanduser().resolve()),
                last_input_dir=str(Path(data.get("last_input_dir", str(home))).expanduser().resolve()),
                open_folder_after_export=bool(data.get("open_folder_after_export", False)),
                overwrite=bool(data.get("overwrite", False)),
            )
        except Exception:
            # Fail safe if settings get corrupted
            return DesktopSettings(
                default_output_dir=str(d),
                last_input_dir=str(home),
            )

    def save(self, s: DesktopSettings) -> None:
        self.path.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
