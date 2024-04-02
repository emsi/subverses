import typer

from subverses.audio_parse import (
    detect_silence_splits_with_ffmpeg,
    split_audio_with_ffmpeg,
    max_clip_size,
    recombine_segments,
)
from subverses.config import config, Context


def split_audio(context: Context):
    """Split audio file"""
    typer.echo("Detecting silence splits...")
    silence_splits = detect_silence_splits_with_ffmpeg(context)
    typer.echo(f"Detected {len(silence_splits) + 1} segments.")
    if len(silence_splits) == 0:
        raise typer.Abort("No silence detected.")
    if len(silence_splits) > 1000:
        raise typer.Abort("Too many segments detected.")
    typer.echo("Splitting audio file...")
    split_audio_with_ffmpeg(config.config, silence_splits)

    recombine_segments(context, len(silence_splits) + 1)


def transcribe_audio(context: Context):
    """Transcribe audio file"""
    audio_file_size = context.audio_path.stat().st_size
    if max_clip_size < audio_file_size:
        typer.echo(
            f"Audio file is too large: {audio_file_size:.1f} bytes. Max size is {max_clip_size // 1024**2} MB."
        )
        split_audio(context)
