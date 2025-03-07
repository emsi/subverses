"""Download video and transcripts from YouTube"""

from pathlib import Path

import pysrt
import typer
from pathvalidate import sanitize_filename
from pytubefix import Stream, YouTube
from pytubefix.extract import video_id
from tqdm import tqdm
from youtube_transcript_api import YouTubeTranscriptApi

from subverses.audio_parse import extract_audio
from subverses.config import Context
from subverses.errors import Abort


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

    with tqdm(
        total=stream.filesize,
        unit="B",
        unit_scale=True,
        desc=f"Downloading {filename_prefix[:-1]}",
    ) as progress:

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


def get_local_stream(context: Context):
    """Get a local file stream"""
    local_path = Path(context.youtube_url).expanduser().resolve()

    if not local_path.exists():
        raise Abort(f"File not found: {context.youtube_url}")

    context.video_filepath = local_path.as_posix()
    context.data_dir = Path(context.data_dir) / local_path.stem
    context.srt_filepath = (context.data_dir / local_path.with_suffix(".srt").name).as_posix()
    context.audio_filepath = (
        context.data_dir
        / local_path.with_name("audio_" + local_path.stem).with_suffix(".mp3").name
    ).as_posix()
    context.local_stream = True
    context.data_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Data directory: {context.data_dir} - all files will be saved here.")


def get_yuoutube_stream(context: Context):
    """Get a YouTube stream"""

    try:
        yt = context.youtube_stream = YouTube(context.youtube_url)
    except Exception as exc:
        raise Abort(
            f"Could not get YouTube stream {context.youtube_url}\nError: {exc}",
        )

    context.title = yt.title
    context.data_dir = Path(context.data_dir) / sanitize_filename(yt.title)
    typer.echo(f"Data directory: {context.data_dir} - all files will be saved here.")

    context.srt_filepath = Path(
        yt.streams[0].get_file_path(output_path=context.data_dir.as_posix())
    ).with_suffix(".srt")


def download_audio(context: Context):
    """Download audio from YouTube"""
    audio_stream = context.youtube_stream.streams.filter(only_audio=True).first()
    context.audio_filepath = _download(context, audio_stream, filename_prefix="audio_")


def download_video(context: Context):
    """Download video from YouTube"""

    video_stream = context.youtube_stream.streams.order_by("resolution").last()
    context.video_filepath = _download(context, video_stream, filename_prefix="video_")


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


def overlapping_subs(transcript):
    """Check if there are overlapping subtitles"""
    prev_end_time = 0
    for segment in transcript:
        end_time = segment["start"] + segment["duration"]
        if segment["start"] < prev_end_time:
            raise Abort("Overlapping subtitles detected")
        prev_end_time = end_time


def download_subtitles(context: Context):
    """Download subtitles for a video"""
    if context.skip_existing and context.srt_path.exists():
        typer.echo(f"Skipping download of existing transcript file: '{context.srt_path}'")
        return context.srt_path.as_posix()

    vid_id = video_id(context.youtube_url)
    transcript = YouTubeTranscriptApi.get_transcript(vid_id, languages=[context.translate_from])
    overlapping_subs(transcript)

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


def download(context: Context):
    """Download necessary files"""
    if context.local_stream:
        if context.have_ffmpeg:
            extract_audio(context)
            return "audio"
        else:
            raise Abort("FFmpeg is not installed.")

    if not context.force_transcription_from_audio:
        try:
            if download_subtitles(context):
                return "subtitles"
        except Exception:
            typer.echo("There is no manual transcript available for this video.", err=True)
    try:
        if context.have_ffmpeg:
            download_audio(context)
            return "audio"
        else:
            raise Abort("FFmpeg is not installed.")
    except Exception as exc:
        raise Abort(f"Could not download audio from YouTube\nError: {exc}")
