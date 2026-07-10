"""Global hotkey trigger — the reliable fallback when the room is loud.

Also what your mod/producer hits, or what you bind to a Stream Deck key.
"""

from __future__ import annotations

import time

from khaosclip.config import get_settings
from khaosclip.log import get_logger
from khaosclip.triggers.base import Trigger

log = get_logger("hotkey")


class HotkeyTrigger(Trigger):
    name = "hotkey"

    def _run(self) -> None:
        try:
            import keyboard
        except ImportError:
            log.warning("Hotkey deps missing. Install with: pip install \"khaosclip[hotkey]\"")
            return

        s = get_settings()
        # Mode "auto": the worker resolves it — closes an open forward clip,
        # otherwise fires a retro clip. One key, does the right thing.
        keyboard.add_hotkey(s.hotkey, lambda: self.fire(mode="auto", detail=s.hotkey))
        log.info(f"Hotkey armed: [bold]{s.hotkey}[/bold] (retro clip / close open clip)")
        while not self._stop.is_set():
            time.sleep(0.25)
