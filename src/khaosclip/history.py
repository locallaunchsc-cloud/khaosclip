"""Clip history — every clip ever made, in SQLite.

Powers `khaosclip history`, dedupe/cooldown decisions, and eventually the
analytics dashboard (clips -> views -> which moments actually ran).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    source TEXT NOT NULL,
    raw_path TEXT,
    clip_path TEXT,
    duration_s REAL,
    status TEXT NOT NULL,          -- processed | posted | failed
    tweet_url TEXT,
    error TEXT
);
"""


@dataclass
class ClipRecord:
    id: int
    created_at: float
    source: str
    clip_path: str | None
    status: str
    tweet_url: str | None


class History:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def start(self, source: str, raw_path: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO clips (created_at, source, raw_path, status) VALUES (?, ?, ?, 'processed')",
            (time.time(), source, raw_path),
        )
        self._conn.commit()
        return cur.lastrowid

    def mark_processed(self, clip_id: int, clip_path: str, duration_s: float) -> None:
        self._conn.execute(
            "UPDATE clips SET clip_path=?, duration_s=? WHERE id=?",
            (clip_path, duration_s, clip_id),
        )
        self._conn.commit()

    def mark_posted(self, clip_id: int, tweet_url: str) -> None:
        self._conn.execute(
            "UPDATE clips SET status='posted', tweet_url=? WHERE id=?", (tweet_url, clip_id)
        )
        self._conn.commit()

    def mark_failed(self, clip_id: int, error: str) -> None:
        self._conn.execute(
            "UPDATE clips SET status='failed', error=? WHERE id=?", (error[:500], clip_id)
        )
        self._conn.commit()

    def recent(self, limit: int = 20) -> list[ClipRecord]:
        rows = self._conn.execute(
            "SELECT id, created_at, source, clip_path, status, tweet_url "
            "FROM clips ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [ClipRecord(*r) for r in rows]

    def close(self) -> None:
        self._conn.close()
