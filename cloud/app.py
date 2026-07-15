"""NameiT Cloud Relay — the hosted posting layer.

WHY THIS EXISTS
Local-only NameiT requires every streamer to create their own X developer
account and API keys. That kills 95% of signups. The relay fixes it:

  1. Streamer visits the relay once, clicks "Connect X" (OAuth 2.0 PKCE)
  2. Relay stores their tokens and hands them a NAMEIT_API_KEY
  3. Their local agent sets CLOUD_MODE=true + the key in .env
  4. Every clip now uploads to the relay, which posts to X *as them*
     using the ONE NameiT developer app

Streamer setup drops from "make an X developer account" (30+ min, most quit)
to "click Connect, paste one key" (60 seconds).

ENDPOINTS
  GET  /auth/login           -> redirect to X OAuth (PKCE)
  GET  /auth/callback        -> exchange code, store tokens, show API key
  POST /api/v1/clips         -> multipart clip + caption, posts to X, returns URL
  GET  /api/v1/me            -> validates an API key
  GET  /health               -> deploy checks

DEPLOY: Railway / Fly.io / Render (needs a persistent disk or Postgres for
tokens — see cloud/README.md). Set env: X_CLIENT_ID, X_CLIENT_SECRET,
RELAY_BASE_URL, RELAY_SECRET.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sqlite3
import time
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

# ---------------------------------------------------------------- config
X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")
RELAY_BASE_URL = os.environ.get("RELAY_BASE_URL", "http://localhost:8000")
DB_PATH = Path(os.environ.get("RELAY_DB", "relay.db"))

AUTH_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
UPLOAD_URL = "https://api.x.com/2/media/upload"
TWEET_URL = "https://api.x.com/2/tweets"
SCOPES = "tweet.read tweet.write users.read media.write offline.access"

app = FastAPI(title="NameiT Cloud Relay", version="0.1.0")

# ---------------------------------------------------------------- storage
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        api_key TEXT PRIMARY KEY,
        x_user_id TEXT,
        x_username TEXT,
        access_token TEXT,
        refresh_token TEXT,
        expires_at REAL,
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS oauth_state (
        state TEXT PRIMARY KEY,
        verifier TEXT,
        created_at REAL
    );
    """)
    return conn


# ---------------------------------------------------------------- oauth
@app.get("/auth/login")
def auth_login():
    if not X_CLIENT_ID:
        raise HTTPException(500, "Relay not configured: X_CLIENT_ID missing")
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    conn = db()
    conn.execute("INSERT INTO oauth_state VALUES (?, ?, ?)", (state, verifier, time.time()))
    conn.commit(); conn.close()

    url = (f"{AUTH_URL}?response_type=code&client_id={X_CLIENT_ID}"
           f"&redirect_uri={RELAY_BASE_URL}/auth/callback"
           f"&scope={SCOPES.replace(' ', '%20')}"
           f"&state={state}&code_challenge={challenge}&code_challenge_method=S256")
    return RedirectResponse(url)


@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    conn = db()
    row = conn.execute("SELECT verifier FROM oauth_state WHERE state=?", (state,)).fetchone()
    if not row:
        raise HTTPException(400, "Bad state — restart login")
    verifier = row[0]
    conn.execute("DELETE FROM oauth_state WHERE state=?", (state,))

    async with httpx.AsyncClient() as http:
        r = await http.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": X_CLIENT_ID,
            "redirect_uri": f"{RELAY_BASE_URL}/auth/callback",
            "code_verifier": verifier,
        }, auth=(X_CLIENT_ID, X_CLIENT_SECRET))
        r.raise_for_status()
        tok = r.json()

        me = await http.get("https://api.x.com/2/users/me",
                            headers={"Authorization": f"Bearer {tok['access_token']}"})
        me.raise_for_status()
        user = me.json()["data"]

    api_key = "nameit_" + secrets.token_urlsafe(32)
    conn.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
        (api_key, user["id"], user["username"], tok["access_token"],
         tok.get("refresh_token", ""), time.time() + tok.get("expires_in", 7200), time.time()),
    )
    conn.commit(); conn.close()

    return HTMLResponse(f"""
    <body style="font-family:monospace;background:#0C0F16;color:#EDEFF4;padding:60px;text-align:center">
      <h1>Name<span style="color:#FF3B30">iT</span> connected ✓</h1>
      <p>Posting as <b>@{user['username']}</b></p>
      <p>Put these two lines in your local <code>.env</code>:</p>
      <pre style="background:#121722;padding:20px;border-radius:8px;display:inline-block;text-align:left">
CLOUD_MODE=true
NAMEIT_API_KEY={api_key}</pre>
      <p style="color:#8A93A6">Keep this key private — it can post as you.</p>
    </body>""")


