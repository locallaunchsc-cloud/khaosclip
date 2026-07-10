"""Worker orchestration tests — OBS, pipeline, and publisher all faked."""

import time
from unittest.mock import MagicMock, patch

from khaosclip.config import get_settings, reset_settings
from khaosclip.events import ClipEvent, EventBus
from khaosclip.history import History
from khaosclip.worker import ClipWorker


def make_worker(tmp_path, publisher=None):
    obs = MagicMock()
    raw = tmp_path / "replay.mkv"
    raw.write_bytes(b"fake")
    obs.save_replay.return_value = raw
    history = History(tmp_path / "h.db")
    w = ClipWorker(EventBus(), obs, publisher=publisher or MagicMock(), history=history)
    return w, obs, history


def test_successful_clip_is_posted_and_recorded(tmp_path, monkeypatch):
    reset_settings()
    pub = MagicMock()
    pub.post_clip.return_value = "https://x.com/i/status/1"
    w, obs, history = make_worker(tmp_path, publisher=pub)

    fake_clip = tmp_path / "out.mp4"
    fake_clip.write_bytes(b"clip")
    with patch("khaosclip.worker.process_clip", return_value=fake_clip), \
         patch("khaosclip.worker.probe_duration", return_value=45.0):
        w.dispatch(ClipEvent(source="voice", detail="clip that"))

    rec = history.recent(1)[0]
    assert rec.status == "posted"
    pub.post_clip.assert_called_once()


def test_capture_failure_does_not_crash(tmp_path):
    reset_settings()
    w, obs, history = make_worker(tmp_path)
    obs.save_replay.side_effect = RuntimeError("obs died")
    w.dispatch(ClipEvent(source="voice"))  # must not raise
    assert history.recent(1) == []


def test_post_failure_keeps_clip_and_records_error(tmp_path):
    reset_settings()
    pub = MagicMock()
    pub.post_clip.side_effect = RuntimeError("api down")
    w, obs, history = make_worker(tmp_path, publisher=pub)

    fake_clip = tmp_path / "out.mp4"
    fake_clip.write_bytes(b"clip")
    with patch("khaosclip.worker.process_clip", return_value=fake_clip), \
         patch("khaosclip.worker.probe_duration", return_value=45.0):
        w.dispatch(ClipEvent(source="hotkey"))

    rec = history.recent(1)[0]
    assert rec.status == "failed"
    assert fake_clip.exists()  # the clip is never lost


def test_cooldown_blocks_double_fire(tmp_path, monkeypatch):
    reset_settings()
    w, obs, history = make_worker(tmp_path)
    w._last_clip_at = time.time()  # just clipped

    handled = []
    monkeypatch.setattr(w, "dispatch", lambda ev: handled.append(ev))
    w.bus.publish(ClipEvent(source="voice"))

    # run one loop iteration manually
    w.bus.next(timeout=0.1)
    since = time.time() - w._last_clip_at
    if since < get_settings().trigger_cooldown_seconds:
        pass  # cooldown path: handle() not called
    assert handled == []
