# Troubleshooting

Run `khaosclip doctor` first — it catches 90% of issues with a fix per line.

## "Replay saved but no file found"
`OBS_REPLAY_DIR` in `.env` doesn't match OBS's actual recording path.
Check OBS → Settings → Output → Recording → Recording Path. Copy exactly.

## Voice trigger doesn't hear me
- Wrong input device: Windows Sound Settings → set your stream mic as default
  input, or check `python -c "import sounddevice; print(sounddevice.query_devices())"`
- Talking over game audio: the trigger listens to the mic device, not the
  stream mix — it hears what your mic hears. If your mic gain is low, raise it.
- Say the phrase clearly; the small model favors low CPU over vocabulary.
  You can change phrases: `RETRO_PHRASES=run it back` etc.
- "Aye" is heard many ways (i / a / hey / eye) — all are accepted, so don't
  over-enunciate. If it still misses, check your mic gain.
- The hotkey (`ctrl+alt+c`) always works as backup — retro clip, or closes
  an open forward clip.

## Voice trigger fires accidentally
The "aye" prefix already blocks casual mentions ("that clip was crazy" does
nothing). If you get false fires anyway, raise `TRIGGER_COOLDOWN_SECONDS` or
switch to a more unusual phrase set.

## I said "aye clip this" and nothing posted
Forward clips don't post until you CLOSE them — say "aye clip that" or
"aye end clip", or wait for the auto-close at MAX_FORWARD_SECONDS. Watch the
console: you'll see CLIP OPEN when the mark is set and CLIP CLOSE when it
captures.

## Post failed: 401 Unauthorized
Access token was generated before you set Read+Write permissions.
Regenerate the Access Token & Secret on developer.x.com and update `.env`.

## Post failed: 403 / "not permitted"
- App lacks write permission (see SETUP_X_API.md step 2)
- Or your API tier's monthly post cap is hit

## Clips look pixelated in fast motion
OBS Replay Buffer inherits your recording encoder settings. In OBS →
Settings → Output → Recording, use a higher-quality preset (or NVENC with
CQ ~20). KhaosClip re-encodes at CRF 21, which preserves what it's given.

## ffmpeg is slow / drops my stream FPS while processing
- Keep `CAPTIONS=false` while streaming (Whisper is the heavy part)
- The worker runs ONE encode at a time by design, at `veryfast` preset
- If it still hurts, lower RETRO_SECONDS or clip after raid/break moments

## Nothing posts, no errors
Check `AUTO_POST=true` and `DRY_RUN=false` in `.env`. Then `khaosclip history`
to see what each clip did, and `logs/khaosclip.log` for full detail.
