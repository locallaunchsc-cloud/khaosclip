# Building NameiT-Setup.exe

The one-click installer streamers actually use. No git, no Python, no terminal
on their side — download, double-click, Next, Finish, tray icon appears.

## What the user experiences

1. Download `NameiT-Setup.exe` (~150MB — Python runtime + Vosk + ffmpeg inside)
2. Double-click → Next → Finish (like installing Discord)
3. NameiT launches → **setup wizard** (30 seconds):
   - OBS recording folder **auto-detected** from OBS's own config (one click to confirm; Browse button if it guessed wrong)
   - Mic check: they talk, the bar goes green
   - Done
4. Green icon in the system tray = armed and listening
5. They stream. They say "aye clip that". A small popup shows 3 AI captions
   (or auto-picks in 10s). X compose opens with the caption pre-filled, clip
   folder opens, they drag + Post.

Right-click the tray icon: Start/Stop listening · Open clips folder ·
Settings · Quit. Settings live at `%APPDATA%\NameiT\.env`.

## Build it (your machine, one time setup)

```powershell
winget install JRSoftware.InnoSetup
# download ffmpeg essentials zip from https://www.gyan.dev/ffmpeg/builds/
# copy ffmpeg.exe (from the zip's bin\) into packaging\bin\
```

## Build it (every release)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Output: `packaging\out\NameiT-Setup.exe`

Upload to a GitHub Release, link it from nameit.vercel.app as the big
**[Download for Windows]** button. The git-clone path stays in the README for
devs — same engine, two front doors.

## Pieces

| File | Job |
|---|---|
| `launcher.py` | Frozen entrypoint: sets workdir to `%APPDATA%\NameiT`, wires bundled ffmpeg/Vosk, starts the app |
| `nameit.spec` | PyInstaller config: what gets bundled |
| `installer.iss` | Inno Setup: shortcuts, optional run-at-startup, uninstaller |
| `build.ps1` | Runs the whole chain with pre-flight checks |
| `src/khaosclip/gui/` | Wizard, tray app, popup caption picker |
| `src/khaosclip/obs_detect.py` | Reads OBS's config to auto-fill the wizard |

## Notes

- `PrivilegesRequired=lowest` — installs per-user, no admin prompt, no
  SmartScreen admin scare. (Unsigned exe still shows the blue SmartScreen
  banner once — "More info → Run anyway". Code-signing cert removes it later;
  ~$100/yr, do it when the tool has traction.)
- The GUI sets `GUI_MODE=true`, which swaps the terminal caption picker for
  the popup. The CLI is untouched.
- Mac build later: same spec works with minor changes + a .dmg; not worth it
  until a Mac streamer asks.
