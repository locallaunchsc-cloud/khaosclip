"""Entry script PyInstaller freezes into NameiT.exe.

Sets the working directory to the per-user data dir so clips/history/logs land
somewhere writable (never inside Program Files), then starts the desktop app.
"""

import os
import sys


def _find_bundled_ffmpeg() -> None:
    """Make the bundled ffmpeg.exe visible on PATH."""
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(sys.executable)
        os.environ["PATH"] = bundle + os.pathsep + os.environ.get("PATH", "")


def main() -> int:
    _find_bundled_ffmpeg()

    from khaosclip.config import app_data_dir

    data = app_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    os.chdir(data)  # relative paths (clips/, models/) resolve here

    # models ship inside the bundle — point Vosk at them if not overridden
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(sys.executable)
        os.environ.setdefault(
            "VOSK_MODEL_PATH",
            os.path.join(bundle, "models", "vosk-model-small-en-us-0.15"),
        )

    from khaosclip.gui.app import main as app_main
    return app_main()


if __name__ == "__main__":
    sys.exit(main())
