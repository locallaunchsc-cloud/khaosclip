"""Trigger interface. A trigger's only job: notice a moment, publish an event."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from khaosclip.events import ClipEvent, EventBus


class Trigger(ABC):
    name: str = "trigger"

    def __init__(self, bus: EventBus):
        self.bus = bus
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def fire(self, mode: str = "retro", detail: str = "") -> None:
        self.bus.publish(ClipEvent(source=self.name, mode=mode, detail=detail))

    @abstractmethod
    def _run(self) -> None:
        """Blocking loop; must check self._stop periodically."""
