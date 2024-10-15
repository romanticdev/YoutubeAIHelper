# YouTube AI Helper

This project automates the process of downloading a YouTube video as an MP3, transcribing it using Whisper, and processing the transcript with an LLM (Language Learning Model) through OpenAI’s API. This is ideal for extracting useful information, summaries, or insights from YouTube video transcripts.

## Features

- Downloads YouTube videos as MP3.
- Automatically transcribes the audio using Whisper.
- Executes custom LLM prompts on the transcript for further processing.
- Easily configurable with different prompt setups.

## Requirements

Before you can run the batch file, make sure you have the following installed and available in your system’s PATH:

1. [yt-dlp](https://github.com/yt-dlp/yt-dlp) – for downloading YouTube videos as MP3 files.
2. [Whisper](https://github.com/openai/whisper) – for transcribing audio files.
3. [curl](https://curl.se/download.html) – for making API requests to OpenAI's API.
4. PowerShell – for script execution.

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/romanticdev/YoutubeAIHelper.git
cd YoutubeAIHelper
```

### 2. Install Required Tools

Make sure `yt-dlp`, Whisper, and `curl` are installed and available on your PATH.

- [Install yt-dlp](https://github.com/yt-dlp/yt-dlp#installation)
- [Install Whisper](https://github.com/openai/whisper#installation)
- [Install curl](https://curl.se/download.html)

### 3. Obtain OpenAI API Key

To use the LLM feature, you'll need an OpenAI API key.

1. Go to [OpenAI API](https://platform.openai.com/account/api-keys).
2. Copy your API key.
3. Add the API key to the `llm_config.txt` file in your configuration directory.

Example `llm_config.txt` file:

```
model=gpt-3.5-turbo
max_tokens=500
openai_api_key=your_api_key_here
```

### 4. Configure Prompts

- Define the prompts you want to use for the LLM inside the `configurations/prompts/` folder. Create `.txt` files containing the prompt instructions. Each prompt will be applied to the transcript.
  
  Example of a prompt file (`summary.txt`):

  ```
  Provide a brief summary of this transcript.
  ```

## Usage

### 1. Run the Script

1. Open a terminal or command prompt.
2. Run the batch script:

```bash
YoutubeAIHelper.bat
```

### 2. Follow the Prompts

- Enter the YouTube URL when prompted.
- The script will download the video, extract the MP3, and transcribe it.
- You'll then be asked to select the configuration folder that contains your LLM prompts.
  
### 3. Review Output

Once the process is complete:
- Transcriptions (both `.txt` and `.srt` formats) will be saved in a folder named after the video.
- The LLM responses will be saved as `.txt` files within the same folder.

### Example Workflow

1. **Download video**: The MP3 file is downloaded and placed in the `videos/` directory.
2. **Transcription**: Whisper generates a transcript from the MP3 file.
3. **LLM Processing**: The LLM processes the transcript using your prompts, saving the results in the output folder.

## Configuration

- **Custom Prompts**: You can define your own prompts in the `configurations/prompts/` folder. Each `.txt` file corresponds to a specific task (e.g., summarization, question-answering).
- **API Config**: The `llm_config.txt` file in the configuration folder allows you to set the model, maximum token limit, and your OpenAI API key.

## Troubleshooting

- **Missing dependencies**: Ensure `yt-dlp`, Whisper, and `curl` are installed correctly.
- **File errors**: Check if the YouTube URL is valid, and ensure the paths for prompts and configurations are correct.
  
## Contributions

Contributions are welcome! Please fork the repository and submit a pull request with any improvements or new features.
```

You can copy and paste this content into your `README.md` file directly. Let me know if you'd like any further adjustments!
