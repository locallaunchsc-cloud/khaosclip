"""Cloud relay publishing tests — publisher side, relay mocked."""

from unittest.mock import MagicMock

import pytest

from khaosclip.config import reset_settings
from khaosclip.publish.x_api import PublishError, XPublisher


def test_cloud_mode_posts_via_relay(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "true")
    monkeypatch.setenv("NAMEIT_API_KEY", "nameit_testkey")
    monkeypatch.setenv("RELAY_URL", "https://relay.example.com")
    reset_settings()

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\x00" * 512)

    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"url": "https://x.com/i/status/777", "posted_as": "HoodToshi"}
    session.request.return_value = resp

    pub = XPublisher(session=session)
    url = pub.post_clip(clip, text="test caption")
    assert url.endswith("/777")

    # verify it hit the relay endpoint with the bearer key
    call = session.request.call_args
    assert "relay.example.com/api/v1/clips" in call.args[1]
    assert call.kwargs["headers"]["Authorization"] == "Bearer nameit_testkey"


def test_cloud_mode_missing_key_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "true")
    reset_settings()

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    pub = XPublisher(session=MagicMock())
    with pytest.raises(PublishError, match="NAMEIT_API_KEY"):
        pub.post_clip(clip)
