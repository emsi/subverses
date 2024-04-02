from pathlib import Path

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Configuration for application."""

    youtube_url: str
    title: str | None = None
    translate_from: str = "en"
    translate_to: str = "Polish"
    data_dir: Path
    download_max_retries: int
    skip_existing: bool

    audio_path: str | None = None
    video_path: str | None = None
    srt_path: str | None = None


class Config:
    """Config singleton."""

    _config: AppConfig | None = None

    @staticmethod
    def initialize(**kwargs):
        """Initialize the config."""
        if Config._config is None:
            Config._config = AppConfig(**kwargs)
        else:
            raise ValueError("Config already set")

    @property
    def config(self) -> AppConfig:
        """Get the config."""
        if Config._config is None:
            raise ValueError("Config not set")
        return Config._config


config: Config = Config()
