from pathlib import Path

import pysrt
import typer
from pathvalidate import sanitize_filename
from pytube import Stream, YouTube
from pytube.extract import video_id
from tqdm import tqdm
from youtube_transcript_api import YouTubeTranscriptApi

from subverses.config import config


def _download(stream: Stream, *, filename_prefix: str, progress=True):
    """Download a stream"""
    if config.config.skip_existing and (
        filename := stream.get_file_path(
            output_path=config.config.data_dir.as_posix(),
            filename_prefix=filename_prefix,
        )
    ):
        typer.echo(f"Skipping download of existing file: {filename}")
        return stream.get_file_path(
            output_path=config.config.data_dir.as_posix(),
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
        output_path=config.config.data_dir.as_posix(),
        filename_prefix=filename_prefix,
        skip_existing=config.config.skip_existing,
        max_retries=config.config.download_max_retries,
    )


def download(yt_url: str):
    """Download a video from YouTube and return the file name"""

    yt = YouTube(yt_url)

    config.config.title = yt.title
    config.config.data_dir = Path(config.config.data_dir) / sanitize_filename(yt.title)

    # Download video and audio streams separately
    video_stream = yt.streams.get_highest_resolution()

    config.config.video_path = _download(video_stream, filename_prefix="video_")

    # Download the lower quality as it transcribes well but is smaller
    audio_stream = yt.streams.filter(only_audio=True).first()

    config.config.audio_path = _download(audio_stream, filename_prefix="audio_")


def download_transcripts(yt_url: str):
    """Download transcripts for a video"""
    filename = config.config.data_dir / f"{config.config.translate_from}.srt"
    config.config.srt_path = filename.as_posix()
    if config.config.skip_existing and filename.exists():
        typer.echo("Skipping download of existing transcript")
        config.config.srt_path = filename
        return

    vid_id = video_id(yt_url)
    transcript = YouTubeTranscriptApi.get_transcript(
        vid_id, languages=[config.config.translate_from]
    )

    subs = pysrt.SubRipFile()

    for entry in transcript:
        item = pysrt.SubRipItem(
            index=len(subs),
            start=pysrt.SubRipTime(seconds=entry["start"]),
            end=pysrt.SubRipTime(seconds=entry["start"] + entry["duration"]),
            text=entry["text"],
        )
        subs.append(item)

    subs.save(config.config.data_dir / f"{config.config.translate_from}.srt", encoding="utf-8")

