# Changelog

## [0.1.0] — 2026-07-09

First public build. Built live, in public.

### Added
- Skills: caption style templates (yoxic_jack expert/insider, crypto_alpha
  trade receipts, comedy, narrative) — `khaosclip skills` to list,
  `--skill <key>` per session, custom .json skills supported
- AI caption generation: Whisper transcribes the clip, Claude suggests 3
    SEO-optimized tweet captions, terminal picker with 10s auto-select countdown
- Two voice commands via offline Vosk recognition:
  - "aye clip that" — retro clip of the last 60s (configurable to 90)
  - "aye clip this" … "aye clip that"/"aye end clip" — forward clip of an exact
    marked window, auto-closes at 90s
- "Aye" mishearing normalization (i / a / hey / eye all accepted)
- Hotkey trigger — global shortcut fallback (default `ctrl+alt+c`)
- OBS Replay Buffer capture over obs-websocket v5 (no plugin required)
- ffmpeg pipeline: end-trim, 9:16 vertical crop, watermark burn, optional Whisper captions
- X API v2 publisher: chunked media upload + post, retry with exponential backoff
- `khaosclip` CLI: `run`, `test`, `doctor`, `post`, `history`
- SQLite clip history
- Trigger cooldown + single-worker queue (no encode pile-ups mid-stream)
- Dry-run mode for rehearsals
- Windows one-shot installer (`scripts/setup.ps1`)
- Full test suite (23 tests) + GitHub Actions CI
