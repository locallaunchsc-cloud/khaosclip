"""System tray app — NameiT lives by the clock, not in a terminal.

Icon states:  green = armed and listening · gray = stopped · red = problem
Right-click:  Start/Stop listening · Open clips folder · Settings · Quit

The agent (triggers + worker) runs on daemon threads exactly like the CLI
`khaosclip run` path — this is only a different skin over the same engine.
"""

from __future__ import annotations

import subprocess
import sys
import threading

from khaosclip.config import env_file_path, get_settings
from khaosclip.log import get_logger

log = get_logger("tray")


def _make_icon_image(color: str):
    """Simple filled-circle icon, drawn in code so we ship zero image assets."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=color)
    d.polygon([(26, 22), (26, 42), (44, 32)], fill="white")  # play triangle
    return img


COLORS = {"armed": "#4caf50", "stopped": "#757575", "error": "#f44336"}


class TrayApp:
    def __init__(self):
        self.agent_thread: threading.Thread | None = None
        self.stop_flag = threading.Event()
        self.state = "stopped"
        self.icon = None

    # ------------------------------------------------------------ agent
    def _agent_loop(self):
        """Same wiring as `khaosclip run`, headless."""
        try:
            from khaosclip.capture.obs import OBSCapture, OBSError
            from khaosclip.events import EventBus
            from khaosclip.triggers.hotkey import HotkeyTrigger
            from khaosclip.triggers.wakeword import make_voice_trigger
            from khaosclip.worker import ClipWorker

            obs = OBSCapture()
            try:
                obs.connect()
            except OBSError as e:
                log.error(str(e))
                self._set_state("error")
                return

            bus = EventBus()
            triggers = [make_voice_trigger(bus), HotkeyTrigger(bus)]
            for t in triggers:
                t.start()

            self._set_state("armed")
            worker = ClipWorker(bus, obs)
            while not self.stop_flag.is_set():
                worker.run_once(timeout=0.5)

            for t in triggers:
                t.stop()
        except Exception as e:  # never let the tray die silently
            log.error(f"Agent crashed: {e}")
            self._set_state("error")
        else:
            self._set_state("stopped")

    def _set_state(self, state: str):
        self.state = state
        if self.icon:
            self.icon.icon = _make_icon_image(COLORS.get(state, "#757575"))
            self.icon.title = f"NameiT — {state}"

    # ------------------------------------------------------------ actions
    def toggle(self, *_):
        if self.state == "armed":
            self.stop_flag.set()
        else:
            self.stop_flag.clear()
            self.agent_thread = threading.Thread(target=self._agent_loop, daemon=True)
            self.agent_thread.start()

    def open_clips(self, *_):
        s = get_settings()
        folder = s.output_dir
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def open_settings(self, *_):
        path = env_file_path()
        if sys.platform == "win32":
            subprocess.Popen(["notepad", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-t", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def quit(self, icon, *_):
        self.stop_flag.set()
        icon.stop()

    # ------------------------------------------------------------ run
    def run(self):
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: "Stop listening" if self.state == "armed" else "Start listening",
                self.toggle, default=True,
            ),
            pystray.MenuItem("Open clips folder", self.open_clips),
            pystray.MenuItem("Settings", self.open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit),
        )
        self.icon = pystray.Icon(
            "NameiT", _make_icon_image(COLORS["stopped"]), "NameiT — stopped", menu
        )
        # auto-arm on launch: double-clicking the desktop icon should mean "go"
        self.toggle()
        self.icon.run()
