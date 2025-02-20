import subprocess
import sys
from pathlib import Path
from typing import List

import typer

from subverses.config import Context

# As per https://platform.openai.com/docs/guides/speech-to-text
# "File uploads are currently limited to 25 MB and the following input
# file types are supported: mp3, mp4, mpeg, mpga, m4a, wav, and webm."
max_clip_size = 24.5 * 1024**2  # 25 MB


class AudioParseError(Exception):
    """Audio parse error."""


class SilenceDetectionError(AudioParseError):
    """Silence detection error."""


class AudioSplitError(AudioParseError):
    """Audio split error."""


class SegmentTooLongError(AudioParseError):
    """Segment too long error."""


def split_file_format(audio_file_path: Path, split_prefix=".splits_"):
    """Return the path used to construct the split file name."""
    return audio_file_path.parent / (split_prefix + audio_file_path.name)


def n_split_file(audio_file_path: Path, split_no: int, split_prefix=".splits_") -> Path:
    """Return the nth split file name."""
    return split_file_format(audio_file_path, split_prefix=split_prefix).with_suffix(
        f".{split_no:03d}" + audio_file_path.suffix
    )


def detect_silence_splits_with_ffmpeg(context: Context) -> List[float]:
    """Detect silence in an audio file using ffmpeg.

    :return: A list of floats, each containing the midpoint of a silence.
    """
    command = [
        "ffmpeg",
        "-i",
        context.audio_filepath,
        "-af",
        f"silencedetect=noise={context.silence_threshold}dB:duration={context.min_silence_len_sec}",
        "-f",
        "null",
        "-",
    ]
    typer.echo(" ".join(command))
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    # Use communicate() to capture output
    stdout_output, stderr_output = process.communicate()

    # Check for errors
    if stderr_output:
        raise SilenceDetectionError(stderr_output)
    if process.returncode != 0:
        raise AudioParseError(stdout_output)

    return [
        float(line.split("silence_start: ")[1]) + context.min_silence_len_sec / 2
        for line in stdout_output.split("\n")
        if "silence_start" in line
    ]


def split_audio_with_ffmpeg(context: Context, segments: List[float]):
    """Split an audio file using ffmpeg.

    :param context: The context.
    :param segments: A list of floats, each containing the split points.
    :return: A list of paths to the split audio files.
    """
    command = [
        "ffmpeg",
        "-i",
        context.audio_path,
        "-f",
        "segment",
        "-segment_times",
        ",".join(str(s) for s in segments),
        "-c",
        "copy",
        split_file_format(context.audio_path).with_suffix(".%03d" + context.audio_path.suffix),
    ]

    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
    )

    # Use communicate() to capture output
    stdout_output, stderr_output = process.communicate()

    # Check for errors
    if stderr_output:
        raise AudioSplitError(stderr_output)
    if process.returncode != 0:
        raise AudioParseError(stdout_output)


def concat_audio_segments(context: Context, input_files: List[Path], output_file: Path) -> Path:
    """Concat back audio segments into chunks of less than max_clip_size.

    :param context: The context.
    :param output_file: The output file path object.
    :param input_files: A list of paths to the split audio files.
    :return: The path to the concatenated audio file.
    """
    # Create the input string expected by ffmpeg for the concat demuxer
    input_string = "\n".join(f"file '{file.name}'" for file in input_files)
    concat_filename = context.data_dir / "concat_files.txt"
    # write the input string to a file
    with open(concat_filename, "w") as f:
        f.write(input_string)

    command = [
        "ffmpeg",
        "-y",
        "-safe",
        "0",
        "-f",
        "concat",
        "-i",
        concat_filename.name,
        "-c",
        "copy",
        output_file.name,
    ]

    process = subprocess.Popen(
        command,
        cwd=context.data_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    # Pass the input_string to ffmpeg via stdin and get the output
    output, _ = process.communicate(input=input_string)

    # Use communicate() to capture output
    stdout_output, stderr_output = process.communicate()

    concat_filename.unlink()

    # Check for errors
    if stderr_output:
        raise AudioParseError(stderr_output)
    if process.returncode != 0:
        raise AudioParseError(stdout_output)

    # cleanup
    for file in input_files:
        file.unlink()

    return output_file


def get_segment_sizes(context: Context, segments: int):
    """Return the size of each segment in seconds."""
    return [n_split_file(context.audio_path, i).stat().st_size for i in range(segments)]


def get_sub_max_segments(context: Context, segments: int) -> List[List[int]]:
    """Return segments of the audio file that are less than or equal to the max_clip_size.

    Returns list of lists of segment numbers such that the sum of the sizes of the segments in each
    list does not exceed max_clip_size."""

    segment_sizes = get_segment_sizes(context, segments)

    current_sum = 0
    segment_groups = []  # List to store the segment groups
    current_group = []  # List to store the current group of segments

    for i, size in enumerate(segment_sizes):
        if size > max_clip_size:
            raise SegmentTooLongError(f"Segment {i} is too large.")
        if current_sum + size > max_clip_size:
            segment_groups.append(current_group)
            current_group = [i]  # Start a new group with the current segment
            current_sum = size  # Reset current_sum for the next group of segments
        else:
            current_group.append(i)
            current_sum += size

    if current_group:
        segment_groups.append(current_group)

    return segment_groups


def recombine_segments(context: Context, segments: List[float]) -> List[tuple[Path, float]]:
    """Recombine segments into the least number of files smaller than max_clip_size.

    :param context: The context.
    :param segments: The number of segments.
    :return: A list of tuples, each containing the path to the
        recombined segment and the start time of the segment.
    """
    segment_groups = get_sub_max_segments(context, len(segments) + 1)
    start_times = [0.0] + segments

    return [
        (
            concat_audio_segments(
                context,
                [n_split_file(context.audio_path, segment) for segment in segment_group],
                n_split_file(context.audio_path, i, split_prefix=".recombined_"),
            ),
            start_times[segment_group[0]],
        )
        for i, segment_group in enumerate(segment_groups)
    ]


def extract_audio(context):
    """Extract audio from a video file"""

    if context.skip_existing and context.audio_path.exists():
        typer.echo(f"Skipping extraction of audio file: '{context.audio_filepath}'")
        return

    command = [
        "ffmpeg",
        "-i",
        context.video_filepath,
        "-vn",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "56k",
        "-ac",
        "1",
        context.audio_filepath,
    ]
    typer.echo(" ".join(command))

    process = subprocess.Popen(
        command, stdout=sys.stdout, stderr=sys.stderr, universal_newlines=True
    )
    # Wait for the process to complete
    process.wait()

    # Check for errors
    if process.returncode != 0:
        raise AudioParseError(
            "FFmpeg process failed with exit code: {}".format(process.returncode))
