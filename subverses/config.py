from pathlib import Path

import openai
from openai import NOT_GIVEN, NotGiven
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytubefix import YouTube


class Context(BaseSettings):
    """Application context."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # CLI options
    youtube_url: str
    # processing steps
    download: bool
    transcribe: bool
    translate: bool
    render: bool
    # download options
    data_dir: Path
    download_max_retries: int
    skip_existing: bool
    # transcription options
    whisper_prompt: str | None
    whisper_model: str
    force_transcription_from_audio: bool
    start_transcription_segment: int
    min_silence_len_sec: int
    silence_threshold: int
    # translation options
    translate_additional_prompt: str | None
    gpt_model: str
    translate_from: str = "en"
    translate_to: str = "Polish"
    # debug options
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
    have_ffmpeg: bool = False
    youtube_stream: YouTube | None = None
    local_stream: bool = False

    @field_validator("silence_threshold")
    def check_silence_threshold(cls, v):
        """Check the silence threshold."""
        if not -60 <= v <= -5:
            raise ValueError("silence_threshold must be between -60 and -5")
        return v

    @property
    def audio_path(self) -> Path:
        """Get the audio path."""
        if self.audio_filepath is None:
            raise ValueError("Audio file path not set")
        return Path(self.audio_filepath)

    @property
    def video_path(self) -> Path:
        """Get the video path."""
        if self.video_filepath is None:
            raise ValueError("Video file path not set")
        return Path(self.video_filepath)

    @property
    def rendered_video_path(self) -> Path:
        """Get the rendered video path."""
        # remove the "video_" prefix from the video file name
        return self.video_path.with_name(self.video_path.name[6:]).with_suffix(".mp4")

    @property
    def srt_path(self) -> Path:
        """Get the srt path."""
        if self.srt_filepath is None:
            raise ValueError("SRT file path not set")
        return Path(self.srt_filepath)

    @property
    def translated_srt_path(self) -> Path:
        """Get the translated srt path."""
        return self.srt_path.with_name(f"{self.srt_path.stem}_{self.translate_to}.srt")

    @property
    def openai_client(self):
        """Returns the initialized OpenAI client."""
        return openai.OpenAI(
            api_key=self.openai_api_key,
            organization=self.openai_organization,
            base_url=self.openai_base_url,
            timeout=self.whisper_openai_timeout,
            max_retries=self.whisper_openai_max_retries,
        )


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
