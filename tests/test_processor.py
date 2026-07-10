"""End-to-end pipeline tests against real ffmpeg (skipped if unavailable)."""

import subprocess
from pathlib import Path

import pytest

from khaosclip.pipeline.processor import (
    build_filtergraph,
    ffmpeg_available,
    probe_duration,
    process_clip,
)

needs_ffmpeg = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")


@pytest.fixture
def sample_video(tmp_path) -> Path:
    """A 12-second 1280x720 test clip with audio."""
    out = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc2=duration=12:size=1280x720:rate=30",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out)],
        capture_output=True, check=True,
    )
    return out


def test_filtergraph_contains_crop_and_watermark():
    vf = build_filtergraph()
    assert "crop=1080:1920" in vf
    assert "drawtext" in vf


def test_filtergraph_escapes_watermark(monkeypatch):
    monkeypatch.setenv("WATERMARK", "50:50 odds' club")
    from khaosclip.config import reset_settings
    reset_settings()
    vf = build_filtergraph()
    assert r"\:" in vf and r"\'" in vf


@needs_ffmpeg
def test_process_produces_vertical_trimmed_clip(sample_video, tmp_path):
    out = process_clip(sample_video, out_dir=tmp_path / "clips", keep_seconds=5)
    assert out.exists()

    dur = probe_duration(out)
    assert 4.0 <= dur <= 6.5  # trimmed to last ~5s

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,codec_name", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True,
    ).stdout.strip()
    assert probe == "h264,1080,1920"


@needs_ffmpeg
def test_probe_duration(sample_video):
    assert 11.0 <= probe_duration(sample_video) <= 13.0
