"""Manual share mode tests — clipboard/browser/explorer all faked."""

from unittest.mock import MagicMock, patch

from khaosclip.config import reset_settings
from khaosclip.events import ClipEvent, EventBus
from khaosclip.history import History
from khaosclip.publish.manual import manual_share
from khaosclip.worker import ClipWorker


def test_manual_share_preps_everything(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")

    with patch("khaosclip.publish.manual.copy_to_clipboard", return_value=True) as cb, \
         patch("khaosclip.publish.manual.webbrowser.open") as wb, \
         patch("khaosclip.publish.manual.reveal_in_explorer") as rv:
        status = manual_share(clip, "my caption #test")

    assert status == "manual://prepared"
    cb.assert_called_once_with("my caption #test")
    # intent URL contains the encoded caption
    assert "x.com/intent/post" in wb.call_args.args[0]
    assert "my%20caption" in wb.call_args.args[0]
    rv.assert_called_once()


def test_worker_manual_mode_never_touches_api(tmp_path, monkeypatch):
    monkeypatch.setenv("POST_MODE", "manual")
    monkeypatch.setenv("AI_CAPTIONS", "false")
    reset_settings()

    obs = MagicMock()
    raw = tmp_path / "replay.mkv"
    raw.write_bytes(b"fake")
    obs.save_replay.return_value = raw

    publisher = MagicMock()
    history = History(tmp_path / "h.db")
    w = ClipWorker(EventBus(), obs, publisher=publisher, history=history)

    fake_clip = tmp_path / "out.mp4"
    fake_clip.write_bytes(b"clip")
    with patch("khaosclip.worker.process_clip", return_value=fake_clip), \
         patch("khaosclip.worker.probe_duration", return_value=45.0), \
         patch("khaosclip.publish.manual.copy_to_clipboard", return_value=True), \
         patch("khaosclip.publish.manual.webbrowser.open"), \
         patch("khaosclip.publish.manual.reveal_in_explorer"):
        w.dispatch(ClipEvent(source="voice", mode="retro"))

    publisher.post_clip.assert_not_called()  # zero API calls, zero cost
    assert history.recent(1)[0].status == "posted"
