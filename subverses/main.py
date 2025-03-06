import subprocess
from pathlib import Path
from typing import Optional

import pycountry
import typer

from subverses.config import config
from subverses.download import (
    get_yuoutube_stream,
    download_audio,
    download as do_download,
    download_video, get_local_stream,
)
from subverses.errors import Abort
from subverses.render import render_final_video
from subverses.transcribe import transcribe_audio
from subverses.translate import translate as do_translate, trabslate_subtitles

app = typer.Typer(add_completion=False)


def check_dependencies():
    """Check if the required dependencies are installed."""
    try:
        # Try to execute 'ffmpeg -version'
        result = subprocess.run(
            ["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        # If the command was successful, 'ffmpeg' is installed
        if result.returncode != 0:
            raise Exception()
        config.config.have_ffmpeg = True
    except Exception:
        # 'ffmpeg' is not installed if FileNotFoundError is raised
        typer.echo("WARNING: ffmpeg is not installed! Won't be able to render or split audio.")

    if config.config.openai_api_key is None:
        raise Abort(
            "OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable or add it to the .env file."
        )


@app.command()
def youtube(
    # required positional argument
    youtube_url: str = typer.Argument(
        ...,
        help="URL of the YouTube video to download.",
    ),
    download: bool = typer.Option(
        True,
        help="Download subtitles and streams. If --no-download it basically just checks streams and acts like dry run.",
    ),
    transcribe: bool = typer.Option(
        True,
        help="Transcribe the audio. If --no-transcribe and no subtitles are available it will end processing after download.",
    ),
    translate: bool = typer.Option(
        True,
        help="Translate the subtitles. If --no-translate it will end processing after download and transcription.",
    ),
    render: bool = typer.Option(
        True,
        help="Render the final video.",
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

    whisper_prompt: Optional[str] = typer.Option(
        None,
        help="Prompt for the whisper model. See https://cookbook.openai.com/examples/whisper_prompting_guide for more information.",
    ),
    whisper_model: str = typer.Option(
        "whisper-1",
        help="Transcription model name.",
    ),
    force_transcription_from_audio: bool = typer.Option(
        False,
        help="Force transcription from audio file even if downloading manual transcript is possible.",
    ),
    start_transcription_segment: int = typer.Option(
        0,
        help="Start transcription from this segment number.",
    ),
    min_silence_len_sec: int = typer.Option(
        2,
        help="The minimum length of silence to detect, when audio splitting is needed (in seconds).",
    ),
    silence_threshold: int = typer.Option(
        -30,
        help="The silence threshold used for audio splitting. It should be negative integer in range -60 to -5 dB.",
    ),
    translate_additional_prompt: Optional[str] = typer.Option(
        None,
        help="Additional prompt for the translation model.",
    ),
    gpt_model: str = typer.Option(
        "gpt-3.5-turbo",
        help="Translation model name.",
    ),
    translate_from: str = typer.Option(
        "en",
        help="Translate from language. Use two letter ISO 639-1 country code.",
    ),
    translate_to: str = typer.Option(
        "Polish",
        help="Translate to language. Use full language name.",
    ),
    verbose: bool = typer.Option(
        False,
        help="Verbose output.",
    ),
):
    """Process and translate YouTube videos"""
    try:
        config.initialize(**locals())
    except ValueError as exc:
        raise Abort(exc)
    context = config.config

    check_dependencies()

    if pycountry.languages.get(alpha_2=translate_from) is None:
        raise typer.BadParameter("Invalid language code")

    # check if youtube_url is an url or a local path
    if not youtube_url.startswith("http"):
        get_local_stream(context)
    else:
        get_yuoutube_stream(context)

    if not download:
        return

    if do_download(context) == "audio":
        if not transcribe:
            raise Abort("No subtitles available and transcribe is disabled.")
        transcribe_audio(context)

    if translate:
        do_translate(context)
    else:
        return

    if render:
        if not context.have_ffmpeg:
            raise Abort("Cannot render video without ffmpeg.")
        if not context.local_stream:
            download_video(context)
        if not context.audio_filepath:
            download_audio(context)
        render_final_video(context)


@app.command()
def srt(
    # required positional argument
    srt_path: Path = typer.Argument(
        ...,
        help="Path to the SRT file to translate.",
    ),
    additional_instruction: Optional[str] = typer.Option(
        None,
        help="Additional prompt instruction for the translation model. E.g. 'Use family-friendly language.', 'Translate Geogie as Gigi', etc.",
    ),
    gpt_model: str = typer.Option(
        "gpt-3.5-turbo",
        help="Translation model name.",
    ),
    translate_from: str = typer.Option(
        "en",
        help="Translate from language. Use two letter ISO 639-1 country code.",
    ),
    translate_to: str = typer.Option(
        "Polish",
        help="Translate to language. Use full language name.",
    ),
    verbose: bool = typer.Option(
        False,
        help="Verbose output.",
    ),
):
    """Process and translate SRT subtitle files"""
    stub_arguments = {
        "youtube_url": "",
        "download": False,
        "transcribe": False,
        "translate": False,
        "render": False,
        "data_dir": Path(),
        "download_max_retries": 0,
        "skip_existing": False,
        "whisper_prompt": None,
        "whisper_model": "",
        "force_transcription_from_audio": False,
        "start_transcription_segment": 0,
        "min_silence_len_sec": 0,
        "silence_threshold": -30,
        "translate_additional_prompt": None,
        "gpt_model": gpt_model,
        "translate_from": translate_from,
        "translate_to": translate_to,
        "verbose": verbose,
    }
    try:
        config.initialize(**{**stub_arguments})
    except ValueError as exc:
        raise Abort(exc)

    check_dependencies()

    if pycountry.languages.get(alpha_2=translate_from) is None:
        raise typer.BadParameter("Invalid language code")

    if not srt_path.exists():
        raise typer.BadParameter(f"SRT file not found: {srt_path}")

    trabslate_subtitles(
        srt_path=srt_path,
        target_language=translate_to,
        openai_client=config.config.openai_client,
        model=gpt_model,
        extra_prompt_instruction=additional_instruction,
        verbose=verbose,
    )


def main():
    """Entry point for the application."""
    try:
        app(prog_name="subverses")
    except Abort as exc:
        typer.echo(exc, err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
