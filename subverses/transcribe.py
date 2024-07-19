from pathlib import Path

import pysrt
import typer
from tqdm import tqdm

from subverses.audio_parse import (
    detect_silence_splits_with_ffmpeg,
    split_audio_with_ffmpeg,
    max_clip_size,
    recombine_segments,
)
from subverses.config import config, Context
from subverses.errors import Abort


def transcription_file_format(audio_file_path: Path):
    """Return the path used to construct the transcription file name."""
    return audio_file_path.with_suffix(".srt")


def n_split_transcription_file(audio_file_path: Path, split_no: int) -> Path:
    """Return the nth split file name."""
    return audio_file_path.with_suffix(f".{split_no:03d}" + ".srt")


def split_audio(context: Context) -> list[tuple[Path, float]]:
    """Split audio file

    returns: list of tuples, each containing the path to the recombined
        segment and the start time of the segment.
    """
    typer.echo("Detecting silence splits...")
    silence_splits = detect_silence_splits_with_ffmpeg(context)
    typer.echo(f"Detected {len(silence_splits) + 1} segments.")
    if len(silence_splits) == 0:
        raise Abort("No silence detected.")
    if len(silence_splits) > 1000:
        raise Abort("Too many segments detected.")
    typer.echo("Splitting audio file...")
    split_audio_with_ffmpeg(config.config, silence_splits)
    typer.echo("Recombining segments to the least possible number of files...")
    return recombine_segments(context, silence_splits)


def transcribe_audio(context: Context) -> Path:
    """Transcribe audio file"""
    typer.echo("Transcribing audio...")
    audio_file_size = context.audio_path.stat().st_size
    if context.srt_path.exists() and not context.force_transcription_from_audio:
        typer.echo(f"Skipping transcription of existing file: '{context.srt_path}'")
        return context.srt_path
    if max_clip_size < audio_file_size:
        typer.echo(
            f"Audio file is too large: {audio_file_size:.1f} bytes. Max size is {max_clip_size // 1024**2} MB."
        )
        audio_segment_splits = split_audio(context)

        transcription = ""
        progress = tqdm(
            total=len(audio_segment_splits), unit="segments", desc="Transcribing audio segments"
        )
        for segment_no, (segment_path, segment_offset) in enumerate(audio_segment_splits):
            transcription += transcribe_file(
                context,
                segment_path,
                segment_no=segment_no,
                segment_offset=segment_offset,
            )
            progress.update(1)

        # write the transcription file
        with open(context.srt_path, "w") as f:
            f.write(transcription)
    else:
        transcribe_file(context, context.audio_path)

    return context.srt_path


def _transcribed_file(transcription_path, segment_offset):
    with open(transcription_path) as subs_file:
        return shift_subtitles(subs_file.read(), segment_offset)


def transcribe_file(
    context: Context,
    audio_segment_path: Path,
    *,
    segment_no: int | None = None,
    segment_offset: float = 0.0,
) -> str:
    """Transcribe an audio file."""

    if segment_no is not None:
        transcription_path = transcription_file_format(audio_segment_path)
    else:
        transcription_path = context.srt_path

    if segment_no is not None and segment_no < context.start_transcription_segment:
        return _transcribed_file(transcription_path, segment_offset)

    if transcription_path.exists() and not context.force_transcription_from_audio:
        return _transcribed_file(transcription_path, segment_offset)

    with open(audio_segment_path, "rb") as audio_file:
        transcription = context.openai_client.audio.transcriptions.create(
            model=context.whisper_model,
            file=audio_file,
            prompt=context.whisper_prompt,
            response_format="srt",
            language=context.translate_from,
        )
        subs = pysrt.from_string(transcription)

    if segment_no is not None and segment_no > 0:
        subs = shift_subtitles(transcription, segment_offset)

    transcription = "\n".join(str(sub) for sub in subs) + "\n"

    with open(transcription_path, "w") as subs_file:
        subs_file.write(transcription)

    return transcription


def shift_subtitles(srt_txt: str, shift: float) -> str:
    """Shift all subtitles by a given amount of seconds"""
    subs = pysrt.from_string(srt_txt)
    subs.shift(seconds=shift)
    return subs
