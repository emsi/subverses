import subprocess

import typer

from subverses.config import Context


def render_ffmpeg(video_file_path, audio_file_path, subtitle_path, rendered_file_path):
    """Render the video, connecting audio and subtitles"""
    command = [
        "ffmpeg",
        "-i", video_file_path,
        "-i", audio_file_path,
        "-i", subtitle_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-c:s", "mov_text",
        "-map", "0",
        "-map", "1",
        "-map", "2",
        rendered_file_path,
    ]

    # Use Popen to initiate the ffmpeg process
    process = subprocess.Popen(command, universal_newlines=True)

    # Wait for the process to complete
    process.communicate()


def render(context: Context):
    """Render the video"""
    if not context.rendered_video_path.exists():
        typer.echo("Rendering video...")
        render_ffmpeg(
            context.video_path,
            context.audio_path,
            context.translated_srt_path,
            context.rendered_video_path,
        )
    else:
        typer.echo(f"Skipping rendering, file already exists: {context.rendered_video_path}")
