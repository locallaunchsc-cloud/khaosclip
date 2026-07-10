"""Captions — transcribe with faster-whisper, burn styled subtitles.

Off by default: Whisper on CPU competes with the stream encoder. Turn on
with CAPTIONS=true if your machine has headroom, or wait for the hosted
version where this runs on our workers.
"""

from __future__ import annotations

from pathlib import Path

from khaosclip.config import get_settings
from khaosclip.log import get_logger
from khaosclip.pipeline.processor import ProcessError, _run

log = get_logger("captions")

_STYLE = (
    "FontName=Arial,FontSize=14,Bold=1,PrimaryColour=&HFFFFFF&,"
    "OutlineColour=&H000000&,Outline=2,MarginV=60"
)


def _ts(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    sec = int(seconds)
    return f"{sec // 3600:02}:{(sec % 3600) // 60:02}:{sec % 60:02},{ms:03}"


def burn_captions(clip: Path) -> Path:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ProcessError(
            "Captions enabled but faster-whisper missing. "
            "Install with: pip install \"khaosclip[captions]\""
        ) from e

    s = get_settings()
    log.info(f"Transcribing with whisper-{s.whisper_model} (CPU)…")
    model = WhisperModel(s.whisper_model, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(clip), word_timestamps=False)

    srt_path = clip.with_suffix(".srt")
    n = 0
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n{_ts(seg.start)} --> {_ts(seg.end)}\n{seg.text.strip()}\n\n")
            n = i
    if n == 0:
        log.warning("No speech detected — skipping caption burn.")
        return clip

    captioned = clip.with_name(clip.stem + "_cc.mp4")
    srt_arg = str(srt_path).replace("\\", "/").replace(":", r"\:")
    _run([
        "ffmpeg", "-y", "-i", str(clip),
        "-vf", f"subtitles='{srt_arg}':force_style='{_STYLE}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "copy", str(captioned),
    ])
    log.info(f"Captions burned ({n} segments).")
    return captioned
