import subprocess
from pathlib import Path
from typing import List

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


def split_file_format(audio_file_path: Path):
    """Return the path used to construct the split file name."""
    return audio_file_path.parent / (".splits_" + audio_file_path.name)


def n_split_file(audio_file_path: Path, split_no: int) -> Path:
    """Return the nth split file name."""
    return split_file_format(audio_file_path).with_suffix(
        f".{split_no:03d}" + audio_file_path.suffix
    )


def detect_silence_splits_with_ffmpeg(context: Context) -> List[float]:
    """Detect silence in an audio file using ffmpeg.

    :return: A list of floats, each containing the midpoint of a silence.
    """
    command = [
        "ffmpeg",
        "-i",
        context.audio_path,
        "-af",
        f"silencedetect=noise={context.silence_threshold}dB:duration={context.min_silence_len_sec}",
        "-f",
        "null",
        "-",
    ]
    process = subprocess.Popen(
        command,
        cwd=context.data_dir,
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


def concat_audio_segments(context: Context, input_files: List[Path], output_file: Path):
    """Concat back audio segments into chunks of less than max_clip_size.

    :param context: The context.
    :param input_files: A list of paths to the split audio files.
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
        if file != output_file:
            file.unlink()


def get_segment_sizes(context: Context, segments: int):
    """Return the size of each segment in seconds."""
    return [n_split_file(context.audio_path, i).stat().st_size for i in range(segments)]


def get_sub_max_segments(context: Context, segments: int):
    """Return segments of the audio file that are less than or equal to the max_clip_size.

    Returns list of lists of segment numbers such that the sum of the sizes of the segments in each
    list does not exceed max_clip_size."""

    segment_sizes = get_segment_sizes(context, segments)

    current_sum = 0
    segment_groups = []  # List to store the segment groups
    current_group = []  # List to store the current group of segments

    for i, size in enumerate(segment_sizes):
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


def recombine_segments(context: Context, segments: int):
    """Recombine segments into the least number of files smaller than max_clip_size."""
    segment_groups = get_sub_max_segments(context, segments)
    for i, segment_group in enumerate(segment_groups):
        concat_audio_segments(
            context,
            [n_split_file(context.audio_path, segment) for segment in segment_group],
            n_split_file(context.audio_path, i),
        )
