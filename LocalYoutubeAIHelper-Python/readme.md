# Local YouTube AI Helper (Python)

[**Return to Project Root**](/README.md)

This Python-based tool extends the functionality of the overall project by providing a more flexible and configurable environment to handle larger videos, run more complex prompt workflows, **interact with live YouTube chat**, and transcribe live audio. It can:

												  
																												   
																									
																															   
																				  

- **Download YouTube videos and extract their audio**.
- **Transcribe long audio files** using OpenAI Whisper (either via OpenAI API or Azure OpenAI, if configured).
- **Improve and refine transcripts** by applying custom LLM prompts (including JSON-structured outputs).
- **Process multiple prompts** against the transcript to extract summaries, keywords, or other structured/unstructured content.
- **Update YouTube video metadata** and upload improved subtitles directly to YouTube.
- **Generate discussion starters** from your existing YouTube streams, pulling in context from transcripts and real-time news.
- **Host a live chatbot** to respond automatically in YouTube Live Chat.
- **Perform real-time local transcription** of your microphone feed (for personal use, e.g., auto-creating transcripts from your microphone input).

## Key Features

1. **Flexible Downloading**  
   - Download YouTube videos and convert them to audio in `.ogg` format using `yt-dlp` and `ffmpeg`.
																																											
																																																																												   
																														  
																																																																				   
																																																				   
																																																				

2. **Local and Remote Transcription**  
   - Utilize the Whisper model via OpenAI’s API or Azure OpenAI’s Whisper deployment to convert audio to text.  
   - Handles long-duration audio by splitting it into manageable chunks.

3. **Improved Transcripts**  
   - Automatically refine SRT subtitle files.  
   - Apply custom LLM prompts to improve grammar, punctuation, and formatting.

4. **Custom Prompt Processing**  
   - Apply a set of custom user-defined prompts (in `.txt` files) to the transcript to generate summaries, structured JSON outputs, etc.  
   - Supports `.schema.json` to enforce a validated JSON output.

5. **Discussion Starters**  
   - Use `discussion_starters.py` to generate conversation prompts based on your last few YouTube streams.  
   - Integrate real-time news (both AI-focused and general) into your conversation prompts.

6. **Live Chat Bot**  
   - `livechatbot.py` can connect to your active YouTube Live Chat.  
   - Leverages GPT-based function calls (like `get_latest_ai_news`, `get_last_stream_context`, etc.) to provide dynamic, context-aware responses.  
   - Auto-filters whether to respond or skip user messages with a message-filter prompt.

7. **YouTube Updates**  
   - Automatically update your YouTube video's metadata (title, description, tags) and upload improved subtitles directly to YouTube.  
   - Requires a one-time OAuth flow with the YouTube Data API.

8. **Environment-Based Settings**  
   - Configure OpenAI or Azure OpenAI keys, default models, and other settings via `local.env` and configuration files.  
   - Supports both OpenAI API keys and Azure OpenAI credentials.

9. **Deepseek Model Instructions**
For instructions on using the **deepseek‑r1‑distill‑qwen‑7b** model with LM Studio , please refer to the [Deepseek Readme](configurations/deepseek/readme.md).

10. **Ollama Integration**
For instructions on using local models with Ollama, please refer to the [Ollama Readme](configurations/ollama/readme.md).

## Requirements

You will need the following tools and dependencies installed:

