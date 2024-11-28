import os
import argparse
from downloader import Downloader
from transcriber import Transcriber
from youtube_update import YouTubeUpdater
from prompt_processor import PromptProcessor
from config import CONFIG, WHISPER_CONFIG, load_config_from_folder
from utilities import setup_logging

logger = setup_logging()

def parse_arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="A tool to download, transcribe, and process YouTube videos with AI prompts and updates."
    )
    parser.add_argument('--config-folder', help="Path to configuration folder (default: 'configurations/generic')", 
                        default='configurations/generic')
    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Full process: download, transcribe, and process prompts
    parser_full = subparsers.add_parser('full-process', help="Download, transcribe, and process prompts")
    parser_full.add_argument('urls', nargs='+', help="YouTube URLs to process")
    parser_full.add_argument('--update-youtube', action='store_true', help="Update YouTube videos after processing (default: False)")

    # Download YouTube videos
    parser_download = subparsers.add_parser('download', help="Download YouTube videos")
    parser_download.add_argument('urls', nargs='+', help="YouTube URLs to download")

    # Transcribe audio files
    parser_transcribe = subparsers.add_parser('transcribe', help="Transcribe local audio files")
    parser_transcribe.add_argument('folders', nargs='+', help="Folders containing MP3 files to transcribe")

    # Process prompts on transcriptions
    parser_prompts = subparsers.add_parser('process-prompts', help="Process prompts on transcribed files")
    parser_prompts.add_argument('folders', nargs='+', help="Folders containing transcribed files")

    # Update YouTube videos
    parser_update = subparsers.add_parser('update-youtube', help="Update YouTube videos using folder details")
    parser_update.add_argument('folder', help="Folder containing file_details.txt and optional metadata files")

    return parser.parse_args()

def main():
    """
    Main entry point for the script.
    """
    args = parse_arguments()
    config, whisper_config = CONFIG, WHISPER_CONFIG

    if args.config_folder:
        config, whisper_config = load_config_from_folder(args.config_folder)

    # Initialize components
    downloader = Downloader(config)
    transcriber = Transcriber(config, whisper_config)
    prompt_processor = PromptProcessor(config)

    if (args.mode == 'full-process' and args.update_youtube) or \
        args.mode == 'update-youtube':
        youtube_updater = YouTubeUpdater(config)

    if args.mode == 'full-process':
        output_dir = os.path.join(os.getcwd(), 'videos')
        os.makedirs(output_dir, exist_ok=True)

        for url in args.urls:
            logger.info(f"Processing URL: {url}")
            audio_file, video_folder, title = downloader.download_youtube_video(url, output_dir)
            transcriber.transcribe_audio_files([audio_file])
            prompt_processor.process_prompts_on_transcripts([video_folder])

            if args.update_youtube:
                youtube_updater.process_update_youtube(video_folder)
            
    elif args.mode == 'download':
        output_dir = os.path.join(os.getcwd(), 'videos')
        os.makedirs(output_dir, exist_ok=True)
        for url in args.urls:
            downloader.download_youtube_video(url, output_dir)

    elif args.mode == 'transcribe':
        for folder in args.folders:
            transcriber.transcribe_folder(folder)

    elif args.mode == 'process-prompts':
        prompt_processor.process_prompts_on_transcripts(args.folders)

    elif args.mode == 'update-youtube':
        youtube_updater.process_update_youtube(args.folder)

if __name__ == "__main__":
    main()
