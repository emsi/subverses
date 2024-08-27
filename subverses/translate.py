import re
import textwrap
from copy import deepcopy
from itertools import chain
from pathlib import Path
from typing import Dict, List

import joblib
import pysrt
import typer
from tqdm import tqdm

from subverses.config import Context


def word_wrap(text, line_length=60):
    """Wraps text to a specified line length"""
    # replace all " \\n " with "\n" to avoid word_wrap splitting on those
    text = text.replace(" \\n ", "\n")
    return "\n".join(textwrap.wrap(text, width=line_length))


def parse_block(block):
    """Parse a single subtitle block"""
    # if block consists of just newline we're at the end of the file
    if block == "\n" or block == "":
        return None
    try:
        index, timecodes, *text = block.split("\n")
        # convert list of text lines back to a single string with newlines
        text = " ".join(text)

        # parse start and end times
        start_time, end_time = timecodes.split(" --> ")

        return {"text": text, "start_time": start_time, "end_time": end_time}
    except ValueError:
        typer.echo(f"""Error parsing subtitles. Invalid block "{block}" """, err=True)


def srt_parse(srt_text: str) -> List[Dict[str, str]]:
    """Parse a srt file

    Parse srt file and return a list of dicts containing the timecode
    and text of each subtitle.
    """

    # split by subtitle blocks
    blocks = re.split(r"\n\n", srt_text)

    # parse blocks using a list comprehension, filtering out None results
    subtitles = [sub for block in blocks if (sub := parse_block(block)) is not None]

    return subtitles


def srt_dump(*, srt_list, srt_filename):
    """Dump subtitles to a srt file"""
    with open(srt_filename, "w") as file:
        for index, subtitle in enumerate(srt_list, start=1):
            file.write(
                f"""{index}\n{subtitle["start_time"]} --> {subtitle["end_time"]}\n{subtitle["text"]}\n\n"""
            )
        file.write("\n")


def concatenate_srt_list(srt_list):
    """Concatenate a list of srt dicts into a single srt string"""
    return "\n\n".join([f"{i}: {sub['text']}" for i, sub in enumerate(srt_list)])


def replace_translation(srt_list: List[Dict[str, str]], new_texts: List[str]):
    """Replace text in a list of srt dicts"""

    srt_list = deepcopy(srt_list)
    for text in new_texts:
        number, text = re.findall(r"(\d+):\s*(.*)", text)[0]
        number = int(number)
        srt_list[number]["text"] = word_wrap(text)

    return srt_list


def shift_subtitles(srt_txt: str, shift: float) -> str:
    """Shift all subtitles by a given amount of seconds"""
    subs = pysrt.from_string(srt_txt)
    subs.shift(seconds=shift)
    return subs


def split_into_chunks(lst, chunk_size, overlap):
    """Split a list into overlapping chunks"""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks = []
    i = 0  # starting index

    while i < len(lst):
        chunks.append(lst[i : i + chunk_size])
        if i + chunk_size >= len(lst):  # if we're at the last chunk
            break
        i += chunk_size - overlap

    return chunks


def _find_overlap(chunk1, chunk2, overlap):
    """Find the overlap between two chunks"""
    if not chunk1:
        return chunk2

    # we're guaranteed that the overlap is >=2
    for i in range(overlap):
        if chunk1[-overlap + i]["text"] == chunk2[i]["text"]:
            return chunk1[: -overlap + i] + chunk2[i:]

    print(f"*** No overlap found:\n{chunk1}\n**** \n{chunk2}")
    return chunk1 + chunk2[overlap:]


def join_overlapping_chunks(chunks, overlap):
    """Join overlapping chunks"""

    if overlap <= 1:
        remaining_chunks = [chunk[overlap:] for chunk in chunks[1:]]
        return list(chain.from_iterable(chunks[0:1] + remaining_chunks))

    joined_chunks = []
    for chunk in chunks:
        joined_chunks = _find_overlap(joined_chunks, chunk, overlap)

    return joined_chunks


