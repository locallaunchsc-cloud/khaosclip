"""Clip worker — consumes trigger events, runs the full pipeline for each.

Two clip modes:
  RETRO   ("aye clip that"): save the buffer, keep the last retro_seconds.
  FORWARD ("aye clip this" … "aye clip that"/"aye end clip"): mark a start
          time; on close, save the buffer and keep exactly the marked window.
          Auto-closes at max_forward_seconds.

The forward mode needs no extra recording: the replay buffer is ALWAYS
holding the recent past, so a forward clip is just "trim the last
(now - marked_start) seconds" at close time.

Guarantees:
  * One encode at a time (no pile-ups on a streaming PC)
  * Cooldown between completed clips (no double-fires from one shout)
  * A failure at any stage never crashes the agent or loses the raw replay
  * Everything is recorded in history.db
"""

from __future__ import annotations

import time

from khaosclip.caption_ai import get_caption_for_clip
from khaosclip.capture import OBSCapture
from khaosclip.config import get_settings
from khaosclip.events import ClipEvent, EventBus
from khaosclip.history import History
from khaosclip.log import get_logger
from khaosclip.pipeline import probe_duration, process_clip
from khaosclip.publish import XPublisher

log = get_logger("worker")

# Small pad so "aye clip this" captures the second or two BEFORE you said it —
# the thing that made you call the clip is usually already happening.
FORWARD_LEAD_PAD_S = 2.0


class ClipWorker:
    def __init__(self, bus: EventBus, obs: OBSCapture,
                 publisher: XPublisher | None = None, history: History | None = None):
        self.bus = bus
        self.obs = obs
        self.publisher = publisher or XPublisher()
        self.history = history or History(get_settings().history_db)
        self._last_clip_at = 0.0
        self._forward_started_at: float | None = None

    # ------------------------------------------------------------ loop
    def run_forever(self) -> None:
        while True:
            event = self.bus.next(timeout=0.5)
            self._maybe_autoclose()
            if event is None:
                continue
            self.dispatch(event)

    def _maybe_autoclose(self) -> None:
        """Forward clips can't run past max_forward_seconds — close them."""
        s = get_settings()
        if (self._forward_started_at is not None
                and time.time() - self._forward_started_at >= s.max_forward_seconds):
            log.info(f"Forward clip hit {s.max_forward_seconds}s — auto-closing.")
            self._close_forward(source="auto")

    # ------------------------------------------------------------ dispatch
    def dispatch(self, event: ClipEvent) -> None:
        mode = event.mode
        if mode == "auto":  # hotkey: do the intuitive thing
            mode = "end" if self._forward_started_at is not None else "retro"

        if mode == "start":
            self._handle_start(event)
        elif mode == "end":
            self._handle_end(event)
        else:  # retro — but "aye clip that" while a clip is open means "close it"
            if self._forward_started_at is not None:
                self._handle_end(event)
            else:
                self._handle_retro(event)

    # ------------------------------------------------------------ start
    def _handle_start(self, event: ClipEvent) -> None:
        if self._forward_started_at is not None:
            elapsed = time.time() - self._forward_started_at
            log.info(f"Forward clip already open ({elapsed:.0f}s) — ignoring start.")
            return
        if not self._cooldown_ok():
            return
        self._forward_started_at = time.time() - FORWARD_LEAD_PAD_S
        s = get_settings()
        log.info(f"[bold]CLIP OPEN[/bold] ({event.source}) — say "
                 f'"{s.retro_phrases[0]}" or "{s.end_phrases[0]}" to close, '
                 f"auto-closes at {s.max_forward_seconds}s.")

    # ------------------------------------------------------------ end
    def _handle_end(self, event: ClipEvent) -> None:
        if self._forward_started_at is None:
            log.info("No forward clip open — nothing to close.")
            return
        self._close_forward(source=event.source)

    def _close_forward(self, source: str) -> None:
        s = get_settings()
        elapsed = time.time() - self._forward_started_at
        keep = min(elapsed, s.max_forward_seconds)
        self._forward_started_at = None
        log.info(f"[bold]CLIP CLOSE[/bold] ({source}) — capturing the last {keep:.0f}s.")
        self._make_clip(source=source, keep_seconds=keep)

    # ------------------------------------------------------------ retro
    def _handle_retro(self, event: ClipEvent) -> None:
        if not self._cooldown_ok():
            return
        s = get_settings()
        log.info(f"[bold]CLIP[/bold] retro ({event.source}"
                 + (f', "{event.detail}"' if event.detail else "")
                 + f") — last {s.retro_seconds}s.")
        self._make_clip(source=event.source, keep_seconds=s.retro_seconds)

    # ------------------------------------------------------------ shared
    def _cooldown_ok(self) -> bool:
        s = get_settings()
        since = time.time() - self._last_clip_at
        if since < s.trigger_cooldown_seconds:
            log.info(f"Trigger ignored — cooldown "
                     f"({since:.0f}s / {s.trigger_cooldown_seconds:.0f}s).")
            return False
        return True

    def _make_clip(self, source: str, keep_seconds: float) -> None:
        s = get_settings()
        self._last_clip_at = time.time()

        # 1. capture
        try:
            raw = self.obs.save_replay()
            log.info(f"Replay captured: {raw.name}")
        except Exception as e:
            log.error(f"Capture failed: {e}")
            return

        clip_id = self.history.start(source=source, raw_path=str(raw))

        # 2. process
        try:
            clip = process_clip(raw, keep_seconds=keep_seconds)
            self.history.mark_processed(clip_id, str(clip), probe_duration(clip))
            log.info(f"Formatted: {clip.name}")
        except Exception as e:
            self.history.mark_failed(clip_id, f"process: {e}")
            log.error(f"Processing failed (raw replay kept at {raw}): {e}")
            return

        # 3. publish
        if not s.auto_post:
            log.info(f"AUTO_POST off — clip ready at {clip}")
            return

        # AI caption: transcribe + Claude suggestions + terminal picker
        caption = get_caption_for_clip(clip)
        if s.brand_tag:
            caption = f"{caption}\n\n{s.brand_tag}"

        try:
            url = self.publisher.post_clip(clip, text=caption)
            self.history.mark_posted(clip_id, url)
        except Exception as e:
            self.history.mark_failed(clip_id, f"post: {e}")
            log.error(f"Posting failed — clip is safe at {clip}. ({e})")
