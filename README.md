# Subverses

Subverses is a simple CLI application to translate YouTube video subtitles to a different language. It uses the YouTube API to download the subtitles and the OpenAI API to translate them.
If no subtitles are available for the video, the application will try to transcribe the audio and then translate it.

## Installation

You can install Subverses directly from GitHub:

```bash
pip install git+https://github.com/your-username/subverses.git
```

Or install it in development mode:

```bash
git clone https://github.com/your-username/subverses.git
cd subverses
pip install -e .
```

## Quickstart

After installation, you can use the `subverses` command directly:

```bash
subverses youtube https://www.youtube.com/watch?v=...
```

Or translate an existing subtitle file:

```bash
subverses srt path/to/subtitle.srt
```

The YouTube command will download and create files in a dedicated subdirectory under `data` directory.
For your convenience, the subdirectory will be named after the video title.

## Commandline options

```
./subverses  --help
Usage: subverses [OPTIONS] YOUTUBE_URL

  Reasoning questions generation tool

Arguments:
  YOUTUBE_URL  URL of the YouTube video to download.  [required]

Options:
  --whisper-prompt TEXT           Prompt for the whisper model. See https://co
                                  okbook.openai.com/examples/whisper_prompting
                                  _guide for more information.
  --translate-additional-prompt TEXT
                                  Additional prompt for the translation model.
  --whisper-model TEXT            Transcription model name.  [default:
                                  whisper-1]
  --gpt-model TEXT                Translation model name.  [default:
                                  gpt-3.5-turbo]
  --dont-transcribe-audio / --no-dont-transcribe-audio
                                  Fail if there is no manual transcript
                                  available.  [default: dont-transcribe-audio]
  --force-transcription-from-audio / --no-force-transcription-from-audio
                                  Force transcription from audio file even if
                                  downloading manual transcript is possible.
                                  [default: no-force-transcription-from-audio]
  --start-transcription-segment INTEGER
                                  Start transcription from this segment
                                  number.  [default: 0]
  --translate-from TEXT           Translate from language. Use two letter ISO
                                  639-1 country code.  [default: en]
  --translate-to TEXT             Translate to language. Use full language
                                  name.  [default: Polish]
  --data-dir PATH                 Directory to store the downloaded data.
                                  [default: data]
  --download-max-retries INTEGER  Maximum number of retries for downloading.
                                  [default: 2]
  --skip-existing / --no-skip-existing
                                  When downloading audio and video, skip if
                                  the file already exists.  [default: skip-
                                  existing]
  --min-silence-len-sec INTEGER   The minimum length of silence to detect,
                                  when audio splitting is needed (in seconds).
                                  [default: 2]
  --silence-threshold INTEGER     The silence threshold used for audio
                                  splitting. It should be negative integer in
                                  range -60 to -5 dB.  [default: -30]
  --verbose / --no-verbose        Verbose output.  [default: no-verbose]
  --help                          Show this message and exit.
```

## Configuration

The following options can be set int the .env configuration file (please use CAPITAL_LETTERS for the option names in the .env file):
```
    # CLI options
    youtube_url: str
    whisper_prompt: str | None
    translate_additional_prompt: str | None
    whisper_model: str
    gpt_model: str
    dont_transcribe_audio: bool
    force_transcription_from_audio: bool
    start_transcription_segment: int
    translate_from: str = "en"
    translate_to: str = "Polish"
    data_dir: Path
    download_max_retries: int
    skip_existing: bool
    min_silence_len_sec: int
    silence_threshold: int
    verbose: bool

    # .env only options
    openai_api_key: str | None = None
    openai_organization: str | None = None
    openai_base_url: str | None = None
    whisper_openai_timeout: float | None | NotGiven = NOT_GIVEN
    whisper_openai_max_retries: int | None = 2
```

For example to set the OPENAI_API_KEY, create a .env file in the root directory of the project and add the following line:
```
OPENAI_API_KEY=sk-...
```

To set the `translate_to` option to "German" add the following line to the .env file:
```
TRANSLATE_TO=German
```

Check the output of the `subverses --help` command for the full list of options.