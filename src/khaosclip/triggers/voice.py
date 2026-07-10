"""Voice trigger — offline streaming command detection with Vosk.

Two commands:
  "aye clip that"  -> retro clip (last RETRO_SECONDS)
  "aye clip this"  -> open a forward clip from this moment
  "aye end clip" / "aye clip that" (while open) -> close the forward clip

Small speech models hear "aye" a dozen ways ("i", "a", "hey", "eye"…), so we
normalize those tokens before matching — the streamer shouldn't have to
enunciate like a butler mid-hype.

Why Vosk over Whisper for the trigger: Whisper is batch-oriented; Vosk does
true streaming recognition on CPU with near-zero latency and a ~40MB model.
(Whisper still handles captions in the pipeline, where latency doesn't matter.)
"""

from __future__ import annotations

import json
import queue

from khaosclip.config import get_settings
from khaosclip.log import get_logger
from khaosclip.triggers.base import Trigger

log = get_logger("voice")

# Things small models hear when a human says "aye"
_AYE_VARIANTS = {"aye", "ay", "a", "i", "eye", "hey", "yay"}


def normalize(text: str) -> str:
    """Lowercase and collapse common mishearings of 'aye' into 'aye'."""
    tokens = [("aye" if t in _AYE_VARIANTS else t) for t in text.lower().split()]
    return " ".join(tokens)


def match_command(text: str, start_phrases: list[str], retro_phrases: list[str],
                  end_phrases: list[str]) -> tuple[str, str] | None:
    """Return (mode, phrase) for the first command found in text, else None.

    'start' is checked before 'retro' so "clip this" never falls through to
    a retro match, and end phrases are checked first since they're the most
    specific.
    """
    t = normalize(text)
    for phrase in end_phrases:
        if phrase in t:
            return ("end", phrase)
    for phrase in start_phrases:
        if phrase in t:
            return ("start", phrase)
    for phrase in retro_phrases:
        if phrase in t:
            return ("retro", phrase)
    return None


class VoiceTrigger(Trigger):
    name = "voice"

    def _run(self) -> None:
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except ImportError as e:
            log.error(f"Voice deps missing ({e}). Install with: pip install \"khaosclip[voice]\"")
            return

        s = get_settings()
        if not s.vosk_model_path.exists():
            log.error(
                f"Vosk model not found at {s.vosk_model_path}. "
                "Run scripts/setup.ps1 or download vosk-model-small-en-us-0.15 "
                "from https://alphacephei.com/vosk/models"
            )
            return

        SetLogLevel(-1)
        model = Model(str(s.vosk_model_path))
        rec = KaldiRecognizer(model, 16000)
        audio_q: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(bytes(indata))

        log.info(
            f'Voice armed — retro: [bold]{", ".join(s.retro_phrases)}[/bold] · '
            f'start: [bold]{", ".join(s.start_phrases)}[/bold] · '
            f'end: [bold]{", ".join(s.end_phrases)}[/bold]'
        )

        with sd.RawInputStream(
            samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=callback
        ):
            while not self._stop.is_set():
                try:
                    data = audio_q.get(timeout=0.5)
                except queue.Empty:
                    continue

                if rec.AcceptWaveform(data):
                    text = json.loads(rec.Result()).get("text", "")
                else:
                    text = json.loads(rec.PartialResult()).get("partial", "")

                if not text:
                    continue

                hit = match_command(text, s.start_phrases, s.retro_phrases, s.end_phrases)
                if hit:
                    mode, phrase = hit
                    rec.Reset()
                    with audio_q.mutex:
                        audio_q.queue.clear()
                    log.info(f'Heard: "[bold yellow]{phrase}[/bold yellow]" ({mode})')
                    self.fire(mode=mode, detail=phrase)
