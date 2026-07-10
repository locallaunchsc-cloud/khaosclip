"""KhaosClip CLI.

  khaosclip run       Start the live agent (voice + hotkey triggers)
  khaosclip test      Run any local video through the pipeline — no OBS, no keys
  khaosclip doctor    Check your whole setup before you go live
  khaosclip post      Manually post a processed clip
  khaosclip history   Show your recent clips
"""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from khaosclip import __version__
from khaosclip.config import get_settings
from khaosclip.log import get_logger, setup_logging

app = typer.Typer(
    name="khaosclip",
    help="You stay live. Your clips post themselves.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

BANNER = r"""
[bold]KHAOS[/bold][bold red]CLIP[/bold red] v{v} — you stay live, your clips post themselves
"""


def _boot() -> None:
    s = get_settings()
    setup_logging(s.log_level)
    console.print(BANNER.format(v=__version__))


# ---------------------------------------------------------------- run
@app.command()
def run(
    no_voice: bool = typer.Option(False, help="Disable the voice trigger."),
    no_hotkey: bool = typer.Option(False, help="Disable the hotkey trigger."),
    dry_run: bool = typer.Option(False, help="Process clips but never post."),
):
    """Start the live agent. Go live, say "clip that", keep streaming."""
    _boot()
    log = get_logger("cli")
    s = get_settings()
    if dry_run:
        s.dry_run = True
        log.info("[yellow]DRY RUN[/yellow] — clips will be processed but not posted.")

    from khaosclip.capture import OBSCapture, OBSError
    from khaosclip.events import EventBus
    from khaosclip.worker import ClipWorker

    obs = OBSCapture()
    try:
        obs.connect()
        obs.ensure_replay_buffer()
        log.info("OBS connected — replay buffer rolling.")
    except OBSError as e:
        log.error(str(e))
        raise typer.Exit(1) from None

    if s.auto_post and not s.dry_run and not s.has_x_credentials():
        log.warning(
            f"X credentials missing ({', '.join(s.missing_x_credentials())}) — "
            "clips will be saved locally but NOT posted. Run [bold]khaosclip doctor[/bold]."
        )

    bus = EventBus()
    triggers = []
    if not no_voice:
        from khaosclip.triggers.voice import VoiceTrigger
        triggers.append(VoiceTrigger(bus))
    if not no_hotkey:
        from khaosclip.triggers.hotkey import HotkeyTrigger
        triggers.append(HotkeyTrigger(bus))
    if not triggers:
        log.error("All triggers disabled — nothing to listen for.")
        raise typer.Exit(1)

    for t in triggers:
        t.start()

    log.info("Agent live. [dim]Ctrl+C to stop.[/dim]\n")
    worker = ClipWorker(bus, obs)
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        console.print("\n[dim]Stream safe. Clips saved. Later.[/dim]")


# ---------------------------------------------------------------- test
@app.command()
def test(
    video: Path = typer.Argument(..., exists=True, readable=True,
                                 help="Any local video file to run through the pipeline."),
    post: bool = typer.Option(False, help="Also post the result to X (uses your real account!)."),
):
    """Run a local video through the exact live pipeline. No OBS needed."""
    _boot()
    log = get_logger("cli")
    from khaosclip.pipeline import process_clip

    started = time.time()
    out = process_clip(video)
    log.info(f"Done in {time.time() - started:.1f}s -> [bold]{out.resolve()}[/bold]")

    if post:
        from khaosclip.publish import XPublisher
        url = XPublisher().post_clip(out, text=get_settings().clip_tweet_text)
        log.info(f"Posted: {url}")
    else:
        log.info("Open it, check the crop and watermark. Add --post to send it to X.")


# ---------------------------------------------------------------- doctor
@app.command()
def doctor():
    """Check every part of your setup BEFORE you go live."""
    _boot()
    s = get_settings()
    table = Table(title="Pre-flight check", show_lines=False)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Fix", style="dim")

    def row(name: str, ok: bool, fix: str = ""):
        table.add_row(name, "[green]OK[/green]" if ok else "[red]FAIL[/red]", "" if ok else fix)

    # ffmpeg
    from khaosclip.pipeline.processor import ffmpeg_available
    row("ffmpeg + ffprobe on PATH", ffmpeg_available(), "Install from https://ffmpeg.org")

    # OBS
    obs_ok, obs_fix = False, "Open OBS, enable Tools > WebSocket Server Settings"
    try:
        from khaosclip.capture import OBSCapture
        o = OBSCapture()
        o.connect()
        o.ensure_replay_buffer()
        obs_ok = True
    except Exception as e:
        obs_fix = str(e)
    row("OBS websocket + replay buffer", obs_ok, obs_fix)

    # replay dir
    row(f"Replay dir exists ({s.obs_replay_dir})", Path(s.obs_replay_dir).is_dir(),
        "Set OBS_REPLAY_DIR in .env to OBS's recording path")

    # voice model
    row(f"Vosk model ({s.vosk_model_path})", s.vosk_model_path.exists(),
        "Run scripts/setup.ps1 or download from https://alphacephei.com/vosk/models")

    # mic
    mic_ok, mic_fix = False, "pip install \"khaosclip[voice]\" and check your input device"
    try:
        import sounddevice as sd
        mic_ok = any(d["max_input_channels"] > 0 for d in sd.query_devices())
    except Exception as e:
        mic_fix = str(e)
    row("Microphone available", mic_ok, mic_fix)

    # X creds
    row("X API credentials", s.has_x_credentials(),
        f"Missing: {', '.join(s.missing_x_credentials())} — see docs/SETUP_X_API.md")

    console.print(table)
    console.print("\n[dim]All green? Go live and say the words.[/dim]")


# ---------------------------------------------------------------- post
@app.command()
def post(
    video: Path = typer.Argument(..., exists=True, help="A processed clip to post."),
    text: str = typer.Option(None, help="Post text (defaults to CLIP_TWEET_TEXT)."),
):
    """Manually post a clip to X."""
    _boot()
    from khaosclip.publish import XPublisher

    url = XPublisher().post_clip(video, text=text or get_settings().clip_tweet_text)
    console.print(f"[bold green]Posted:[/bold green] {url}")


# ---------------------------------------------------------------- history
@app.command()
def history(limit: int = typer.Option(15, help="How many recent clips to show.")):
    """Show your recent clips and where they went."""
    _boot()
    from khaosclip.history import History

    h = History(get_settings().history_db)
    records = h.recent(limit)
    if not records:
        console.print("[dim]No clips yet. Go make some noise.[/dim]")
        return

    table = Table(title=f"Last {len(records)} clips")
    table.add_column("When")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Where")
    for r in records:
        when = time.strftime("%m/%d %H:%M", time.localtime(r.created_at))
        status = {"posted": "[green]posted[/green]", "failed": "[red]failed[/red]"}.get(
            r.status, "[yellow]processed[/yellow]"
        )
        table.add_row(when, r.source, status, r.tweet_url or (r.clip_path or ""))
    console.print(table)


@app.command()
def version():
    """Print version."""
    console.print(__version__)


if __name__ == "__main__":
    app()
