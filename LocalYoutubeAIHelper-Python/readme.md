# Local YouTube AI Helper (Python)

[**Return to Project Root**](/README.md)

This Python-based tool extends the functionality of the overall project by providing a more flexible and configurable environment to handle larger videos and run more complex prompt workflows. It can:

- Download YouTube videos and extract their audio.
- Transcribe long audio files using OpenAI Whisper (either directly via OpenAI API or Azure OpenAI, if configured).
- Improve and refine transcripts by applying custom LLM prompts (including JSON-structured outputs).
- Process multiple prompts against the transcript to extract summaries, keywords, or any other structured/unstructured content.
- Update YouTube video metadata and upload improved subtitles directly to YouTube.

It is highly configurable through environment variables and configuration folders. The tool supports large files by chunking audio into manageable parts and merging results for transcripts over several hours of audio.

## Key Features

- **Flexible Downloading**: Download YouTube videos and convert them to audio in `.ogg` format using `yt-dlp` and `ffmpeg`.
- **Local and Remote Transcription**: Utilize the Whisper model via OpenAI's API or Azure OpenAI’s Whisper deployment to convert audio to text. Handles long-duration audio by splitting into chunks.
- **Improved Transcripts**: Automatically refine SRT subtitle files. The tool can apply custom LLM prompts to improve grammar, punctuation, or formatting of the transcript.
- **Custom Prompt Processing**: Apply a set of custom user-defined prompts (in `.txt` files) against the transcript to generate summaries, structured JSON outputs, or other information. The script supports a corresponding `.schema.json` file for each prompt, allowing it to produce validated JSON responses.
- **JSON-Structured Outputs**: Leverage JSON schema files to ensure standardized, machine-readable responses from the LLM.
- **Multiple Configuration Folders**: Each configuration folder can contain its own `llm_config.txt`, `whisper_config.txt`, and `prompts/` directory. This allows different videos or projects to use different settings and prompts easily.
- **YouTube Updates**: After processing, automatically update the YouTube video's metadata (title, description, tags) and upload improved subtitles. This requires a one-time OAuth flow with the YouTube Data API.
- **Environment-Based Settings**: Configure OpenAI or Azure OpenAI keys, default models, and other settings via `local.env` and configuration files. Supports both OpenAI API keys and Azure OpenAI credentials.

## Requirements

You will need the following tools and dependencies installed:

1. **Python**  
   Download Python from [here](https://www.python.org/downloads/) and ensure it's added to your system PATH.

   Verify installation:
   ```bash
   python --version
   ```

2. **FFmpeg** (for audio handling)  
   Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to your PATH.

   Verify installation:
   ```bash
   ffmpeg -version
   ```

3. **OpenAI and Additional Python Dependencies**  
   Install required Python packages via `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
   
   This includes:
   - `openai`
   - `requests`
   - `yt-dlp`
   - `srt`

   If you intend to use Azure OpenAI, ensure you have the corresponding environment variables set in `local.env`.

4. **Google API Credentials** (Optional, only if updating YouTube videos)  
   If you plan to run `--update-youtube` or use `update-youtube` mode, follow the instructions in the "Google API Credentials" section below.

## Setting Up Configuration

### 1. Cloning the Repository

```bash
git clone https://github.com/romanticdev/YoutubeAIHelper.git
cd YoutubeAIHelper/LocalYoutubeAIHelper-Python
```

### 2. Environment Variables

Create a `local.env` file in the same directory as `main.py` to store your API keys and default settings. For example:

```plaintext
# OpenAI / Azure OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here
USE_AZURE_OPENAI=false
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_DEPLOYMENT_NAME=
AZURE_API_VERSION=

# Model Settings
DEFAULT_MODEL=gpt-4o
MAX_TOKENS=16000
TEMPERATURE=0.7
TOP_P=1.0

# Default Folders and Settings
DEFAULT_OUTPUT_DIR=videos
DEFAULT_CONFIG_FOLDER=configurations/generic
```

- Set `USE_AZURE_OPENAI=true` and provide `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_DEPLOYMENT_NAME`, and `AZURE_API_VERSION` to use Azure OpenAI.
- Otherwise, just set `OPENAI_API_KEY` for OpenAI’s standard models.

### 3. Configuration Folders

Each configuration folder (e.g., `configurations/generic/`) can have:

- `llm_config.txt`  
  Contains model and API key (if needed) overrides, for example:
  ```plaintext
  model=gpt-3.5-turbo
  max_tokens=500
  openai_api_key=your_api_key_here
  ```

- `whisper_config.txt` (optional)  
  Can contain Whisper parameters like language, temperature, and prompt for improved SRT:
  ```plaintext
  language=en
  improve_srt_content=path_or_inline_prompt_here
  ```

- `prompts/` folder  
  Contains `.txt` and optional `.schema.json` files for each prompt. For example:
  ```plaintext
  summary.txt
  summary.schema.json
  keywords.txt
  ```

### 4. Prompts and JSON Schemas

You can define as many `.txt` prompt files as you like. For JSON output, include a `.schema.json` file named similarly to the prompt file (e.g., `summary.schema.json` for `summary.txt`). The tool will ensure the LLM’s response matches the schema.

### 5. Google API Credentials (For YouTube Updates)

To update YouTube metadata and upload subtitles directly:

1. Create a Google Cloud project and enable the YouTube Data API v3.
2. Obtain OAuth 2.0 credentials and download `client_secret_youtube.json`.
3. Place `client_secret_youtube.json` in the same directory as `main.py`.
4. The first time you run a command that updates YouTube, you’ll be prompted to do an OAuth flow. A `token.json` will be saved for subsequent uses.

## Supported Modes

The `main.py` script supports multiple modes to give you precise control over the process:

1. **full-process**:  
   Downloads, transcribes, improves SRT (if not disabled), runs prompts, and optionally updates YouTube metadata.  
   **Usage**:  
   ```bash
   python main.py --config-folder configurations/generic full-process <YouTube_URL_or_local_file> {<Another_YouTube_URL_or_local_file>...} [--update-youtube] [--disable-improve-srt]
   ```

2. **download**:  
   Only downloads the given YouTube videos as audio files.  
   **Usage**:  
   ```bash
   python main.py --config-folder configurations/generic download <YouTube_URL> {<Another_YouTube_URL>...}
   ```

3. **transcribe**:  
   Only transcribes audio files (e.g., `.ogg`, `.mp3`) in the specified folder.  
   **Usage**:  
   ```bash
   python main.py --config-folder configurations/generic transcribe <folder(s)>
   ```

4. **improve-srt**:  
   Improves existing SRT files using LLM prompts (defined in `whisper_config.txt`).  
   **Usage**:  
   ```bash
   python main.py --config-folder configurations/generic improve-srt <folder(s)>
   ```

5. **process-prompts**:  
   Runs the defined prompts on the existing transcripts, generating `.prompt.txt` or `.prompt.json` outputs.  
   **Usage**:  
   ```bash
   python main.py --config-folder configurations/generic process-prompts <folder(s)>
   ```

6. **update-youtube**:  
   Updates YouTube metadata and uploads subtitles from the processed folder.  
   **Usage**:  
   ```bash
   python main.py --config-folder configurations/generic update-youtube <folder(s)>
   ```

## Example Workflows

**Full Process Example**:

```bash
python main.py --config-folder configurations/generic full-process "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --update-youtube
```

This will:

1. Download the video and extract audio.
2. Transcribe it (splitting into chunks if needed).
3. Improve the SRT (if `improve_srt_content` is defined).
4. Execute all prompts found in `prompts/` directory.
5. Update the YouTube video metadata and upload the improved subtitles.

**Just Run Prompts**:

If you have already downloaded and transcribed a video, and you only want to run new prompts or schemas:

```bash
python main.py --config-folder configurations/generic process-prompts "./videos/YourVideoTitle"
```

## Troubleshooting

- **Dependencies Not Found**: Ensure `ffmpeg` and `yt-dlp` are installed and in your PATH.
- **API Key Issues**: Check `local.env` and `llm_config.txt` for correct keys.
- **Large Files**: The script automatically splits large audio files into chunks. Ensure enough disk space and check the logs for details.
- **YouTube Authentication**: If `update-youtube` fails, delete `token.json` and re-run the process to re-authenticate.

## Contributions

Contributions are welcome! Please fork the repository, create a branch for your changes, and submit a pull request. Any improvements, bug fixes, or new features are appreciated.
