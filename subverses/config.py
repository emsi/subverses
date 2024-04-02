from pathlib import Path

from pydantic import BaseModel, Extra, field_validator


class Context(BaseModel):
    """Application context."""

    class Config:
        """Pydantic config."""
        extra = Extra.forbid

    youtube_url: str
    force_transcription_from_audio: bool
    translate_from: str = "en"
    translate_to: str = "Polish"
    data_dir: Path
    download_max_retries: int
    skip_existing: bool
    min_silence_len_sec: int
    silence_threshold: int

    title: str | None = None
    audio_filepath: str | None = None
    video_filepath: str | None = None
    srt_filepath: str | None = None

    @field_validator('silence_threshold')
    def check_silence_threshold(cls, v):
        """Check the silence threshold."""
        if not -60 <= v <= -5:
            raise ValueError('silence_threshold must be between -60 and -5')
        return v

    @property
    def audio_path(self) -> Path:
        """Get the audio path."""
        return Path(self.audio_filepath)

    @property
    def video_path(self) -> Path:
        """Get the video path."""
        return Path(self.video_filepath)

    @property
    def srt_path(self) -> Path:
        """Get the srt path."""
        return Path(self.srt_filepath)


class Config:
    """Config singleton."""

    _config: Context | None = None

    @staticmethod
    def initialize(**kwargs):
        """Initialize the config."""
        if Config._config is None:
            Config._config = Context(**kwargs)
        else:
            raise ValueError("Config already set")

    @property
    def config(self) -> Context:
        """Get the config."""
        if Config._config is None:
            raise ValueError("Config not set")
        return Config._config


config: Config = Config()
