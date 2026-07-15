"""Auto-detect OBS settings from its own config files.

OBS Studio keeps per-profile INI files at:
  Windows: %APPDATA%/obs-studio/basic/profiles/<Profile>/basic.ini
  macOS:   ~/Library/Application Support/obs-studio/...
  Linux:   ~/.config/obs-studio/...

We read them (read-only, OBS doesn't need to be running) to find:
  - the recording/replay output folder  -> OBS_REPLAY_DIR
  - the websocket port/password         -> OBS_WS_PORT / OBS_WS_PASSWORD

so the setup wizard can fill in .env with zero typing.
"""

from __future__ import annotations

import configparser
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OBSInfo:
    replay_dir: Path | None = None
    ws_port: int | None = None
    ws_password: str | None = None
    profile: str = ""
    problems: list[str] = field(default_factory=list)


def obs_config_root() -> Path:
    """Platform-specific OBS config directory."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "obs-studio"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/obs-studio"
    return Path.home() / ".config/obs-studio"


def _read_ini(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    # OBS writes UTF-8, sometimes with BOM
    cp.read(path, encoding="utf-8-sig")
    return cp


def _newest_profile(profiles_dir: Path) -> Path | None:
    """Most recently modified profile — almost always the active one."""
    candidates = [d for d in profiles_dir.iterdir() if (d / "basic.ini").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda d: (d / "basic.ini").stat().st_mtime)


def detect_replay_dir(root: Path | None = None) -> tuple[Path | None, str, list[str]]:
    """Return (replay_dir, profile_name, problems)."""
    root = root or obs_config_root()
    problems: list[str] = []

    profiles_dir = root / "basic" / "profiles"
    if not profiles_dir.exists():
        problems.append("OBS config not found — is OBS Studio installed?")
        return None, "", problems

    profile = _newest_profile(profiles_dir)
    if profile is None:
        problems.append("No OBS profiles found.")
        return None, "", problems

    cp = _read_ini(profile / "basic.ini")

    # Advanced output mode uses [AdvOut] RecFilePath; Simple uses [SimpleOutput] FilePath.
    mode = cp.get("Output", "Mode", fallback="Simple")
    if mode.lower() == "advanced":
        raw = cp.get("AdvOut", "RecFilePath", fallback="")
    else:
        raw = cp.get("SimpleOutput", "FilePath", fallback="")

    if not raw:
        raw = str(Path.home() / "Videos")
        problems.append("Recording folder not set in OBS — assuming ~/Videos.")

    # Replay buffer enabled?
    rb = cp.get("Output", "RecRB", fallback=cp.get("SimpleOutput", "RecRB", fallback="false"))
    if str(rb).lower() != "true":
        problems.append(
            "Replay Buffer looks disabled in OBS. Enable it: "
            "Settings > Output > Replay Buffer, then Start Replay Buffer."
        )

    return Path(raw), profile.name, problems


def detect_websocket(root: Path | None = None) -> tuple[int | None, str | None]:
    """Return (port, password) from OBS websocket config, if present."""
    root = root or obs_config_root()
    cfg = root / "plugin_config" / "obs-websocket" / "config.json"
    if not cfg.exists():
        return None, None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None, None
    port = data.get("server_port")
    password = data.get("server_password") if data.get("auth_required") else ""
    return port, password


def detect() -> OBSInfo:
    """One call the wizard uses: everything we can learn about their OBS."""
    info = OBSInfo()
    info.replay_dir, info.profile, info.problems = detect_replay_dir()
    info.ws_port, info.ws_password = detect_websocket()
    return info
