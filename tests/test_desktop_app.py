"""Desktop-app tests — OBS auto-detect, wizard .env output, picker logic."""

from pathlib import Path

from khaosclip.config import app_data_dir, env_file_path
from khaosclip.gui.picker import resolve_choice
from khaosclip.gui.wizard import build_env_text
from khaosclip.obs_detect import detect_replay_dir, detect_websocket


# ---------------------------------------------------------------- obs_detect
def _write_obs_config(root: Path, mode: str = "Simple",
                      simple_path: str = r"C:\Users\s\Videos",
                      adv_path: str = r"D:\Recordings", rb: str = "true",
                      profile: str = "Untitled") -> None:
    prof = root / "basic" / "profiles" / profile
    prof.mkdir(parents=True)
    ini = [
        "[Output]", f"Mode={mode}", f"RecRB={rb}",
        "[SimpleOutput]", f"FilePath={simple_path}", f"RecRB={rb}",
        "[AdvOut]", f"RecFilePath={adv_path}",
    ]
    (prof / "basic.ini").write_text("\n".join(ini), encoding="utf-8")


def test_detect_simple_mode(tmp_path: Path):
    _write_obs_config(tmp_path, mode="Simple")
    path, profile, problems = detect_replay_dir(tmp_path)
    assert str(path) == r"C:\Users\s\Videos"
    assert profile == "Untitled"
    assert problems == []


def test_detect_advanced_mode(tmp_path: Path):
    _write_obs_config(tmp_path, mode="Advanced")
    path, _, _ = detect_replay_dir(tmp_path)
    assert str(path) == r"D:\Recordings"


def test_detect_warns_when_replay_buffer_off(tmp_path: Path):
    _write_obs_config(tmp_path, rb="false")
    _, _, problems = detect_replay_dir(tmp_path)
    assert any("Replay Buffer" in p for p in problems)


def test_detect_no_obs_installed(tmp_path: Path):
    path, _, problems = detect_replay_dir(tmp_path / "nothing")
    assert path is None
    assert any("not found" in p for p in problems)


def test_detect_picks_newest_profile(tmp_path: Path):
    import os
    import time
    _write_obs_config(tmp_path, profile="Old", simple_path=r"C:\old")
    old_ini = tmp_path / "basic/profiles/Old/basic.ini"
    past = time.time() - 1000
    os.utime(old_ini, (past, past))
    prof = tmp_path / "basic" / "profiles" / "New"
    prof.mkdir(parents=True)
    (prof / "basic.ini").write_text(
        "[Output]\nMode=Simple\nRecRB=true\n[SimpleOutput]\nFilePath=C:\\new\nRecRB=true",
        encoding="utf-8",
    )
    path, profile, _ = detect_replay_dir(tmp_path)
    assert profile == "New"
    assert str(path) == r"C:\new"


def test_detect_websocket(tmp_path: Path):
    ws = tmp_path / "plugin_config" / "obs-websocket"
    ws.mkdir(parents=True)
    (ws / "config.json").write_text(
        '{"server_port": 4455, "auth_required": true, "server_password": "hunter2"}',
        encoding="utf-8",
    )
    port, password = detect_websocket(tmp_path)
    assert port == 4455
    assert password == "hunter2"


def test_detect_websocket_missing(tmp_path: Path):
    assert detect_websocket(tmp_path) == (None, None)


# ---------------------------------------------------------------- wizard env
def test_wizard_env_contents():
    text = build_env_text(r"C:\Users\s\Videos", 4455, "pw")
    assert "OBS_REPLAY_DIR=C:\\Users\\s\\Videos" in text
    assert "POST_MODE=manual" in text
    assert "GUI_MODE=true" in text
    assert "OBS_WS_PORT=4455" in text
    assert "OBS_WS_PASSWORD=pw" in text


def test_wizard_env_skips_missing_websocket():
    text = build_env_text(r"C:\v", None, None)
    assert "OBS_WS_PORT" not in text
    assert "OBS_WS_PASSWORD" not in text


# ---------------------------------------------------------------- picker logic
CAPS = ["caption one", "caption two", "caption three"]


def test_picker_timeout_auto_picks_first():
    assert resolve_choice(None, CAPS, "default") == "caption one"


def test_picker_numeric_choice():
    assert resolve_choice("2", CAPS, "default") == "caption two"


def test_picker_skip_uses_default():
    assert resolve_choice("skip", CAPS, "default") == "default"


def test_picker_custom_text_passthrough():
    assert resolve_choice("my own caption", CAPS, "d") == "my own caption"


def test_picker_empty_captions_falls_to_default():
    assert resolve_choice(None, [], "default") == "default"


def test_picker_out_of_range_choice():
    assert resolve_choice("3", ["only one"], "d") == "only one"


# ---------------------------------------------------------------- env paths
def test_env_path_dev_mode_is_local():
    assert env_file_path() == Path(".env")


def test_env_path_frozen_uses_appdata(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert env_file_path() == app_data_dir() / ".env"
