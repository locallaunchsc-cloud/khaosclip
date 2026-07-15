"""Caption AI tests — fully mocked, no Whisper, no API calls."""

import json
from unittest.mock import MagicMock, patch

from khaosclip.caption_ai import generate_captions, get_caption_for_clip, pick_caption
from khaosclip.config import reset_settings


def test_generate_captions_parses_response(monkeypatch):
    captions = ["cap1 #crypto", "cap2 #solana", "cap3 #hyperliquid"]
    fake_body = json.dumps({
        "content": [{"text": json.dumps({"captions": captions})}]
    }).encode()

    fake_resp = MagicMock()
    fake_resp.read.return_value = fake_body
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with patch("urllib.request.urlopen", return_value=fake_resp):
        result = generate_captions("I just called this trade live")
    assert result == captions


def test_generate_captions_returns_empty_on_api_failure(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        result = generate_captions("some transcript")
    assert result == []


def test_generate_captions_no_key_returns_empty():
    result = generate_captions("transcript", )
    assert result == []


def test_pick_caption_non_tty_picks_first(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    result = pick_caption(["cap1", "cap2", "cap3"], default="default")
    assert result == "cap1"


def test_pick_caption_empty_list_returns_default(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    result = pick_caption([], default="my default")
    assert result == "my default"


def test_get_caption_ai_disabled(tmp_path, monkeypatch):
    reset_settings()
    monkeypatch.setenv("AI_CAPTIONS", "false")
    monkeypatch.setenv("CLIP_TWEET_TEXT", "default text")
    reset_settings()

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    result = get_caption_for_clip(clip)
    assert result == "default text"


def test_get_caption_falls_back_on_failure(tmp_path, monkeypatch):
    reset_settings()
    monkeypatch.setenv("AI_CAPTIONS", "true")
    monkeypatch.setenv("CLIP_TWEET_TEXT", "fallback text")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    reset_settings()

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    with patch("khaosclip.caption_ai.transcribe_clip", side_effect=RuntimeError("whisper died")):
        result = get_caption_for_clip(clip)
    assert result == "fallback text"
