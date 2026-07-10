"""Publisher tests — fully mocked, no network, no real account."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from khaosclip.config import reset_settings
from khaosclip.publish.x_api import PublishError, XPublisher


def _creds(monkeypatch):
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"):
        monkeypatch.setenv(k, "test-" + k.lower())
    reset_settings()


def _fake_video(tmp_path) -> Path:
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"\x00" * 1024)
    return p


def test_missing_credentials_fail_loud(tmp_path):
    pub = XPublisher()
    with pytest.raises(PublishError, match="Missing X credentials"):
        pub.post_clip(_fake_video(tmp_path))


def test_dry_run_never_touches_network(tmp_path, monkeypatch):
    _creds(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")
    reset_settings()

    session = MagicMock()
    pub = XPublisher(session=session)
    url = pub.post_clip(_fake_video(tmp_path), text="test")
    assert url.startswith("dry-run://")
    session.request.assert_not_called()


def test_happy_path_upload_and_post(tmp_path, monkeypatch):
    _creds(monkeypatch)
    session = MagicMock()

    def respond(method, url, **kw):
        r = MagicMock()
        r.status_code = 200
        data = kw.get("data") or {}
        if kw.get("json") is not None:                      # create post
            r.json.return_value = {"data": {"id": "999"}}
        elif data.get("command") == "INIT":
            r.json.return_value = {"data": {"id": "media-1"}}
        elif data.get("command") == "FINALIZE":
            r.json.return_value = {"data": {"id": "media-1",
                                            "processing_info": {"state": "succeeded"}}}
        else:                                               # APPEND
            r.json.return_value = {"data": {}}
        return r

    session.request.side_effect = respond
    pub = XPublisher(session=session)
    url = pub.post_clip(_fake_video(tmp_path), text="yo")
    assert url == "https://x.com/i/status/999"

    commands = [
        (kw.get("data") or {}).get("command")
        for _, kw in [(c.args, c.kwargs) for c in session.request.call_args_list]
    ]
    assert "INIT" in commands and "APPEND" in commands and "FINALIZE" in commands


def test_transient_500_retries_then_succeeds(tmp_path, monkeypatch):
    _creds(monkeypatch)
    session = MagicMock()
    calls = {"n": 0}

    def flaky(method, url, **kw):
        calls["n"] += 1
        r = MagicMock()
        if calls["n"] == 1:
            r.status_code = 503
            r.text = "unavailable"
            return r
        r.status_code = 200
        data = kw.get("data") or {}
        if kw.get("json") is not None:
            r.json.return_value = {"data": {"id": "42"}}
        elif data.get("command") == "INIT":
            r.json.return_value = {"data": {"id": "m"}}
        elif data.get("command") == "FINALIZE":
            r.json.return_value = {"data": {"id": "m"}}
        else:
            r.json.return_value = {"data": {}}
        return r

    session.request.side_effect = flaky
    monkeypatch.setattr("time.sleep", lambda *_: None)  # no waiting in tests
    pub = XPublisher(session=session)
    url = pub.post_clip(_fake_video(tmp_path))
    assert url.endswith("/42")
    assert calls["n"] > 1
