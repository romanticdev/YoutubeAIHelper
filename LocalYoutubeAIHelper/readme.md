# Local YouTube AI Helper

[RETURN TO THE PROJECT ROOT](/README.md)

This project contains a batch file (for execution on Windows platforms) that uses preinstalled tools like `yt-dlp`, `Whisper`, and `curl` to download videos from YouTube, transcribe them locally, and execute LLMs via the OpenAI API. It is designed to automate the commands you would typically execute manually in `cmd`, organizing them into one streamlined process.

## Features

- Downloads YouTube videos as MP3.
- Automatically transcribes the audio using Whisper.
- Executes custom LLM prompts on the transcript for further processing.
- Easily configurable with different prompt setups.

## Requirements

You need to have the following tools installed before running the batch file:

1. **Git** (for cloning the repository)
   - Install Git from [here](https://git-scm.com/downloads).
   - Ensure Git is added to the system PATH during installation.

   To verify if Git is already installed, open a terminal and run:
   ```bash
   git --version
   ```
   If installed, this command will show the installed version of Git.

2. **Python** (required for Whisper)
   - Install Python from [here](https://www.python.org/downloads/).
   - Ensure to check the box to add Python to the system PATH during installation.

   To verify Python installation, run:
   ```bash
   python --version
   ```

3. **FFmpeg** (for audio extraction from YouTube)
   - Download and install FFmpeg from [here](https://ffmpeg.org/download.html).
   - Add FFmpeg to your system PATH by following [these instructions](https://www.wikihow.com/Install-FFmpeg-on-Windows).

   To verify if FFmpeg is installed, run:
   ```bash
   ffmpeg -version
   ```
   
4. **yt-dlp** (for downloading YouTube videos)
   - Install using Python:
     ```bash
     pip install yt-dlp
     ```
   - To verify, run:
     ```bash
     yt-dlp --version
     ```

5. **Whisper** (OpenAI's Speech-to-Text model)
   - Install Whisper using:
     ```bash
     pip install git+https://github.com/openai/whisper.git
     ```

   To check the installation, run:
   ```bash
   whisper --help
   ```

6. **curl** (for making API requests)
   - `curl` might already be available on Windows 11. To check, run:
     ```bash
     curl --version
     ```
   - If `curl` is not available, download and install it from [here](https://curl.se/download.html).

7. **PowerShell** (for script execution)
   - PowerShell is preinstalled on Windows systems, but to ensure it's available, run:
     ```bash
     powershell
     ```

### Adding Tools to Your System PATH

For each tool, if they are not available on the terminal. follow these instructions to add them to your system PATH:

1. **Verifying the PATH**:
   - Open a terminal or command prompt (`cmd`) and run:
     ```bash
     python --version
     whisper --help
     yt-dlp --version
     curl --version
     ffmpeg -version
     ```
     
1. **Adding to PATH in Windows**:
   - Right-click on "This PC" or "My Computer" and select "Properties".
   - Click on "Advanced system settings" and then click "Environment Variables".
   - Under "System variables", find the PATH variable, select it, and click "Edit".
   - Click "New" and add the path to the folder where the tool is installed.
   - Click "OK" and close all dialogs.

If all tools return their version information, they are correctly installed and added to the PATH.

## Setup

### 1. Clone the Repository

Once Git is installed, clone the repository:

```bash
git clone https://github.com/romanticdev/YoutubeAIHelper.git
cd YoutubeAIHelper\LocalYoutubeAIHelper
```

### 2. Install yt-dlp, Whisper, and curl

- Follow the above instructions to install `yt-dlp`, Whisper, and `curl` and ensure they are added to your PATH.

### 3. Obtain OpenAI API Key

To use the LLM feature, you’ll need an OpenAI API key.

1. Go to [OpenAI API](https://platform.openai.com/account/api-keys) and sign in.
2. Copy your API key.
3. Create or update the `llm_config.txt` file in the configuration directory with your key:

```txt
model=gpt-3.5-turbo
max_tokens=500
openai_api_key=your_api_key_here
```

### 4. Configure Prompts

Define the prompts you want to use for the LLM in the `configurations/prompts/` folder. Create `.txt` files containing the prompt instructions. Each prompt will be applied to the transcript.

Example of a prompt file (`summary.txt`):

```txt
Provide a brief summary of this transcript.
```

## Folder Structure Example

The project uses a structured configuration setup for each task. Below is an example:

```bash
project_root/
│
├── configuration1/
│   ├── language.txt              # Optional: contains language code (e.g., "en")
│   ├── whisper_instructions.txt  # Optional: additional instructions for Whisper
│   ├── llm_config.txt            # Contains LLM API key or parameters
│   └── prompts/
│       ├── prompt1.txt           # Contains system message for prompt 1
│       └── prompt2.txt           # Contains system message for prompt 2
└── configuration2/               # Another configuration folder
```

## Usage

### 1. Run the Script

1. Open a terminal or command prompt.
2. Navigate to the project folder and run the batch script:

```bash
ai_helper.bat
```

### 2. Follow the Prompts

- Enter the YouTube URL when prompted.
- The script will download the video, extract the MP3, and transcribe it.
- You'll then be asked to select the configuration folder containing your LLM prompts.

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

- **Missing dependencies**: Ensure `yt-dlp`, Whisper, `ffmpeg`, and `curl` are installed correctly.
- **File errors**: Check if the YouTube URL is valid, and ensure the paths for prompts and configurations are correct.

## Contributions

Contributions are welcome! Please fork the repository and submit a pull request with any improvements or new features.
