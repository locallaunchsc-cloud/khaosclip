"""X publisher — API v2 chunked media upload + create post, with retries.

Auth: OAuth 1.0a user context (app key/secret + account access token/secret).
The app needs Read + Write permissions on developer.x.com.

Flow: INIT -> APPEND (4MB chunks) -> FINALIZE -> poll STATUS -> POST.
Transient failures (5xx, network, rate limits) retry with exponential backoff.
A failed post NEVER loses the clip — it's already safe on disk.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests
from requests_oauthlib import OAuth1

from khaosclip.config import get_settings
from khaosclip.log import get_logger

log = get_logger("publish")

UPLOAD_URL = "https://api.x.com/2/media/upload"
TWEET_URL = "https://api.x.com/2/tweets"
CHUNK = 4 * 1024 * 1024
RETRYABLE = {429, 500, 502, 503, 504}


class PublishError(RuntimeError):
    pass


class XPublisher:
    def __init__(self, session: requests.Session | None = None):
        self.http = session or requests.Session()

    # ------------------------------------------------------------ auth
    def _auth(self) -> OAuth1:
        s = get_settings()
        missing = s.missing_x_credentials()
        if missing:
            raise PublishError(
                f"Missing X credentials: {', '.join(missing)}. "
                "Get them at developer.x.com > your app > Keys & Tokens, put them in .env"
            )
        return OAuth1(s.x_api_key, s.x_api_secret, s.x_access_token, s.x_access_secret)

    # ------------------------------------------------------------ retry
    def _request(self, method: str, url: str, **kw) -> requests.Response:
        s = get_settings()
        last: Exception | None = None
        for attempt in range(1, s.post_max_retries + 1):
            try:
                r = self.http.request(method, url, timeout=60, **kw)
                if r.status_code in RETRYABLE:
                    raise PublishError(f"HTTP {r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                return r
            except (requests.RequestException, PublishError) as e:
                last = e
                if attempt < s.post_max_retries:
                    wait = 2 ** attempt
                    log.warning(f"{method} {url.split('/')[-1]} failed (attempt {attempt}), "
                                f"retrying in {wait}s: {e}")
                    time.sleep(wait)
        raise PublishError(f"Gave up after {s.post_max_retries} attempts: {last}")

    # ------------------------------------------------------------ public
    def post_clip(self, video: Path, text: str = "") -> str:
        """Upload the video and post it. Returns the post URL."""
        s = get_settings()
        if s.dry_run:
            log.info(f"[DRY RUN] Would post {video.name}: \"{text}\"")
            return "dry-run://not-posted"

        auth = self._auth()
        media_id = self._upload_video(video, auth)
        return self._create_post(text, media_id, auth)

    # ------------------------------------------------------------ upload
    def _upload_video(self, video: Path, auth: OAuth1) -> str:
        total = video.stat().st_size
        log.info(f"Uploading {video.name} ({total / 1e6:.1f} MB)…")

        r = self._request("POST", UPLOAD_URL, auth=auth, data={
            "command": "INIT",
            "media_type": "video/mp4",
            "total_bytes": total,
            "media_category": "tweet_video",
        })
        media_id = r.json()["data"]["id"]

        with open(video, "rb") as f:
            idx = 0
            while chunk := f.read(CHUNK):
                self._request("POST", UPLOAD_URL, auth=auth,
                              data={"command": "APPEND", "media_id": media_id,
                                    "segment_index": idx},
                              files={"media": chunk})
                idx += 1

        r = self._request("POST", UPLOAD_URL, auth=auth,
                          data={"command": "FINALIZE", "media_id": media_id})
        info = r.json()["data"]

        # Poll X-side processing
        while info.get("processing_info", {}).get("state") in ("pending", "in_progress"):
            wait = info["processing_info"].get("check_after_secs", 3)
            time.sleep(wait)
            r = self._request("GET", UPLOAD_URL, auth=auth,
                              params={"command": "STATUS", "media_id": media_id})
            info = r.json()["data"]

        if info.get("processing_info", {}).get("state") == "failed":
            raise PublishError(f"X media processing failed: {info['processing_info']}")

        return media_id

    # ------------------------------------------------------------ post
    def _create_post(self, text: str, media_id: str, auth: OAuth1) -> str:
        r = self._request("POST", TWEET_URL, auth=auth, json={
            "text": text,
            "media": {"media_ids": [str(media_id)]},
        })
        tweet_id = r.json()["data"]["id"]
        url = f"https://x.com/i/status/{tweet_id}"
        log.info(f"[bold green]LIVE ON X[/bold green] -> {url}")
        return url