def translate_srt(
    context: Context,
    *,
    srt_path: Path,
    target_language: str,
    extra_prompt_instruction="",
    model: str,
    temperature=0.0,
    chunk_size=8,
    overlap=3,
):
    """Translate an SRT file

    Translation happens in overlapping chunks of `chunk_size` lines,
    with `overlap` lines of overlap. This helps maintain consistent
    translation.
    """
    if overlap > chunk_size:
        raise ValueError("Overlap size cannot be larger than chunk size")
    if overlap < 0:
        raise ValueError("Overlap size cannot be negative")

    # work in progress file
    wip_file = srt_path.with_suffix(".wip.joblib")
    wip = None
    if wip_file.exists():
        wip = joblib.load(wip_file)

    with open(srt_path, "r", encoding="utf-8") as srt_file:
        str_list = srt_parse(srt_file.read())

    srt_chunks = split_into_chunks(str_list, chunk_size, overlap)

    progressbar = tqdm(desc="Translating dialog lines", total=len(srt_chunks))

    def chunk_callback():
        progressbar.update()

    messages = []
    translated_chunks = []
    for i, chunk in enumerate(srt_chunks):
        # rewind to last saved progress
        if wip and i <= wip["i"]:
            translated_chunks = wip["translated_chunks"]
            messages = wip["messages"]
            chunk_callback()
            continue

        chunk_str = concatenate_srt_list(chunk)
        messages += translation_message(
            chunk_str,
            target_language=target_language,
            extra_prompt_instruction=extra_prompt_instruction,
        )

        response = translate_chunk(
            context,
            messages=messages[-3:],  # let the model see previous request and response
            target_language=target_language,
            model=model,
            temperature=temperature,
        )

        translated_chunk_str = find_translated_text(response)
        translated_list = re.split(r"\n\n", translated_chunk_str)
        translated_chunks += [replace_translation(chunk, translated_list)]

        messages += [
            {
                "role": "assistant",
                "content": response,
            }
        ]
        chunk_callback()

        # dump progress
        joblib.dump(
            {"i": i, "translated_chunks": translated_chunks, "messages": messages}, wip_file
        )
    # wip_file.unlink()
    return join_overlapping_chunks(translated_chunks, overlap)


def find_translated_text(translated_text):
    """Find the translated text in the response"""
    match = re.search(r"'''\n?(.*?)'''", translated_text, re.DOTALL)
    if match:
        return match.group(1)
    return translated_text


def translate_chunk(context: Context, *, messages, model, temperature, target_language):
    """Translate a chunk of text"""

    if context.verbose:
        print(messages)
    messages = translation_messages(messages, target_language=target_language)

    response = context.openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=2048,
    )

    return response.choices[0].message.content


def translation_message(text_chunk, *, target_language, extra_prompt_instruction):
    """Construct the translation message"""
    return [
        {
            "role": "user",
            "content": f"""
'''
{text_chunk}
'''
Please translate above text to {target_language}. 
Output ONLY translated text!
{extra_prompt_instruction}
""",
        }
    ]


def translation_messages(messages: List[Dict[str, str]], *, target_language: str):
    """Construct the translation messages"""
    return [
        {
            "role": "system",
            "content": f"""You are a world class professional translator specialized in translating to {target_language}.
Please maintain the exact text structure (lines of text, empty lines, line breaks, etc.) and do not add or remove any text!
Make sure the line numbers are unchanged!
Do not skip any line, even if you would have to output empty line, although try to translate in a way that does not result in empty lines.
Stick to {target_language} grammar and punctuation rules.""",
        }
    ] + messages


def translate(context: Context):
    """Translate an SRT file"""

    if not context.skip_existing or not context.translated_srt_path.exists():
        typer.echo(f"Translating {context.srt_path} to {context.translated_srt_path}")

        srt_list = translate_srt(
            context,
            srt_path=context.srt_path,
            target_language=context.translate_to,
            model=context.gpt_model,
        )
        srt_dump(srt_list=srt_list, srt_filename=context.translated_srt_path)
    else:
        typer.echo(f"Translated SRT file already exists: {context.translated_srt_path}")
        return
