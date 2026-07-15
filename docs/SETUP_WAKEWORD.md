# Wake-word engine setup (OpenWakeWord)

NameiT ships two voice engines:

| Engine | How it works | Accuracy in a loud stream | Best for |
|---|---|---|---|
| **openwakeword** | Neural model trained on ONE phrase; ignores all other speech | ~95%+ | Default once models are installed |
| **vosk** | Full speech-to-text, then string-matches the transcript | ~85% | Zero-setup fallback (setup.ps1 installs it) |

`VOICE_ENGINE=auto` (the default) uses OpenWakeWord whenever its models exist
in `models/openwakeword/`, and falls back to Vosk otherwise. Nothing breaks if
you never touch this.

## 1. Install the extra

```
pip install "khaosclip[wakeword]"
```

## 2. Get the models

Each voice command is its own small model file (~1–3MB), named by phrase:

```
models/openwakeword/
  aye_clip_that.onnx   -> retro clip (last RETRO_SECONDS)
  aye_clip_this.onnx   -> open a forward clip
  aye_end_clip.onnx    -> close the forward clip
```

You only need the first one to start — missing models just disable that
command (the hotkey always works).

### Option A — download prebuilt NameiT models
When published, grab them from the repo's Releases page and drop the `.onnx`
files into `models/openwakeword/`.

### Option B — train your own (any phrase, ~30 min, free)
OpenWakeWord trains custom wake words from synthetic speech — no recordings
of your voice needed:

1. Open the official training notebook:
   https://github.com/dscripka/openWakeWord (see "Training New Models" —
   they provide a Google Colab that runs free on a T4)
2. Set the target phrase, e.g. `aye clip that`
3. Run all cells (~30 min). Download the resulting `.onnx`
4. Rename it to the phrase with underscores: `aye_clip_that.onnx`
5. Drop it in `models/openwakeword/`

Repeat per phrase. Want a totally custom phrase like "lets ride"? Train it,
save as `lets_ride.onnx`, and map it to a mode in `.env`:

```ini
OWW_MODE_MAP=lets_ride:retro
```

## 3. Tune it

```ini
VOICE_ENGINE=auto        # auto | openwakeword | vosk
OWW_THRESHOLD=0.5        # raise (0.6–0.7) if false fires; lower (0.35) if it misses you
OWW_COOLDOWN_SECONDS=2   # debounce so one shout = one clip
```

Or per-session: `khaosclip run --engine openwakeword`

## 4. Verify

```
khaosclip run --dry-run --engine openwakeword
```

Say the phrase at normal stream volume with your usual background audio
running. You should see:

```
Heard: "aye clip that" (retro, 0.87)
```

If the score hovers just under threshold, lower `OWW_THRESHOLD` a notch
rather than shouting like a butler.

## Troubleshooting

- **"No wake-word models found"** — the `.onnx` files aren't in
  `OWW_MODEL_DIR` (default `models/openwakeword/`), or the stems don't match
  a known mode. Check the filenames.
- **Fires on random speech** — raise `OWW_THRESHOLD` to 0.6–0.7.
- **Misses the phrase over loud game audio** — use a headset mic (less bleed),
  or lower the threshold slightly. Wake models key on your voice pattern, not
  loudness, so mic quality matters more than volume.
- **Want the old behavior back** — `VOICE_ENGINE=vosk`. Both engines stay
  installed side by side.
