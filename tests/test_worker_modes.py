"""Forward/retro state machine tests — OBS, pipeline, publisher all faked."""

import time
from unittest.mock import MagicMock, patch

from khaosclip.config import reset_settings
from khaosclip.events import ClipEvent, EventBus
from khaosclip.history import History
from khaosclip.worker import ClipWorker


def make_worker(tmp_path):
    reset_settings()
    obs = MagicMock()
    raw = tmp_path / "replay.mkv"
    raw.write_bytes(b"fake")
    obs.save_replay.return_value = raw
    pub = MagicMock()
    pub.post_clip.return_value = "https://x.com/i/status/1"
    w = ClipWorker(EventBus(), obs, publisher=pub, history=History(tmp_path / "h.db"))
    return w


def patched_pipeline(tmp_path):
    fake_clip = tmp_path / "out.mp4"
    fake_clip.write_bytes(b"clip")
    return (
        patch("khaosclip.worker.process_clip", return_value=fake_clip),
        patch("khaosclip.worker.probe_duration", return_value=45.0),
    )


def test_retro_uses_retro_seconds(tmp_path):
    w = make_worker(tmp_path)
    p1, p2 = patched_pipeline(tmp_path)
    with p1 as proc, p2:
        w.dispatch(ClipEvent(source="voice", mode="retro"))
    assert proc.call_args.kwargs["keep_seconds"] == 60  # default retro_seconds


def test_forward_clip_open_then_close(tmp_path, monkeypatch):
    w = make_worker(tmp_path)
    w.dispatch(ClipEvent(source="voice", mode="start"))
    assert w._forward_started_at is not None

    # pretend 30s of stream happened
    w._forward_started_at = time.time() - 30

    p1, p2 = patched_pipeline(tmp_path)
    with p1 as proc, p2:
        w.dispatch(ClipEvent(source="voice", mode="end"))
    assert w._forward_started_at is None
    assert 29 <= proc.call_args.kwargs["keep_seconds"] <= 32


def test_retro_phrase_closes_open_forward_clip(tmp_path):
    """'aye clip that' while a clip is open means CLOSE IT, not retro."""
    w = make_worker(tmp_path)
    w.dispatch(ClipEvent(source="voice", mode="start"))
    w._forward_started_at = time.time() - 20

    p1, p2 = patched_pipeline(tmp_path)
    with p1 as proc, p2:
        w.dispatch(ClipEvent(source="voice", mode="retro"))
    assert w._forward_started_at is None
    assert proc.call_args.kwargs["keep_seconds"] < 25  # window, not full 60


def test_forward_autocloses_at_max(tmp_path):
    w = make_worker(tmp_path)
    w.dispatch(ClipEvent(source="voice", mode="start"))
    w._forward_started_at = time.time() - 999  # way past max

    p1, p2 = patched_pipeline(tmp_path)
    with p1 as proc, p2:
        w._maybe_autoclose()
    assert w._forward_started_at is None
    assert proc.call_args.kwargs["keep_seconds"] == 90  # capped at max_forward_seconds


def test_end_with_nothing_open_is_noop(tmp_path):
    w = make_worker(tmp_path)
    w.dispatch(ClipEvent(source="voice", mode="end"))  # must not raise
    assert w.history.recent(1) == []


def test_double_start_ignored(tmp_path):
    w = make_worker(tmp_path)
    w.dispatch(ClipEvent(source="voice", mode="start"))
    first = w._forward_started_at
    w.dispatch(ClipEvent(source="voice", mode="start"))
    assert w._forward_started_at == first


def test_hotkey_auto_mode(tmp_path):
    w = make_worker(tmp_path)
    # nothing open -> retro
    p1, p2 = patched_pipeline(tmp_path)
    with p1 as proc, p2:
        w.dispatch(ClipEvent(source="hotkey", mode="auto"))
    assert proc.call_args.kwargs["keep_seconds"] == 60

    # open -> same key closes it
    w._last_clip_at = 0  # bypass cooldown
    w.dispatch(ClipEvent(source="hotkey", mode="start"))
    w._forward_started_at = time.time() - 10
    with p1 as proc, p2:
        w.dispatch(ClipEvent(source="hotkey", mode="auto"))
    assert w._forward_started_at is None
