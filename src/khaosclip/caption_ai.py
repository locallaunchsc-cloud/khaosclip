"""AI caption generator — transcribes the clip, asks Claude for tweet options.

Flow:
  1. Whisper transcribes the audio (fast, CPU, base model ~30s for a 60s clip)
  2. Claude gets the transcript + streamer context and returns 3 captions
  3. Terminal shows a countdown picker — one keypress or auto-selects #1

This is the only network call in the hot path. Everything else (voice,
ffmpeg, OBS) is fully local. If the API is down or slow, we fall back to
the default CLIP_TWEET_TEXT and post immediately — the clip is never held
hostage waiting for a caption.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

from khaosclip.config import get_settings
from khaosclip.log import get_logger

log = get_logger("caption")

SYSTEM_PROMPT = """You are a social media expert for live streamers on X (Twitter).
Your job: given a transcript of a live stream clip, write 3 short tweet captions.

Rules:
- X (Twitter) ONLY — no YouTube, TikTok, or cross-platform language
- Each caption under 200 characters (leave room for the video)
- Hook-first: lead with the most exciting/surprising part
- Match the streamer's niche and voice exactly
- 2-3 relevant X/crypto hashtags woven in naturally
- Conversational and native to CT (Crypto Twitter) — not corporate
- Vary the angle: one hype, one curiosity/question, one alpha-drop

Respond ONLY with valid JSON, no markdown, no explanation:
{"captions": ["caption1", "caption2", "caption3"]}"""


def transcribe_clip(clip_path: Path) -> str:
    """Run Whisper on the clip and return the transcript text."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log.warning("faster-whisper not installed — skipping transcription. "
                    "Install with: pip install \"khaosclip[captions]\"")
        return ""

    log.info("Transcribing clip for caption suggestions…")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(clip_path), word_timestamps=False)
    text = " ".join(seg.text.strip() for seg in segments)
    log.info(f"Transcript ({len(text)} chars): {text[:120]}{'…' if len(text) > 120 else ''}")
    return text


def generate_captions(transcript: str, context: str = "") -> list[str]:
    """Call Claude API and return 3 caption strings."""
    import urllib.request

    s = get_settings()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping AI captions.")
        return []

    user_msg = f"""Streamer niche/context: {context or s.streamer_context}

Clip transcript:
{transcript or "(no transcript available)"}

Generate 3 tweet captions for this clip."""

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 400,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            raw = body["content"][0]["text"].strip()
            # Strip any accidental markdown fences
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            return data.get("captions", [])
    except Exception as e:
        log.warning(f"Claude caption API failed: {e}")
        return []


def pick_caption(captions: list[str], default: str, timeout: int = 10) -> str:
    """Show numbered options in terminal, auto-select #1 after timeout seconds.

    Returns the chosen caption string.
    Works even if stdin is not a tty (falls back to default immediately).
    """
    if not captions:
        return default

    if not sys.stdin.isatty():
        log.info(f"Non-interactive mode — using caption: {captions[0]}")
        return captions[0]

    print("\n" + "─" * 60)
    print("  📋  CAPTION SUGGESTIONS  (clip is ready to post)")
    print("─" * 60)
    for i, cap in enumerate(captions, 1):
        print(f"  [{i}] {cap}")
    print(f"\n  [Enter] post with [1]  |  type 2 or 3 to pick another")
    print(f"  [s] skip / use default  |  [e] edit before posting")
    print("─" * 60)

    chosen = [captions[0]]  # default
    done = threading.Event()

    def countdown():
        for remaining in range(timeout, 0, -1):
            if done.is_set():
                return
            print(f"\r  Auto-posting in {remaining}s… ", end="", flush=True)
            time.sleep(1)
        if not done.is_set():
            print("\r  Auto-posting now…         ")
            done.set()

    t = threading.Thread(target=countdown, daemon=True)
    t.start()

    try:
        raw = input().strip().lower()
        done.set()
        if raw == "2" and len(captions) >= 2:
            chosen[0] = captions[1]
        elif raw == "3" and len(captions) >= 3:
            chosen[0] = captions[2]
        elif raw == "s":
            chosen[0] = default
        elif raw == "e":
            print("  Edit caption (Enter to confirm):")
            print(f"  > {captions[0]}")
            edited = input("  > ").strip()
            if edited:
                chosen[0] = edited
        # else: Enter or anything else -> keep captions[0]
    except (EOFError, KeyboardInterrupt):
        done.set()

    print(f"\n  ✓  Posting: {chosen[0]}\n")
    return chosen[0]


def get_caption_for_clip(clip_path: Path) -> str:
    """Full pipeline: transcribe -> generate -> pick. Returns final tweet text.

    Always returns something usable — falls back to default if anything fails.
    """
    s = get_settings()
    default = s.clip_tweet_text

    if not s.ai_captions:
        return default

    try:
        transcript = transcribe_clip(clip_path)
        captions = generate_captions(transcript)
        return pick_caption(captions, default=default, timeout=s.caption_pick_timeout)
    except Exception as e:
        log.warning(f"Caption pipeline failed, using default: {e}")
        return default
