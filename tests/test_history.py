
from khaosclip.history import History


def test_full_clip_lifecycle(tmp_path):
    h = History(tmp_path / "hist.db")
    cid = h.start(source="voice", raw_path="raw.mkv")
    h.mark_processed(cid, "clips/out.mp4", 45.0)
    h.mark_posted(cid, "https://x.com/i/status/123")

    rec = h.recent(1)[0]
    assert rec.status == "posted"
    assert rec.tweet_url.endswith("123")
    h.close()


def test_failure_is_recorded(tmp_path):
    h = History(tmp_path / "hist.db")
    cid = h.start(source="hotkey", raw_path="raw.mkv")
    h.mark_failed(cid, "ffmpeg exploded")
    assert h.recent(1)[0].status == "failed"
    h.close()


def test_recent_ordering(tmp_path):
    h = History(tmp_path / "hist.db")
    first = h.start("voice", "a.mkv")
    second = h.start("voice", "b.mkv")
    recs = h.recent(2)
    assert recs[0].id == second and recs[1].id == first
    h.close()
