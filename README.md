<div align="center">

# KHAOSCLIP

**You stay live. Your clips post themselves.**

Voice-triggered clipping for X Live streamers. Say *"aye clip that"* mid-stream —
KhaosClip grabs the last 60 seconds from OBS, formats it vertical with your
handle burned in, and posts it to X while you keep streaming. Or say
*"aye clip this"* to open a clip, and close it when the moment's done.

![CI](https://github.com/locallaunchsc-cloud/khaosclip/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-alpha%20%C2%B7%20building%20in%20public-red)

</div>

---

## Why

X launched Live Studio and put creator payouts behind livestreaming. Every
streamer arriving on the platform has the same problem: **the moment happens
live, but the growth happens in clips** — and clipping means scrubbing a
4-hour VOD after the stream, so most streamers just don't.

KhaosClip removes the entire job. You never stop streaming. You never open an
editor. You say two words and the clip is on your timeline before the chat
stops spamming.

Built by a clipper with 1B+ views generated across Web3 campaigns. The
auto-format isn't generic — it cuts the way clips that actually perform get cut.

## How it works

### Two voice commands

| You say | What happens |
|---|---|
| **"aye clip that"** | Retro clip — the last 60s (configurable up to 90) are captured. The moment already happened? Already got it. |
| **"aye clip this"** | Opens a forward clip from this moment. Say *"aye clip that"* or *"aye end clip"* when the moment's done — auto-closes at 90s. |

The forward clip needs no extra recording: OBS's Replay Buffer is always
holding the recent past, so closing a forward clip just trims the exact
window you marked. The "aye" prefix means casual conversation ("that clip
was crazy") never fires by accident — and the recognizer accepts every way
a hype human says "aye" (i / hey / a / eye), so you don't have to enunciate.

```
"aye clip that" / "aye clip this…that"   (offline voice — or hotkey, or Stream Deck)
        │
        ▼
OBS Replay Buffer saves        (the last 120s were already in RAM — the moment is captured)
        │
        ▼
ffmpeg auto-format             (trim to your window → 9:16 vertical → handle burned in)
        │
        ▼
posted to X                    (API v2 upload with retries — while you're still talking)
```

No OBS plugin. It rides OBS's built-in Replay Buffer over obs-websocket,
which ships with OBS 28+. Full design notes in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quickstart (Windows)

```powershell
git clone https://github.com/locallaunchsc-cloud/khaosclip
cd khaosclip
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

The setup script creates a venv, installs everything, downloads the offline
voice model (~40MB), creates your `.env`, and runs the pre-flight check.

Then:

1. Configure OBS (2 min): [docs/SETUP_OBS.md](docs/SETUP_OBS.md)
2. Get X API keys (5 min): [docs/SETUP_X_API.md](docs/SETUP_X_API.md)
3. Verify everything:

```powershell
khaosclip doctor
```

4. Go live:

```powershell
khaosclip run
```

Say the words. Watch your timeline.

## Try it right now — no OBS, no API keys

```powershell
khaosclip test path\to\any_video.mp4
```

Runs any local video through the exact live pipeline and drops the formatted
vertical clip in `./clips`. Add `--post` to send it to X for real.

## CLI

| Command | What it does |
|---|---|
| `khaosclip run` | Start the live agent (voice + hotkey triggers) |
| `khaosclip run --dry-run` | Full rehearsal — clips process but never post |
| `khaosclip test <video>` | Run any file through the pipeline |
| `khaosclip doctor` | Pre-flight check: OBS, ffmpeg, mic, model, keys |
| `khaosclip post <clip>` | Manually post a processed clip |
| `khaosclip history` | Every clip you've made and where it went |

## Configuration

Everything lives in `.env` ([.env.example](.env.example) has the full list):

```ini
# AI captions
AI_CAPTIONS=true
ANTHROPIC_API_KEY=your-key-here
STREAMER_CONTEXT=crypto / Web3 streamer, live trade calls, Solana and Hyperliquid perps
CAPTION_PICK_TIMEOUT=10

RETRO_PHRASES=aye clip that                    # your words, your call
START_PHRASES=aye clip this
END_PHRASES=aye end clip,aye stop clip
RETRO_SECONDS=60                               # how far back "clip that" reaches
MAX_FORWARD_SECONDS=90                         # forward clips auto-close here (X caps at 140)
WATERMARK=@YourHandle
HOTKEY=ctrl+alt+c                              # retro clip / closes an open clip
TRIGGER_COOLDOWN_SECONDS=15                    # no double-fires on hype moments
CAPTIONS=false                                 # burned captions (heavier CPU)
```

## Built to not ruin your stream

- **One clip at a time.** Triggers queue; a single worker processes. Shouting
  "clip that" three times in a hype moment = one clip, not three encodes
  fighting your stream encoder.
- **Failures are boring.** Capture fails → agent keeps listening. Processing
  fails → raw replay preserved. Posting fails → retried with backoff, clip
  stays on disk. Nothing crashes mid-stream; no clip is ever lost.
- **Everything is logged.** `khaosclip history` + `logs/khaosclip.log`.
- **Rehearsal mode.** `--dry-run` runs the full pipeline without posting.
- **23 tests, CI on Windows + Linux.** The pipeline is verified end-to-end
  against real ffmpeg on every commit.

## Roadmap

## AI Caption Generation

After every clip, KhaosClip transcribes what you said and asks Claude for 3
SEO-optimized tweet captions tailored to your niche:

```
  📋  CAPTION SUGGESTIONS  (clip is ready to post)
────────────────────────────────────────────────────────────
  [1] I called this trade LIVE and it hit exactly 🎯 #Hyperliquid #crypto
  [2] nobody believed me on this setup 👀 #HoodToshi #Solana
  [3] just printed live on stream 💰 #perps #trading

  [Enter] post with [1]  |  type 2 or 3 to pick another
  [s] skip / use default  |  [e] edit before posting
────────────────────────────────────────────────────────────
  Auto-posting in 8s…
```

10 seconds to pick. Auto-selects #1 if you ignore it. The clip is never
held hostage. Enable with `AI_CAPTIONS=true` and your `ANTHROPIC_API_KEY`.

## Roadmap

- [ ] **Chat trigger** — viewers type `!clip`; your audience becomes the clipping army
- [ ] **AI moment detection** — audio energy + chat velocity pick the clip boundaries
- [ ] **Karaoke captions** — word-by-word styled captions
- [ ] **Style presets** — per-streamer branding (fonts, colors, layouts)
- [ ] **Hosted tier** — zero install, browser dashboard, cloud processing

Building in public. Follow along: [@KhaosClipper](https://x.com/KhaosClipper)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Ground rules: never crash mid-stream,
never lose a clip, keep the trigger path light.

## License

MIT — see [LICENSE](LICENSE).
