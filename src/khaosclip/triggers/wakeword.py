"""Wake-word trigger — OpenWakeWord engine for high-accuracy phrase detection.

Why this exists: Vosk runs full speech-to-text and then string-matches, which
means it's fighting the whole stream soundscape (game audio, music, hype) to
parse every word. OpenWakeWord does one job — score incoming audio against a
small neural model trained on ONE phrase — so it ignores everything that isn't
"aye clip that". In noisy streams that's the difference between ~85% and ~95%+
detection, with far fewer false fires.

Model files live in OWW_MODEL_DIR (default: models/openwakeword/) and map to
clip modes by filename stem:

    aye_clip_that.onnx  -> retro  (clip the last RETRO_SECONDS)
    aye_clip_this.onnx  -> start  (open a forward clip)
    aye_end_clip.onnx   -> end    (close the forward clip)

Any missing model simply disables that voice command (hotkey still works).
Custom phrases: train a model with openWakeWord's synthetic-speech notebook
(see docs/SETUP_WAKEWORD.md) and drop the .onnx in the model dir — the stem
becomes the phrase, and you map it to a mode with OWW_MODE_MAP if it doesn't
match the defaults.
"""

from __future__ import annotations

import queue
import time
from pathlib import Path

from khaosclip.config import get_settings
from khaosclip.log import get_logger
from khaosclip.triggers.base import Trigger

log = get_logger("wakeword")

# filename stem -> clip mode
DEFAULT_MODE_MAP = {
    "aye_clip_that": "retro",
    "aye_clip_this": "start",
    "aye_end_clip": "end",
    "aye_stop_clip": "end",
}

# OpenWakeWord expects 16kHz 16-bit mono in 80ms frames
SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280  # 80ms


def discover_models(model_dir: Path, mode_map: dict[str, str] | None = None) -> dict[str, str]:
    """Return {model_path_str: mode} for every recognized model in model_dir.

    Unknown stems (not in the mode map) are skipped with a warning rather than
    guessed — a wake model firing the wrong clip mode mid-stream is worse than
    one that never loads.
    """
    mapping = dict(DEFAULT_MODE_MAP)
    if mode_map:
        mapping.update(mode_map)

    found: dict[str, str] = {}
    if not model_dir.exists():
        return found
    for f in sorted(model_dir.glob("*")):
        if f.suffix.lower() not in (".onnx", ".tflite"):
            continue
        mode = mapping.get(f.stem.lower())
        if mode is None:
            log.warning(
                f"Skipping {f.name}: stem not mapped to a mode. "
                f"Add it via OWW_MODE_MAP (e.g. OWW_MODE_MAP={f.stem}:retro)."
            )
            continue
        found[str(f)] = mode
    return found


def score_hits(scores: dict[str, float], stem_to_mode: dict[str, str],
               threshold: float) -> tuple[str, str, float] | None:
    """Return (mode, stem, score) for the highest-scoring model over threshold.

    'end' outranks 'start' outranks 'retro' on exact ties, mirroring the
    specificity ordering the Vosk matcher used.
    """
    rank = {"end": 0, "start": 1, "retro": 2}
    best: tuple[str, str, float] | None = None
    for stem, score in scores.items():
        mode = stem_to_mode.get(stem)
        if mode is None or score < threshold:
            continue
        if best is None or score > best[2] or (score == best[2] and rank[mode] < rank[best[0]]):
            best = (mode, stem, score)
    return best


class WakeWordTrigger(Trigger):
    name = "wakeword"

    def _run(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd
            from openwakeword.model import Model
        except ImportError as e:
            log.error(
                f"Wake-word deps missing ({e}). "
                'Install with: pip install "khaosclip[wakeword]"'
            )
            return

        s = get_settings()
        models = discover_models(s.oww_model_dir, s.oww_mode_map)
        if not models:
            log.error(
                f"No wake-word models found in {s.oww_model_dir}. "
                "See docs/SETUP_WAKEWORD.md to train/download them, "
                "or set VOICE_ENGINE=vosk to use the Vosk engine."
            )
            return

        stem_to_mode = {Path(p).stem.lower(): m for p, m in models.items()}
        oww = Model(wakeword_models=list(models.keys()))

        audio_q: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(bytes(indata))

        phrases = ", ".join(f"{Path(p).stem.replace('_', ' ')} ({m})" for p, m in models.items())
        log.info(f"Wake-word armed — [bold]{phrases}[/bold] · threshold {s.oww_threshold}")

        last_fire = 0.0
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES,
            dtype="int16", channels=1, callback=callback,
        ):
            while not self._stop.is_set():
                try:
                    data = audio_q.get(timeout=0.5)
                except queue.Empty:
                    continue

                frame = np.frombuffer(data, dtype=np.int16)
                scores = oww.predict(frame)

                hit = score_hits(scores, stem_to_mode, s.oww_threshold)
                if not hit:
                    continue

                # Debounce: the phrase lingers in the rolling audio buffer for a
                # few frames after detection — one shout should equal one clip.
                now = time.monotonic()
                if now - last_fire < s.oww_cooldown_seconds:
                    continue
                last_fire = now

                mode, stem, score = hit
                oww.reset()
                with audio_q.mutex:
                    audio_q.queue.clear()

                phrase = stem.replace("_", " ")
                log.info(f'Heard: "[bold yellow]{phrase}[/bold yellow]" ({mode}, {score:.2f})')
                self.fire(mode=mode, detail=phrase)


def make_voice_trigger(bus):
    """Pick the voice engine per VOICE_ENGINE config.

    auto (default): OpenWakeWord if its models are on disk, else Vosk.
    Explicit 'openwakeword' or 'vosk' forces that engine.
    """
    s = get_settings()
    engine = s.voice_engine.lower()

    if engine == "auto":
        engine = "openwakeword" if discover_models(s.oww_model_dir, s.oww_mode_map) else "vosk"
        log.info(f"VOICE_ENGINE=auto -> using [bold]{engine}[/bold]")

    if engine in ("openwakeword", "oww", "wakeword"):
        return WakeWordTrigger(bus)

    from khaosclip.triggers.voice import VoiceTrigger
    return VoiceTrigger(bus)
