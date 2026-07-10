"""Application settings — validated, typed, loaded from .env / environment.

Every misconfiguration produces a clear, human error at startup instead of a
mysterious failure mid-stream. That's the whole point: you find out your
setup is broken BEFORE you go live, not during.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------ triggers
    # "aye clip that" -> retro clip of the last RETRO_SECONDS.
    # "aye clip this" -> opens a forward clip from this moment.
    # "aye clip that" / "aye end clip" while a forward clip is open -> closes it.
    retro_phrases: Annotated[list[str], NoDecode] = Field(
        default=["aye clip that"],
        description="Phrases that clip the last RETRO_SECONDS retroactively.",
    )
    start_phrases: Annotated[list[str], NoDecode] = Field(
        default=["aye clip this"],
        description="Phrases that open a forward clip from this moment.",
    )
    end_phrases: Annotated[list[str], NoDecode] = Field(
        default=["aye end clip", "aye stop clip"],
        description="Extra phrases that close an open forward clip.",
    )
    vosk_model_path: Path = Path("models/vosk-model-small-en-us-0.15")
    hotkey: str = Field(
        default="ctrl+alt+c",
        description="Global hotkey fallback trigger (requires [hotkey] extra).",
    )
    trigger_cooldown_seconds: float = Field(
        default=15.0,
        description="Minimum time between clips. Prevents accidental double-fires.",
    )

    # ------------------------------------------------------------ OBS
    obs_ws_host: str = "localhost"
    obs_ws_port: int = 4455
    obs_ws_password: str = ""
    obs_replay_dir: Path = Field(
        default=Path.home() / "Videos",
        description="Where OBS writes Replay Buffer files (Settings > Output > Recording path).",
    )

    # ------------------------------------------------------------ processing
    output_dir: Path = Path("clips")
    vertical: bool = True
    output_width: int = 1080
    output_height: int = 1920
    retro_seconds: int = Field(
        default=60, ge=5, le=140,
        description='How far back "aye clip that" reaches. OBS buffer must be >= this.',
    )
    max_forward_seconds: int = Field(
        default=90, ge=10, le=140,
        description="Forward clips auto-close at this length. OBS buffer must be >= this.",
    )
    watermark: str = "@KhaosClipper"
    captions: bool = False
    whisper_model: str = "base"

    # ------------------------------------------------------------ publishing
    auto_post: bool = True
    dry_run: bool = Field(
        default=False,
        description="Process clips but never post. For rehearsals.",
    )
    clip_tweet_text: str = "LIVE right now — clipped in real time 🎬"
    post_max_retries: int = 3

    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_secret: str = ""

    # ------------------------------------------------------------ misc
    log_level: str = "INFO"
    history_db: Path = Path("clips/history.db")

    # ------------------------------------------------------------ validators
    @field_validator("retro_phrases", "start_phrases", "end_phrases", mode="before")
    @classmethod
    def _split_phrases(cls, v):
        if isinstance(v, str):
            return [p.strip().lower() for p in v.split(",") if p.strip()]
        return [p.lower() for p in v]

    @field_validator("retro_seconds", "max_forward_seconds")
    @classmethod
    def _x_video_limit(cls, v: int) -> int:
        if v > 140:
            raise ValueError(
                "Clip length > 140s: X rejects videos over 140s for standard accounts."
            )
        return v

    # ------------------------------------------------------------ helpers
    def has_x_credentials(self) -> bool:
        return all([self.x_api_key, self.x_api_secret, self.x_access_token, self.x_access_secret])

    def missing_x_credentials(self) -> list[str]:
        pairs = {
            "X_API_KEY": self.x_api_key,
            "X_API_SECRET": self.x_api_secret,
            "X_ACCESS_TOKEN": self.x_access_token,
            "X_ACCESS_SECRET": self.x_access_secret,
        }
        return [k for k, v in pairs.items() if not v]

    def ensure_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history_db.parent.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton accessor so every module sees the same config."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def reset_settings() -> None:
    """Testing hook."""
    global _settings
    _settings = None
