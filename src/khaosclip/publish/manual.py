"""Manual share mode — $0 posting, no API, no keys, no OAuth.

Instead of posting through the X API (which costs per post and needs
credentials), manual mode preps everything for a one-drag human post:

  1. Copies the caption to the clipboard
  2. Opens X's compose window with the caption pre-filled (free web intent)
  3. Reveals the clip file in the file explorer

The streamer (or their mod) drags the mp4 into the compose box and hits
Post. ~8 seconds of work, zero cost, zero credentials, and they see
exactly what goes out under their name.
"""

from __future__ import annotations

import platform
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

from khaosclip.log import get_logger

log = get_logger("manual")

INTENT_URL = "https://x.com/intent/post?text={text}"


def copy_to_clipboard(text: str) -> bool:
    """Cross-platform clipboard, no extra dependencies."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run("clip", input=text.encode("utf-16-le"), check=True)
        elif system == "Darwin":
            subprocess.run("pbcopy", input=text.encode(), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode(), check=True)
        return True
    except Exception as e:
        log.debug(f"Clipboard copy failed: {e}")
        return False


def reveal_in_explorer(path: Path) -> None:
    """Open the file manager with the clip selected."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["explorer", "/select,", str(path.resolve())])
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(path.resolve())])
        else:
            subprocess.Popen(["xdg-open", str(path.parent.resolve())])
    except Exception as e:
        log.debug(f"Could not open file explorer: {e}")


def manual_share(clip: Path, caption: str) -> str:
    """Prep a zero-cost manual post. Returns a status string."""
    copied = copy_to_clipboard(caption)

    intent = INTENT_URL.format(text=urllib.parse.quote(caption))
    try:
        webbrowser.open(intent)
    except Exception as e:
        log.warning(f"Couldn't open browser: {e}")

    reveal_in_explorer(clip)

    log.info("[bold]READY TO POST[/bold] — compose window is open with your caption"
             + (" (also on your clipboard)" if copied else "")
             + f". Drag in [bold]{clip.name}[/bold] and hit Post.")
    return "manual://prepared"
