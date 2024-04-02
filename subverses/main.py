from pathlib import Path

import pycountry
import typer
from youtube_transcript_api import TranscriptsDisabled

from subverses.config import config
from subverses.download import download, download_transcripts
from subverses.transcribe import transcribe_audio

app = typer.Typer(add_completion=False)


@app.command()
def main(
    # required positional argument
    youtube_url: str = typer.Argument(
        ...,
        help="URL of the YouTube video to download",
    ),
    force_transcription_from_audio: bool = typer.Option(
        False,
        help="Force transcription from audio file instead of downloading manual transcript",
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
        help="Directory to store the downloaded data",
    ),
    download_max_retries: int = typer.Option(
        2,
        help="Maximum number of retries for downloading",
    ),
    skip_existing: bool = typer.Option(
        True,
        help="When downloading audio and video, skip if the file already exists",
    ),
    min_silence_len_sec: int = typer.Option(
        2,
        help="The minimum length of silence to detect, when audio splitting is needed",
    ),
    silence_threshold: int = typer.Option(
        -30,
        help="The silence threshold used for audio splitting. It should be negative integer in range -60 to -5 dB",
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

    download(config.config)
    try:
        config.config.srt_filepath = download_transcripts(config.config)
    except TranscriptsDisabled:
        typer.echo("There is no manual transcript available for this video.")
    if force_transcription_from_audio or config.config.srt_filepath is None:
        transcribe_audio(config.config)


if __name__ == "__main__":
    app(prog_name="subversed")

