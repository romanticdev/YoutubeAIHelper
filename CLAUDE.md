# YoutubeAIHelper Commands and Guidelines

## Build/Run Commands
- Install: `pip install -r requirements.txt`
- Full process: `python main.py --config-folder configurations/generic full-process URL --update-youtube`
- Download: `python main.py --config-folder configurations/generic download URL`
- Transcribe: `python main.py --config-folder configurations/generic transcribe FOLDER`
- Improve SRT: `python main.py --config-folder configurations/generic improve-srt FOLDER`
- Process prompts: `python main.py --config-folder configurations/generic process-prompts FOLDER`
- Update YouTube: `python main.py --config-folder configurations/generic update-youtube FOLDER`
- Generate thumbnails: `python main.py --config-folder configurations/generic generate-thumbnail FOLDER`
- Generate discussion starters: `python main.py --config-folder configurations/generic generate-discussion-starters`
- Live chat bot: `python livechatbot.py [optional_video_id]`
- Live transcriber: `python live_transcriber.py`

## Code Style Guidelines
- **Naming**: Use snake_case for variables/functions and CamelCase for classes
- **Imports**: Group standard library imports first, then third-party, then local
- **Docstrings**: Provide clear docstrings for all functions and classes
- **Error Handling**: Use try/except blocks with specific exceptions
- **Indentation**: 4 spaces (standard Python)
- **Module Structure**: Keep files modular and single-purpose focused
- **Configuration**: Set download_video=true in llm_config.txt to download video+audio instead of audio only