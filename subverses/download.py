"""Download video and transcripts from YouTube"""

from pathlib import Path

import pysrt
import typer
from pathvalidate import sanitize_filename
from pytubefix import Stream, YouTube
from pytubefix.extract import video_id
from tqdm import tqdm
from youtube_transcript_api import YouTubeTranscriptApi

from subverses.config import Context
from subverses.transcribe import transcription_file_format


def _download(context: Context, stream: Stream, *, filename_prefix: str, progress=True):
    """Download a stream"""
    filename = Path(
        stream.get_file_path(
            output_path=context.data_dir.as_posix(), filename_prefix=filename_prefix
        )
    )
    if context.skip_existing and filename.exists():
        typer.echo(f"Skipping download of existing file: '{filename}'")
        return stream.get_file_path(
            output_path=context.data_dir.as_posix(),
            filename_prefix=filename_prefix,
        )

    progress = tqdm(total=stream.filesize, unit="B", unit_scale=True, desc=stream.title)

    def progress_function(stream, chunk, bytes_remaining):
        current = (stream.filesize - bytes_remaining) / stream.filesize
        total = stream.filesize
        progress.update(int((current - progress.n / total) * total))

    if progress:
        stream._monostate.on_progress = progress_function

    return stream.download(
        output_path=context.data_dir.as_posix(),
        filename_prefix=filename_prefix,
        skip_existing=context.skip_existing,
        max_retries=context.download_max_retries,
    )


def download_audio_and_video(context: Context):
    """Download a video from YouTube"""

    yt = YouTube(context.youtube_url)

    context.title = yt.title
    context.data_dir = Path(context.data_dir) / sanitize_filename(yt.title)

    # Download video and audio streams separately
    video_stream = yt.streams.order_by("resolution").last()

    context.video_filepath = _download(context, video_stream, filename_prefix="video_")

    # Download the lower quality as it transcribes well but is smaller
    audio_stream = yt.streams.filter(only_audio=True).first()

    context.audio_filepath = _download(context, audio_stream, filename_prefix="audio_")


def download_transcripts(context: Context):
    """Download transcripts for a video
    """
    if context.skip_existing and context.srt_path.exists():
        typer.echo(f"Skipping download of existing transcript file: '{context.srt_path}'")
        return context.srt_path.as_posix()

    vid_id = video_id(context.youtube_url)
    transcript = YouTubeTranscriptApi.get_transcript(vid_id, languages=[context.translate_from])

    subs = pysrt.SubRipFile()

    for entry in transcript:
        item = pysrt.SubRipItem(
            index=len(subs),
            start=pysrt.SubRipTime(seconds=entry["start"]),
            end=pysrt.SubRipTime(seconds=entry["start"] + entry["duration"]),
            text=entry["text"],
        )
        subs.append(item)

    subs.save(context.srt_path, encoding="utf-8")
    return context.srt_path.as_posix()
