"""Receipts engine — tracks the performance of every clip NameiT posts.

Streamers don't buy tools, they buy view counts. This module:
  1. Pulls tweet IDs from history.db (every clip NameiT ever posted)
  2. Fetches live metrics from X API v2 (impressions, likes, reposts, replies)
  3. Stores snapshots so growth over time is visible
  4. Renders the receipts: a stats table and a shareable text card

CLI: `khaosclip stats` and `khaosclip stats --card`
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from requests_oauthlib import OAuth1

from khaosclip.config import get_settings
from khaosclip.log import get_logger

log = get_logger("stats")

TWEETS_URL = "https://api.x.com/2/tweets"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    impressions INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    reposts INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    quotes INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_metrics_tweet ON metrics (tweet_id, fetched_at);
"""


@dataclass
class TweetMetrics:
    tweet_id: str
    impressions: int
    likes: int
    reposts: int
    replies: int
    quotes: int


def extract_tweet_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url or "")
    return m.group(1) if m else None


class StatsStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(self, m: TweetMetrics) -> None:
        self._conn.execute(
            "INSERT INTO metrics (tweet_id, fetched_at, impressions, likes, reposts, replies, quotes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (m.tweet_id, time.time(), m.impressions, m.likes, m.reposts, m.replies, m.quotes),
        )
        self._conn.commit()

    def latest_for(self, tweet_id: str) -> TweetMetrics | None:
        row = self._conn.execute(
            "SELECT tweet_id, impressions, likes, reposts, replies, quotes FROM metrics "
            "WHERE tweet_id=? ORDER BY fetched_at DESC LIMIT 1",
            (tweet_id,),
        ).fetchone()
        return TweetMetrics(*row) if row else None

    def close(self) -> None:
        self._conn.close()


def fetch_metrics(tweet_ids: list[str], session: requests.Session | None = None) -> list[TweetMetrics]:
    """Fetch public metrics for up to 100 tweets per call from X API v2."""
    s = get_settings()
    if not s.has_x_credentials():
        raise RuntimeError("X credentials missing — can't fetch metrics. Run: khaosclip doctor")
    if not tweet_ids:
        return []

    auth = OAuth1(s.x_api_key, s.x_api_secret, s.x_access_token, s.x_access_secret)
    http = session or requests.Session()
    out: list[TweetMetrics] = []

    for i in range(0, len(tweet_ids), 100):
        batch = tweet_ids[i:i + 100]
        r = http.get(
            TWEETS_URL,
            auth=auth,
            params={"ids": ",".join(batch), "tweet.fields": "public_metrics"},
            timeout=30,
        )
        r.raise_for_status()
        for t in r.json().get("data", []):
            pm = t.get("public_metrics", {})
            out.append(TweetMetrics(
                tweet_id=t["id"],
                impressions=pm.get("impression_count", 0),
                likes=pm.get("like_count", 0),
                reposts=pm.get("retweet_count", 0),
                replies=pm.get("reply_count", 0),
                quotes=pm.get("quote_count", 0),
            ))
    return out


def collect(history_db: Path, stats_db: Path,
            session: requests.Session | None = None) -> list[tuple[str, TweetMetrics]]:
    """Refresh metrics for every posted clip. Returns [(tweet_url, metrics)]."""
    conn = sqlite3.connect(history_db)
    rows = conn.execute(
        "SELECT tweet_url FROM clips WHERE status='posted' AND tweet_url IS NOT NULL"
    ).fetchall()
    conn.close()

    url_by_id = {}
    for (url,) in rows:
        tid = extract_tweet_id(url)
        if tid:
            url_by_id[tid] = url

    if not url_by_id:
        return []

    store = StatsStore(stats_db)
    fresh = fetch_metrics(list(url_by_id.keys()), session=session)
    results = []
    for m in fresh:
        store.record(m)
        results.append((url_by_id[m.tweet_id], m))
    store.close()
    return sorted(results, key=lambda x: x[1].impressions, reverse=True)


def totals(results: list[tuple[str, TweetMetrics]]) -> dict:
    return {
        "clips": len(results),
        "impressions": sum(m.impressions for _, m in results),
        "likes": sum(m.likes for _, m in results),
        "reposts": sum(m.reposts for _, m in results),
        "replies": sum(m.replies for _, m in results),
    }


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def receipts_card(results: list[tuple[str, TweetMetrics]], handle: str = "") -> str:
    """A shareable text block — the weekly flex post."""
    t = totals(results)
    top = results[0] if results else None
    lines = [
        "🧾 NameiT receipts" + (f" — {handle}" if handle else ""),
        "",
        f"clips auto-posted: {t['clips']}",
        f"total views: {_fmt(t['impressions'])}",
        f"likes: {_fmt(t['likes'])} · reposts: {_fmt(t['reposts'])} · replies: {_fmt(t['replies'])}",
    ]
    if top:
        lines += ["", f"top clip: {_fmt(top[1].impressions)} views", top[0]]
    lines += ["", 'all clipped by voice, mid-stream. "aye clip that."']
    return "\n".join(lines)
