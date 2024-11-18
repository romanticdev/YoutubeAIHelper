# Local YouTube AI Helper Python Script

[**Return to Project Root**](/README.md)

This project provides a Python script, `ai_helper.py`, designed to make working with YouTube audio simple and efficient. It downloads audio from YouTube videos, transcribes it locally, and uses the OpenAI API to run customized prompts on the transcript. Whether you're working with long videos or specific text prompts, this script makes the process smoother.

## Features

- **Download and Convert**: Downloads YouTube videos and extracts audio in `.ogg` format.
- **Transcription**: Automatically transcribes audio using OpenAI's Whisper API.
- **Prompt Execution**: Runs custom LLM prompts on the transcript for further processing.
- **Flexible Setup**: Easily configure prompts to suit your needs.

## Setup Instructions

### 1. Clone the Repository

Clone this repository with Git:

```bash
git clone https://github.com/romanticdev/YoutubeAIHelper.git
cd YoutubeAIHelper
```

### 2. Install Dependencies

Install the required dependencies using `requirements.txt`:

```bash
pip install -r requirements.txt
```

The `requirements.txt` file includes:

```txt
openai==1.50.0
requests==2.32.3
yt-dlp==2024.8.6
srt==3.5.1
```

### 3. Obtain OpenAI API Key

To use OpenAI for transcription and LLM features, obtain an API key:

1. Go to the [OpenAI API Keys page](https://platform.openai.com/account/api-keys) and sign in using your OpenAI account.
2. If you do not have an account, create one by following the sign-up process.
3. Once logged in, navigate to the API Keys section.
4. Click 'Create new secret key' to generate your API key.
5. Copy the generated key to use in your configuration.

Update `llm_config.txt` in the configuration folder:

```txt
model=chatgpt-4o-latest
max_tokens=16000
openai_api_key=your_api_key_here
```

### 4. Configure Prompts

The generic configuration folder comes with sample prompts that you can use to showcase the possibilities. Create prompt files in `configurations/generic/prompts/`. Each `.txt` file defines a specific prompt for the LLM, while each `.srt` file also provides a prompt but with user input that includes a text and time component specific prompt for the LLM to apply to the transcript.

Example (`summary.txt`):

```txt
Provide a brief summary of this transcript.
```

#### 4.1. Enhancing Prompt Processing with JSON Output

The `ai_helper.py` script now supports structured JSON outputs for prompt processing. This feature ensures consistent and machine-readable responses, facilitating seamless integration with other tools and systems.


#### 4.2. Creating Prompts for JSON Output

To generate JSON-formatted outputs, follow these steps:

- **Define Your Desired JSON Structure**: Determine the specific fields and their data types that you want in the output.

- **Create a Prompt File**: In the `configurations/generic/prompts/` directory, create a `.txt` file (e.g., `summary.txt`) with the desired prompt.

- **Develop a Corresponding JSON Schema**: In the same directory, create a `.schema.json` file (e.g., `summary.schema.json`) that defines the structure of the expected JSON output. This schema ensures that the output adheres to the specified format.

#### 4.3. Example: Generating a Summary in JSON Format

- **Prompt File (`summary.txt`)**:

  ```
  Provide a brief summary of this transcript.
  ```

- **JSON Schema File (`summary.schema.json`)**:

  ```json
  {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SummaryResponse",
    "type": "object",
    "properties": {
      "summary": {
        "type": "string",
        "description": "A concise summary of the transcript."
      }
    },
    "required": ["summary"],
    "additionalProperties": false
  }
  ```

By implementing this structure, the script will process the prompt and return a JSON object matching the defined schema.

#### 4.4. Transforming Custom JSON to JSON Schema

To convert your custom JSON output into a JSON Schema:

- **Identify the Structure**: Analyze your JSON output to determine the data types and required fields.

- **Use JSON Schema Tools**: Utilize online tools or libraries to generate a JSON Schema based on your JSON structure.
To generate schema file locally you can use simple python script included into `tools\generate_schema.py` like:
   ```bash
      python generate_schema.py input.json
   ```

- **Validate the Schema**: Ensure that the generated schema accurately represents your desired output format.

For more detailed guidance on creating JSON Schemas, refer to the [OpenAI Cookbook on Structured Outputs](https://cookbook.openai.com/examples/structured_outputs_intro).


## Usage

### Run the Script

1. Open a terminal or command prompt.
2. Navigate to the project folder and execute:
   ```bash
   python ai_helper.py --config_folder configurations/generic full_process <YouTube_URL>
   ```
   Example:
   ```bash
   python ai_helper.py --config_folder configurations/generic full_process https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

### Options

- `--config_folder`: Specify the configuration folder with prompts and `llm_config.txt`. If this option is omitted, the default `configurations/generic` folder will be used.
- `download`: Only download YouTube audio.
- `transcribe`: Only transcribe the audio file.
- `process_prompts`: Apply prompts to existing transcriptions.

## Workflow Example

1. **Download**: The audio is saved in the `videos/` folder.
2. **Transcription**: Whisper API generates the transcript.
3. **LLM Processing**: The transcript is processed with OpenAI API, saving responses to the output folder.

## Configuration

- **Prompts**: Define custom prompts in `configurations/prompts/`.
- **API Config**: Set model, token limit, and OpenAI API key in `llm_config.txt`.

## Troubleshooting

- **Dependencies**: Ensure all required tools (`ffmpeg`, etc.) are installed.
- **File Errors**: Verify the YouTube URL and paths for configuration files are correct.

## Contributions

Contributions are welcome! Feel free to fork the repository, make improvements, and submit a pull request.
