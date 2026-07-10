# Architecture

```
                 ┌─────────────────────────────────────────────┐
                 │                YOUR STREAM PC               │
                 │                                             │
  mic ──────────▶│  VoiceTrigger (Vosk, offline, streaming)    │
  keyboard ─────▶│  HotkeyTrigger (global shortcut)            │
                 │        │                                    │
                 │        ▼  ClipEvent                         │
                 │  ┌──────────┐   one at a time, cooldown     │
                 │  │ EventBus │──▶ ClipWorker ────────────┐   │
                 │  └──────────┘                           │   │
                 │                                         ▼   │
                 │  OBS (Replay Buffer, last 90s in RAM)       │
                 │        │ obs-websocket: SaveReplayBuffer    │
                 │        ▼                                    │
                 │  raw replay file on disk                    │
                 │        │                                    │
                 │        ▼                                    │
                 │  Pipeline (ffmpeg)                          │
                 │   trim last 45s → 9:16 crop → watermark     │
                 │   → optional Whisper captions               │
                 │        │                                    │
                 │        ▼                                    │
                 │  XPublisher (API v2 chunked upload, retry)  │
                 └────────┼────────────────────────────────────┘
                          ▼
                    x.com/i/status/…       history.db (every clip logged)
```

## Design decisions

**No OBS plugin.** OBS's built-in Replay Buffer + obs-websocket v5 (ships with
OBS 28+) gives us the last N seconds on demand with zero install inside OBS.
A native plugin would mean C++, per-version builds, and scaring users during
install. This way `pip install` is the whole story.

**Vosk for the trigger, Whisper for captions.** The trigger must be
always-on, instant, and invisible next to a game + encoder. Vosk does
streaming recognition on CPU with a 40MB model. Whisper is far better at
transcription but batch-oriented and heavy — perfect for captions after
capture, wrong for the hot path.

**Two clip modes, one buffer.** "Aye clip that" trims the last 60s. "Aye
clip this" just records a timestamp — when the clip is closed (voice, hotkey,
or the 90s auto-close), the worker saves the buffer and trims exactly the
marked window. Forward clips cost nothing extra: the buffer was already
rolling.

**Queue + single worker.** Triggers publish events; one worker consumes.
A hype moment where you yell "clip that" three times produces one clip
(cooldown), never three parallel ffmpeg encodes fighting your stream encoder.

**Failures are boring.** Every stage is wrapped: capture fails → logged, agent
keeps listening. Processing fails → raw replay preserved. Posting fails →
retried with backoff, then the clip stays on disk and the failure is recorded
in history. Nothing ever crashes the agent mid-stream, and no clip is ever lost.

**Clips ≤ 140s.** X rejects longer video for standard accounts; config
validation enforces it at startup, not at post time.

## Roadmap architecture notes

- **Chat trigger (`!clip`)**: X has no public livestream-chat API today. The
  planned approach is a browser-side companion (extension or headless watcher)
  that reads the stream's chat DOM and hits a local webhook on this agent.
  The `Trigger` interface is already built for it.
- **Hosted tier**: the pipeline + publisher are pure functions of (file,
  settings) — they lift cleanly onto a cloud worker for the no-install version.
- **AI moment detection**: audio-energy + chat-velocity scoring inside the
  buffer window to auto-pick clip boundaries instead of a fixed 45s.
