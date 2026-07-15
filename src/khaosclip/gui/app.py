"""NameiT desktop app entrypoint.

First launch (no .env yet): setup wizard — auto-detect OBS, mic check, done.
Every launch after: straight to the tray, armed and listening.

This is what the packaged .exe runs. `nameit-app` also works from a dev
checkout: pip install -e ".[gui]" && nameit-app
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    os.environ.setdefault("GUI_MODE", "true")

    from khaosclip.gui.wizard import needs_setup, run_wizard

    if needs_setup():
        if not run_wizard():
            return 1  # closed the wizard without finishing

    # settings may have just been written by the wizard — rebuild them
    from khaosclip.config import reset_settings
    reset_settings()

    from khaosclip.gui.tray import TrayApp
    TrayApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