# ---------------------------------------------------------------- auth dep
async def current_user(authorization: str = Header("")) -> dict:
    key = authorization.removeprefix("Bearer ").strip()
    if not key:
        raise HTTPException(401, "Missing API key")
    conn = db()
    row = conn.execute(
        "SELECT api_key, x_user_id, x_username, access_token, refresh_token, expires_at "
        "FROM users WHERE api_key=?", (key,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "Unknown API key")
    user = dict(zip(
        ["api_key", "x_user_id", "x_username", "access_token", "refresh_token", "expires_at"], row
    ))
    if time.time() > user["expires_at"] - 60:
        user = await refresh_tokens(user)
    return user


async def refresh_tokens(user: dict) -> dict:
    async with httpx.AsyncClient() as http:
        r = await http.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": user["refresh_token"],
            "client_id": X_CLIENT_ID,
        }, auth=(X_CLIENT_ID, X_CLIENT_SECRET))
        r.raise_for_status()
        tok = r.json()
    user["access_token"] = tok["access_token"]
    user["refresh_token"] = tok.get("refresh_token", user["refresh_token"])
    user["expires_at"] = time.time() + tok.get("expires_in", 7200)
    conn = db()
    conn.execute("UPDATE users SET access_token=?, refresh_token=?, expires_at=? WHERE api_key=?",
                 (user["access_token"], user["refresh_token"], user["expires_at"], user["api_key"]))
    conn.commit(); conn.close()
    return user


# ---------------------------------------------------------------- posting
CHUNK = 4 * 1024 * 1024


@app.post("/api/v1/clips")
async def post_clip(user: dict = Depends(current_user),
                    video: UploadFile = File(...),
                    caption: str = Form("")):
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    data = await video.read()

    async with httpx.AsyncClient(timeout=120) as http:
        r = await http.post(UPLOAD_URL, headers=headers, data={
            "command": "INIT", "media_type": "video/mp4",
            "total_bytes": len(data), "media_category": "tweet_video",
        })
        r.raise_for_status()
        media_id = r.json()["data"]["id"]

        for idx in range(0, len(data), CHUNK):
            r = await http.post(UPLOAD_URL, headers=headers,
                                data={"command": "APPEND", "media_id": media_id,
                                      "segment_index": idx // CHUNK},
                                files={"media": data[idx:idx + CHUNK]})
            r.raise_for_status()

        r = await http.post(UPLOAD_URL, headers=headers,
                            data={"command": "FINALIZE", "media_id": media_id})
        r.raise_for_status()
        info = r.json()["data"]

        while info.get("processing_info", {}).get("state") in ("pending", "in_progress"):
            wait = info["processing_info"].get("check_after_secs", 3)
            import asyncio; await asyncio.sleep(wait)
            r = await http.get(UPLOAD_URL, headers=headers,
                               params={"command": "STATUS", "media_id": media_id})
            info = r.json()["data"]

        if info.get("processing_info", {}).get("state") == "failed":
            raise HTTPException(502, f"X media processing failed: {info['processing_info']}")

        r = await http.post(TWEET_URL, headers=headers,
                            json={"text": caption, "media": {"media_ids": [str(media_id)]}})
        r.raise_for_status()
        tweet_id = r.json()["data"]["id"]

    return {"url": f"https://x.com/i/status/{tweet_id}", "posted_as": user["x_username"]}


@app.get("/api/v1/me")
async def me(user: dict = Depends(current_user)):
    return {"username": user["x_username"]}


@app.get("/health")
def health():
    return {"ok": True, "service": "nameit-relay"}
