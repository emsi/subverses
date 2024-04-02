from pathlib import Path

import pycountry
import typer
from youtube_transcript_api import TranscriptsDisabled

from subverses.config import config
from subverses.download import download, download_transcripts

app = typer.Typer(add_completion=False)


@app.command()
def main(
    # required positional argument
    youtube_url: str = typer.Argument(
        ...,
        help="URL of the YouTube video to download",
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
):
    """Reasoning questions generation tool"""
    config.initialize(**locals())

    if pycountry.languages.get(alpha_2=translate_from) is None:
        raise typer.BadParameter("Invalid language code")

    download(youtube_url)
    try:
        download_transcripts(youtube_url)
    except TranscriptsDisabled:
        typer.echo("There is no manual transcript available for this video.")


if __name__ == "__main__":
    app(prog_name="subversed")
