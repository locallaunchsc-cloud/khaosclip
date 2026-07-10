"""Clip processor — raw OBS replay -> feed-ready vertical clip.

Pipeline (pure ffmpeg, deterministic):
  1. Trim to the last `keep_seconds` (the moment is always at the END
     of a replay buffer — that's the entire point of a replay buffer)
  2. Center-crop 16:9 -> 9:16 at 1080x1920
  3. Burn the streamer's handle bottom-center
  4. Optional: burn word-timed captions (see captions.py)

Output targets X's video specs: H.264 High yuv420p + AAC, faststart,
<= 140s (enforced in config validation).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from khaosclip.config import get_settings
from khaosclip.log import get_logger

log = get_logger("pipeline")


class ProcessError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise ProcessError(f"ffmpeg failed:\n{r.stderr[-1500:]}")


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError as e:
        raise ProcessError(f"Could not read duration of {path.name}: {r.stderr[-300:]}") from e


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'").replace("%", r"\%")


def build_filtergraph() -> str:
    s = get_settings()
    filters: list[str] = []
    if s.vertical:
        # Scale so height fills the frame, then center-crop the width.
        filters.append(f"scale=-2:{s.output_height},crop={s.output_width}:{s.output_height}")
    if s.watermark:
        text = _escape_drawtext(s.watermark)
        filters.append(
            f"drawtext=text='{text}':"
            "fontcolor=white@0.85:fontsize=42:"
            "box=1:boxcolor=black@0.35:boxborderw=12:"
            "x=(w-text_w)/2:y=h-140"
        )
    return ",".join(filters) if filters else "null"


def process_clip(raw: Path, out_dir: Path | None = None,
                 keep_seconds: float | None = None) -> Path:
    if not ffmpeg_available():
        raise ProcessError("ffmpeg/ffprobe not found on PATH. Install: https://ffmpeg.org")

    s = get_settings()
    out_dir = out_dir or s.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"clip_{int(time.time())}.mp4"

    keep = keep_seconds if keep_seconds is not None else s.retro_seconds
    dur = probe_duration(raw)
    start = max(0.0, dur - keep) if keep > 0 else 0.0
    log.info(f"Processing {raw.name} ({dur:.0f}s) -> last {dur - start:.0f}s, "
             f"{'9:16 vertical' if s.vertical else 'source aspect'}")

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.2f}", "-i", str(raw),
        "-vf", build_filtergraph(),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        str(out),
    ]
    _run(cmd)

    if s.captions:
        from khaosclip.pipeline.captions import burn_captions
        out = burn_captions(out)

    return out
