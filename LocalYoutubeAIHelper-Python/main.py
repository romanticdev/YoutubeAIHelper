import os
import argparse
from downloader import Downloader
from transcriber import Transcriber
from youtube_update import YouTubeUpdater
from prompt_processor import PromptProcessor
from discussion_starters import DiscussionStarters
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
    def_config_folder = CONFIG.get('default_config_folder','configurations/generic')
    parser.add_argument('--config-folder', help=f"Path to configuration folder (default: '{def_config_folder}')", 
                        default=def_config_folder)
    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Full process: download, transcribe, and process prompts
    parser_full = subparsers.add_parser('full-process', help="Download, transcribe, and process prompts")
    parser_full.add_argument('inputs', nargs='+', help="YouTube URLs, video IDs, or local file paths to process")
    parser_full.add_argument('--update-youtube', action='store_true', help="Update YouTube videos after processing (default: False)")
    parser_full.add_argument('--disable-improve-srt', action='store_true', help="Disable automatic improvement of transcribed SRT (default: False)", default=False)
    
    # Download YouTube videos
    parser_download = subparsers.add_parser('download', help="Download YouTube videos")
    parser_download.add_argument('urls', nargs='+', help="YouTube URLs to download")

    # Transcribe audio files
    parser_transcribe = subparsers.add_parser('transcribe', help="Transcribe local audio files")
    parser_transcribe.add_argument('folders', nargs='+', help="Folders containing MP3 files to transcribe")

    #Improve transcript
    parser_improve_transcript = subparsers.add_parser('improve-srt',help="Improve automatically transcribed SRT")
    parser_improve_transcript.add_argument('folders', nargs='+', help="Folders containing transcribed files")

    # Process prompts on transcriptions
    parser_prompts = subparsers.add_parser('process-prompts', help="Process prompts on transcribed files")
    parser_prompts.add_argument('folders', nargs='+', help="Folders containing transcribed files")

    # Generate Discussion starter
    parser_discussion = subparsers.add_parser('generate-discussion-starters', help="Generate discussion starters for the next stream")
   
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

        for input_item in args.inputs:
            if os.path.isfile(input_item):  # Check if the input is a local file
                if not downloader.is_valid_media_file(input_item):
                    logger.warning(f"Skipping invalid media file: {input_item}")
                    continue                
                logger.info(f"Processing local file: {input_item}")
                video_folder = os.path.dirname(input_item)
                file_name = os.path.splitext(os.path.basename(input_item))[0]
                
                # Convert to OGG
                ogg_file_path = downloader.convert_to_ogg(input_item, video_folder, file_name)
            else:
                # Handle YouTube URLs or IDs
                audio_file, video_folder, title = downloader.download_youtube_video(input_item, output_dir)
            
            # Proceed with transcription and prompt processing
            transcriber.transcribe_audio_files([os.path.join(video_folder, f) for f in os.listdir(video_folder) if f.endswith('.ogg')])
            if not args.disable_improve_srt:
                transcriber.improve_transcription(video_folder)
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
            
    elif args.mode == 'improve-srt':
        for folder in args.folders:
            transcriber.improve_transcription(folder)

    elif args.mode == 'process-prompts':
        prompt_processor.process_prompts_on_transcripts(args.folders)

    elif args.mode == 'update-youtube':
        youtube_updater.process_update_youtube(args.folder)
        
    elif args.mode == 'generate-discussion-starters':
        ds = DiscussionStarters(config, whisper_config,number_of_streams=3)
        questions = ds.generate_questions()
        print("Generated Questions:\n", questions)

if __name__ == "__main__":
    main()
