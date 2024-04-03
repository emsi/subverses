from pathlib import Path
from typing import Optional

import pycountry
import typer
from youtube_transcript_api import TranscriptsDisabled

from subverses.config import config
from subverses.download import download_audio_and_video, download_transcripts
from subverses.transcribe import transcribe_audio

app = typer.Typer(add_completion=False)


@app.command()
def main(
    # required positional argument
    youtube_url: str = typer.Argument(
        ...,
        help="URL of the YouTube video to download.",
    ),
    whisper_prompt: Optional[str] = typer.Option(
        None,
        help="Prompt for the whisper model. See https://cookbook.openai.com/examples/whisper_prompting_guide for more information.",
    ),
    translate_additional_prompt: Optional[str] = typer.Option(
        None,
        help="Additional prompt for the translation model.",
    ),
    whisper_model: str = typer.Option(
        "whisper-1",
        help="Transcription model name.",
    ),
    gpt_model: str = typer.Option(
        "gpt-3.5-turbo",
        help="Translation model name.",
    ),
    dont_transcribe_audio: bool = typer.Option(
        True,
        help="Fail if there is no manual transcript available.",
    ),
    force_transcription_from_audio: bool = typer.Option(
        False,
        help="Force transcription from audio file even if downloading manual transcript is possible.",
    ),
    start_transcription_segment: int = typer.Option(
        0,
        help="Start transcription from this segment number.",
    ),
    translate_from: str = typer.Option(
        "en",
        help="Translate from language. Use two letter ISO 639-1 country code.",
    ),
    translate_to: str = typer.Option(
        "Polish",
        help="Translate to language. Use full language name.",
    ),
    data_dir: Path = typer.Option(
        Path("./data"),
        help="Directory to store the downloaded data.",
    ),
    download_max_retries: int = typer.Option(
        2,
        help="Maximum number of retries for downloading.",
    ),
    skip_existing: bool = typer.Option(
        True,
        help="When downloading audio and video, skip if the file already exists.",
    ),
    min_silence_len_sec: int = typer.Option(
        2,
        help="The minimum length of silence to detect, when audio splitting is needed (in seconds).",
    ),
    silence_threshold: int = typer.Option(
        -30,
        help="The silence threshold used for audio splitting. It should be negative integer in range -60 to -5 dB.",
    ),
    verbose: bool = typer.Option(
        False,
        help="Verbose output.",
    ),
):
    """Reasoning questions generation tool"""
    try:
        config.initialize(**locals())
    except ValueError as exception:
        typer.echo(exception)
        raise typer.Abort()

    if pycountry.languages.get(alpha_2=translate_from) is None:
        raise typer.BadParameter("Invalid language code")

    download_audio_and_video(config.config)

    if not force_transcription_from_audio:
        try:
            config.config.srt_filepath = download_transcripts(config.config)
        except TranscriptsDisabled:
            typer.echo("There is no manual transcript available for this video.")
            if dont_transcribe_audio:
                raise typer.Abort()

    if force_transcription_from_audio or config.config.srt_filepath is None:
        config.config.srt_filepath = transcribe_audio(config.config)


if __name__ == "__main__":
    app(prog_name="subversed")
