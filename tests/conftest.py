import os
import sys
from pathlib import Path

import pytest

# Make src importable without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from khaosclip.config import reset_settings  # noqa: E402


@pytest.fixture(autouse=True)
def clean_settings(tmp_path, monkeypatch):
    """Every test gets fresh settings pointed at a temp workspace."""
    reset_settings()
    monkeypatch.chdir(tmp_path)
    # Prevent a developer's real .env from leaking into tests
    for k in list(os.environ):
        if k.startswith(("X_", "OBS_", "KHAOS")):
            monkeypatch.delenv(k, raising=False)
    yield
    reset_settings()
