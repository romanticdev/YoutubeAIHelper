# YouTube AI Helper

This project aims to help automate tasks related to video or audio files with speech content. It extracts audio as text and uses it to gather useful information using LLMs (Language Learning Models). One of its goals is to automate the publishing process (for example, on YouTube), including updating video parameters like descriptions, video sections, keywords, and more.

Right now, this project automates the process of downloading a YouTube video as an MP3, transcribing it using the Whisper model, and processing the transcript with an LLM through OpenAI’s API (ChatGPT models).

This is ideal for extracting useful information, summaries, or insights from YouTube video transcripts.

## Current Features

- Downloads YouTube videos as MP3.
- Automatically transcribes the audio using Whisper.
- Executes custom LLM prompts on the transcript for further processing.
- Easily configurable with different prompt setups.

## Implementations

### LocalYoutubeAIHelper

This project contains a batch file (for execution on `Windows` platforms) that uses preinstalled tools like `yt-dlp` and `whisper` to download videos from YouTube, transcribe them locally, and execute LLMs via the OpenAI API using `curl`. It is a simple approach designed to automate the commands you would typically execute manually in `cmd`, organizing them into one streamlined process.

More details about prerequisites and documentation can be found here: [LocalYoutubeAIHelper README](./LocalYoutubeAIHelper/readme.md)

## Contributions

Contributions are welcome! Please fork the repository and submit a pull request with any improvements or new features.
