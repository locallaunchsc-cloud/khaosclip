"""Wake-word engine tests — discovery, scoring, and engine selection."""

from pathlib import Path

from khaosclip.config import get_settings
from khaosclip.events import EventBus
from khaosclip.triggers.wakeword import (
    DEFAULT_MODE_MAP,
    discover_models,
    make_voice_trigger,
    score_hits,
)


# ---------------------------------------------------------------- discovery
def test_discover_maps_default_stems(tmp_path: Path):
    for stem in ("aye_clip_that", "aye_clip_this", "aye_end_clip"):
        (tmp_path / f"{stem}.onnx").touch()
    found = discover_models(tmp_path)
    modes = {Path(p).stem: m for p, m in found.items()}
    assert modes == {
        "aye_clip_that": "retro",
        "aye_clip_this": "start",
        "aye_end_clip": "end",
    }


def test_discover_skips_unmapped_stems(tmp_path: Path):
    (tmp_path / "random_phrase.onnx").touch()
    (tmp_path / "aye_clip_that.onnx").touch()
    found = discover_models(tmp_path)
    assert len(found) == 1
    assert Path(next(iter(found))).stem == "aye_clip_that"


def test_discover_custom_mode_map(tmp_path: Path):
    (tmp_path / "lets_ride.onnx").touch()
    found = discover_models(tmp_path, {"lets_ride": "retro"})
    assert list(found.values()) == ["retro"]


def test_discover_ignores_non_model_files(tmp_path: Path):
    (tmp_path / "readme.txt").touch()
    (tmp_path / "aye_clip_that.tflite").touch()
    found = discover_models(tmp_path)
    assert len(found) == 1


def test_discover_missing_dir_is_empty(tmp_path: Path):
    assert discover_models(tmp_path / "nope") == {}


# ---------------------------------------------------------------- scoring
STEMS = {"aye_clip_that": "retro", "aye_clip_this": "start", "aye_end_clip": "end"}


def test_score_below_threshold_no_hit():
    assert score_hits({"aye_clip_that": 0.3}, STEMS, threshold=0.5) is None


def test_score_over_threshold_hits():
    hit = score_hits({"aye_clip_that": 0.9}, STEMS, threshold=0.5)
    assert hit == ("retro", "aye_clip_that", 0.9)


def test_score_highest_wins():
    scores = {"aye_clip_that": 0.6, "aye_clip_this": 0.95}
    hit = score_hits(scores, STEMS, threshold=0.5)
    assert hit is not None and hit[0] == "start"


def test_score_tie_prefers_end_over_retro():
    scores = {"aye_clip_that": 0.8, "aye_end_clip": 0.8}
    hit = score_hits(scores, STEMS, threshold=0.5)
    assert hit is not None and hit[0] == "end"


def test_score_unknown_stem_ignored():
    assert score_hits({"mystery": 0.99}, STEMS, threshold=0.5) is None


# ---------------------------------------------------------------- engine selection
def test_auto_falls_back_to_vosk_without_models(tmp_path: Path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "voice_engine", "auto")
    monkeypatch.setattr(s, "oww_model_dir", tmp_path / "empty")
    trig = make_voice_trigger(EventBus())
    assert trig.name == "voice"


def test_auto_picks_wakeword_when_models_exist(tmp_path: Path, monkeypatch):
    (tmp_path / "aye_clip_that.onnx").touch()
    s = get_settings()
    monkeypatch.setattr(s, "voice_engine", "auto")
    monkeypatch.setattr(s, "oww_model_dir", tmp_path)
    trig = make_voice_trigger(EventBus())
    assert trig.name == "wakeword"


def test_explicit_engine_forced(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "voice_engine", "vosk")
    assert make_voice_trigger(EventBus()).name == "voice"
    monkeypatch.setattr(s, "voice_engine", "openwakeword")
    assert make_voice_trigger(EventBus()).name == "wakeword"


# ---------------------------------------------------------------- config parsing
def test_mode_map_env_string_parsing():
    from khaosclip.config import Settings
    parsed = Settings._parse_mode_map("lets_ride:retro, cut_it:end")
    assert parsed == {"lets_ride": "retro", "cut_it": "end"}


def test_default_mode_map_covers_all_commands():
    assert set(DEFAULT_MODE_MAP.values()) == {"retro", "start", "end"}
