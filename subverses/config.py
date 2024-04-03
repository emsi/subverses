from pathlib import Path

from openai import NOT_GIVEN, NotGiven
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Context(BaseSettings):
    """Application context."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # CLI options
    youtube_url: str
    whisper_prompt: str | None
    translate_additional_prompt: str | None
    whisper_model: str
    gpt_model: str
    dont_transcribe_audio: bool
    force_transcription_from_audio: bool
    start_transcription_segment: int
    translate_from: str = "en"
    translate_to: str = "Polish"
    data_dir: Path
    download_max_retries: int
    skip_existing: bool
    min_silence_len_sec: int
    silence_threshold: int
    verbose: bool

    # .env only options
    openai_api_key: str | None = None
    openai_organization: str | None = None
    openai_base_url: str | None = None
    whisper_openai_timeout: float | None | NotGiven = NOT_GIVEN
    whisper_openai_max_retries: int | None = 2

    # internal state
    title: str | None = None
    audio_filepath: str | None = None
    video_filepath: str | None = None
    srt_filepath: str | None = None

    @field_validator("silence_threshold")
    def check_silence_threshold(cls, v):
        """Check the silence threshold."""
        if not -60 <= v <= -5:
            raise ValueError("silence_threshold must be between -60 and -5")
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
