# OBS setup (one time, ~2 minutes)

## 1. Enable the WebSocket server
- OBS → **Tools → WebSocket Server Settings**
- Check **Enable WebSocket server**
- Click **Show Connect Info**, copy the password
- Put it in `.env` as `OBS_WS_PASSWORD`

## 2. Enable the Replay Buffer
- OBS → **Settings → Output**
- Recording tab → check **Enable Replay Buffer**
- **Maximum Replay Time**: `120` seconds — the buffer must cover your longest
  clip (retro default 60s, forward clips up to 90s)

## 3. Match the recording path
- OBS → **Settings → Output → Recording → Recording Path**
- Copy that exact path into `.env` as `OBS_REPLAY_DIR`

## 4. Verify
```
khaosclip doctor
```
"OBS websocket + replay buffer" should be OK. If OBS is closed, the check
fails — that's expected; open OBS first.

## Notes
- KhaosClip auto-starts the replay buffer when the agent launches if it's off.
- Replay Buffer holds video in RAM — 120s at 1080p is roughly 1.5–2.5 GB. If
  your machine is tight, drop to 90s and lower MAX_FORWARD_SECONDS to match.