1. **Python**  
   Download Python from [here](https://www.python.org/downloads/) and ensure it’s added to your system `PATH`.

   Verify installation:
   ```bash
   python --version
   ```

2. **FFmpeg** (for audio handling)  
   Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to your `PATH`.

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
   - `sounddevice` (for real-time mic or audio playback)
   - `serpapi` and `worldnewsapi` (if using the news extraction features)
   - `google-auth-oauthlib` + `google-api-python-client` (if updating or connecting to YouTube)

4. **Google API Credentials** (Optional, only if updating or interacting with YouTube)  
   If you plan to run `--update-youtube` or use the live chat features, follow the instructions in the **Google API Credentials** section below.

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

# News Keys
SERP_API_KEY=YourSerpApiKeyHere
WORLD_NEWS_API_KEY=YourWorldNewsApiKeyHere

# Default Folders and Settings
DEFAULT_OUTPUT_DIR=videos
DEFAULT_CONFIG_FOLDER=configurations/generic
AUDIO_BITRATE=12k
```

- Set `USE_AZURE_OPENAI=true` and provide `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_DEPLOYMENT_NAME`, and `AZURE_API_VERSION` to use Azure OpenAI.
- Otherwise, just set `OPENAI_API_KEY` for the standard OpenAI models.

### 3. Configuration Folders

Each configuration folder (e.g., `configurations/generic/`) can have:

- **`llm_config.txt`**  
  Contains model and API key (if needed) overrides, for example:
  ```plaintext
  model=gpt-3.5-turbo
  max_tokens=500
  openai_api_key=your_api_key_here
  ```

- **`whisper_config.txt`** (optional)  
  Can contain Whisper parameters like language, temperature, and prompt for improved SRT:
  ```plaintext
  language=en
  temperature=0.7
  improve_srt_content=path_or_inline_prompt_here
  ```

- **`prompts/` folder**  
  Contains `.txt` and optional `.schema.json` files for each prompt. For example:
  ```plaintext
  summary.txt
  summary.schema.json
  keywords.txt
  ```

### 4. Prompts and JSON Schemas

You can define as many `.txt` prompt files as you like. For JSON output, include a `.schema.json` file named similarly to the prompt file (e.g., `summary.schema.json` for `summary.txt`). The tool will ensure the LLM’s response matches the schema.

### 5. Google API Credentials (For YouTube Updates or Live Chat)

To update YouTube metadata, upload subtitles, or post messages in live chat:

1. Create a Google Cloud project and enable the YouTube Data API v3.
2. Obtain OAuth 2.0 credentials and download `client_secret_youtube.json`.
3. Place `client_secret_youtube.json` in the same directory as `main.py`.
4. The first time you run a command that updates or accesses YouTube live chat, you’ll be prompted for an OAuth flow. A `token.json` will be saved for subsequent uses.

## Usage Overview

You can run multiple scripts for different tasks. The main entry point is **`main.py`**, which supports several modes. Additionally, specialized scripts like **`livechatbot.py`** or **`live_transcriber.py`** handle live scenarios.

					  
																												   
			   
		  
### 1. `main.py` Modes
	  

- **full-process**  
  Downloads, transcribes, improves SRT (if not disabled), runs prompts, and optionally updates YouTube metadata.  
  **Usage**:  
  ```bash
  python main.py \
      --config-folder configurations/generic \
      full-process \
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
      --update-youtube
  ```

- **download**  
  Only downloads the specified YouTube videos as audio files.  
			   
  ```bash
  python main.py \
      --config-folder configurations/generic \
      download <YouTube_URL> [...more URLs...]
  ```

- **transcribe**  
  Only transcribes audio files (e.g., `.ogg`, `.mp3`) in the specified folder.  
			   
  ```bash
  python main.py \
      --config-folder configurations/generic \
      transcribe <folder1> <folder2> ...
  ```

- **improve-srt**  
  Improves existing SRT files using LLM prompts (defined in `whisper_config.txt`).  
			   
  ```bash
  python main.py \
      --config-folder configurations/generic \
      improve-srt <folder1> <folder2> ...
  ```

- **process-prompts**  
  Runs the defined prompts on the existing transcripts, generating `.prompt.txt` or `.prompt.json` outputs.  
  ```bash
  python main.py \
      --config-folder configurations/generic \
      process-prompts <folder1> <folder2> ...
  ```

- **update-youtube**  
  Updates YouTube metadata and uploads subtitles from the processed folder.  
  ```bash
  python main.py \
      --config-folder configurations/generic \
      update-youtube <folder>
  ```

- **generate-discussion-starters**  
  Builds a set of discussion prompts based on your last few live streams and optionally includes relevant AI/general news.  
  ```bash
  python main.py \
      --config-folder configurations/generic \
      generate-discussion-starters
  ```
  This uses `discussion_starters.py` under the hood.

### 2. `livechatbot.py` (Live YouTube Chat Bot)

This script connects to your active YouTube Live Chat, listens for incoming user messages, and responds automatically with GPT-based logic. It can:

- Filter out messages that do not require a response (via a `message_filter.txt`).
- Call “functions” (like `get_latest_ai_news`, `get_last_stream_context`, etc.) to generate more context-aware answers.
- Post messages back to the live chat.

**Quick Start**:

1. **Ensure** you have valid OAuth credentials `client_secret_youtube.json` near `main.py`
2. Make sure you have created `LocalYoutubeAIHelper-Python\configurations\aibot` folder. It will use this folder to pu `token.json`for you chatbot account to authenticate with YouTube API.
3. **Adjust** the `message_filter.txt` and `chatbot_response.txt` in your `aibot` config folder to define the system instructions and message-filter logic.
4. You can add to `stream_info.txt` in your `aibot` config folder to define the stream and host information.
5. **Run**:
   ```bash
   python livechatbot.py <optional_video_id>
   ```
   - If `<optional_video_id>` is provided, it attempts to connect to that specific live stream.
   - Otherwise, it looks for any currently active live stream on chatbot channel.
   - Tip: Right now chatbot don't reply to the messages from the same account. So, you can use another account to test the chatbot.

Once running, it will:

- Fetch new chat messages every few seconds.
- Decide if the bot should respond (based on the `message_filter` logic).
- Generate a response from GPT.  
- Optionally call any “function” it requests (like retrieving news, last stream transcripts or current transcript).
- Post the final text back to the live chat.

> **Tip**: Modify `livechatbot_functions.py` to add or remove function calls that GPT can use.

### 3. `live_transcriber.py` (Real-Time Local Audio Transcriber)

The `live_transcriber.py` script captures audio from your **microphone** in real time and passes it to a local Whisper model (`whisper` from OpenAI’s whisper library, loaded on your machine). It then:

- Accumulates short chunks of audio (e.g., ~5 seconds).
- Transcribes them using the **local** Whisper model (not over the network).
- Appends the text to a `.txt` transcript file in the `transcripts/` folder.
- Prints the transcribed text to your console in real time.
- TIP: the whisper model could be much faster if you have a GPU with CUDA support. In  that case you can use 'turbo' model.

**Quick Start**:
```bash
python live_transcriber.py
```
- By default, it uses the `small` Whisper model loaded from the `whisper` Python library.
- It will create or append to a time-stamped file in `transcripts/`.
- Press **Ctrl+C** to stop.

> **Note**: This is different from transcribing via the OpenAI/Whisper API. This script relies on your local CPU/GPU resources. If you prefer the cloud-based approach, use the main pipeline with `full-process` or `transcribe` modes.  

### 4. Discussion Starters

The `discussion_starters.py` module is designed to:

1. Look up your **last N completed live streams**.
2. **Ensure** their transcripts are downloaded or transcribed locally.
3. Optionally retrieve real-time news (AI or general).
4. Build a comprehensive prompt that references both the current and previous stream transcripts.
5. Generate “conversation starter” questions or prompts using GPT.

**How to use**:
- Via the main script:
  ```bash
  python main.py --config-folder configurations/generic generate-discussion-starters
  ```
- Or from within your own Python code:
  ```python
  from discussion_starters import DiscussionStarters
  ds = DiscussionStarters(config, whisper_config, number_of_streams=3)
  questions = ds.generate_questions()
  print(questions)
  ```

### 5. Using Local Models with Ollama

To run local LLMs (e.g., Llama 2) on your machine and connect them through an OpenAI-compatible interface, you can use [**Ollama**](https://ollama.com). The setup steps are described in [**configurations/ollama/readme.md**](configurations/ollama/readme.md).

Once configured, simply ensure your `local.env` file is pointing to Ollama’s local endpoint:

```env
OPENAI_API_KEY=dummy-ollama-key
OPENAI_BASE_URL=http://localhost:11411/v1
USE_AZURE_OPENAI=false
DEFAULT_MODEL=phi42
```

Then, the rest of the commands (e.g., \`python main.py full-process\`) will transparently use your local Ollama model.

### 6. Using LM Studio for Local LLMs

You can also use LM Studio to host local LLMs and connect to them via the Local YouTube AI Helper. For instructions on setting up LM Studio and connecting to it, refer to the [**configurations/deepseek/readme.md**](configurations/deepseek/readme.md).

## Example Workflows

**Full Process Example**:

```bash
python main.py \
    --config-folder configurations/generic \
    full-process "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
    --update-youtube
```

This will:

1. Download the video and extract audio.
2. Transcribe it (splitting into chunks if needed).
3. Improve the SRT (if `improve_srt_content` is defined).
4. Execute all prompts found in `prompts/` directory.
5. Update the YouTube metadata and upload improved subtitles.

**Just Run Prompts**:

If you already downloaded and transcribed a video, and you only want to run new prompts or schemas:

```bash
python main.py \
    --config-folder configurations/generic \
    process-prompts "./videos/YourVideoTitle"
```

## Troubleshooting & Tips

- **Dependencies Not Found**: Ensure `ffmpeg` and `yt-dlp` are installed and in your PATH.  
- **API Key Issues**: Check `local.env` and `llm_config.txt` for correct keys and ensure you’re not mixing Azure vs. OpenAI.  
- **Large Files**: The script automatically splits large audio files. Ensure you have enough disk space and check the logs for chunk info.  
- **YouTube Authentication**: If `update-youtube` or live chat fails, delete `token.json` and re-run to re-authenticate.  
- **Using `livechatbot.py`**: Make sure your system prompts (`chatbot_response.txt`, `message_filter.txt`) are well-defined so the bot doesn’t spam the chat.  
- **Local vs. Cloud Whisper**: `live_transcriber.py` uses local Whisper; the main pipeline uses the OpenAI or Azure Whisper API. Choose whichever suits your setup.

## Contributions

Contributions are welcome! Please fork the repository, create a branch for your changes, and submit a pull request. Any improvements, bug fixes, or new features are appreciated.
