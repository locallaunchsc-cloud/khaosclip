"""Receipts engine tests — mocked X API, real SQLite."""

from unittest.mock import MagicMock

from khaosclip.config import reset_settings
from khaosclip.history import History
from khaosclip.stats import (
    StatsStore,
    TweetMetrics,
    collect,
    extract_tweet_id,
    receipts_card,
    totals,
)


def test_extract_tweet_id():
    assert extract_tweet_id("https://x.com/i/status/12345") == "12345"
    assert extract_tweet_id("https://x.com/user/status/999?s=20") == "999"
    assert extract_tweet_id("not a url") is None
    assert extract_tweet_id(None) is None


def test_stats_store_roundtrip(tmp_path):
    store = StatsStore(tmp_path / "stats.db")
    m = TweetMetrics("111", impressions=5000, likes=42, reposts=7, replies=3, quotes=1)
    store.record(m)
    latest = store.latest_for("111")
    assert latest.impressions == 5000 and latest.likes == 42
    store.close()


def test_totals_and_card():
    results = [
        ("https://x.com/i/status/1", TweetMetrics("1", 1_500_000, 900, 120, 45, 10)),
        ("https://x.com/i/status/2", TweetMetrics("2", 30_000, 50, 8, 2, 0)),
    ]
    t = totals(results)
    assert t["clips"] == 2
    assert t["impressions"] == 1_530_000

    card = receipts_card(results, handle="@HoodToshi")
    assert "1.5M" in card
    assert "@HoodToshi" in card
    assert "https://x.com/i/status/1" in card  # top clip linked


def test_collect_pulls_from_history(tmp_path, monkeypatch):
    reset_settings()
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"):
        monkeypatch.setenv(k, "test")
    reset_settings()

    # seed history with two posted clips
    h = History(tmp_path / "hist.db")
    c1 = h.start("voice", "a.mkv")
    h.mark_posted(c1, "https://x.com/i/status/101")
    c2 = h.start("voice", "b.mkv")
    h.mark_posted(c2, "https://x.com/i/status/102")
    h.close()

    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [
        {"id": "101", "public_metrics": {"impression_count": 900, "like_count": 10,
                                          "retweet_count": 2, "reply_count": 1, "quote_count": 0}},
        {"id": "102", "public_metrics": {"impression_count": 40_000, "like_count": 300,
                                          "retweet_count": 50, "reply_count": 12, "quote_count": 3}},
    ]}
    session.get.return_value = resp

    results = collect(tmp_path / "hist.db", tmp_path / "stats.db", session=session)
    assert len(results) == 2
    assert results[0][1].impressions == 40_000  # sorted desc by views
