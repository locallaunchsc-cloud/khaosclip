"""Clip events and the queue that decouples triggers from the worker.

Any number of triggers (voice, hotkey, future chat) push ClipEvents onto one
queue; a single worker consumes them. Triggers never block on ffmpeg or the
X API, and a burst of triggers can't stack five encodes on a streaming PC.
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClipEvent:
    source: str                      # "voice" | "hotkey" | "chat" | "manual"
    mode: str = "retro"              # "retro" | "start" | "end"
    detail: str = ""                 # e.g. the phrase that matched
    triggered_at: float = field(default_factory=time.time)


class EventBus:
    def __init__(self, maxsize: int = 8):
        self._q: queue.Queue[ClipEvent] = queue.Queue(maxsize=maxsize)

    def publish(self, event: ClipEvent) -> bool:
        """Non-blocking publish. Returns False if the queue is full."""
        try:
            self._q.put_nowait(event)
            return True
        except queue.Full:
            return False

    def next(self, timeout: float | None = None) -> ClipEvent | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None
