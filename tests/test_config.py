import pytest
from pydantic import ValidationError

from khaosclip.config import Settings, get_settings


def test_defaults_are_sane():
    s = Settings(_env_file=None)
    assert s.retro_seconds == 60
    assert s.max_forward_seconds == 90
    assert s.output_width == 1080 and s.output_height == 1920
    assert s.vertical is True
    assert "aye clip that" in s.retro_phrases
    assert "aye clip this" in s.start_phrases


def test_phrases_from_csv_env(monkeypatch):
    monkeypatch.setenv("RETRO_PHRASES", "Yo Clip It, RUN IT BACK")
    s = Settings(_env_file=None)
    assert s.retro_phrases == ["yo clip it", "run it back"]


def test_rejects_clips_over_x_limit():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, retro_seconds=200)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_forward_seconds=200)


def test_missing_credentials_reported():
    s = Settings(_env_file=None, x_api_key="abc")
    assert not s.has_x_credentials()
    missing = s.missing_x_credentials()
    assert "X_API_KEY" not in missing
    assert "X_API_SECRET" in missing


def test_settings_singleton():
    assert get_settings() is get_settings()
