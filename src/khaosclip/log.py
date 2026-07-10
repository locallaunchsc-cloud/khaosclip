"""Structured logging: rich console for the streamer, rotating file for debugging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

_configured = False


def setup_logging(level: str = "INFO", log_dir: Path = Path("logs")) -> None:
    global _configured
    if _configured:
        return
    log_dir.mkdir(exist_ok=True)

    console = RichHandler(rich_tracebacks=True, show_path=False, markup=True)
    console.setLevel(level.upper())

    file_handler = RotatingFileHandler(
        log_dir / "khaosclip.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )

    logging.basicConfig(level=logging.DEBUG, handlers=[console, file_handler], format="%(message)s")
    # Quiet noisy third parties
    for noisy in ("urllib3", "requests_oauthlib", "obsws_python"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
