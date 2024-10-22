import argparse
import os
import sys
import re
import yt_dlp
from pydub import AudioSegment
from pydub.utils import make_chunks
import openai

def extract_text_from_srt(srt_content):
    """
    Extracts the plain text from the given SRT content.
    
    Parameters:
    srt_content (str): The content of the SRT file as a string.
    
    Returns:
    str: The extracted plain text.
    """
    # Regular expression to match the SRT timestamps and sequence numbers
    srt_pattern = re.compile(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n')
    
    # Remove the timestamps and sequence numbers, and clean up the text
    plain_text = re.sub(srt_pattern, '', srt_content)
    
    # Remove extra newlines and return the result
    plain_text = plain_text.replace('\n\n', '\n').strip()
    
    return plain_text

def parse_arguments():
    parser = argparse.ArgumentParser(description='Video Downloader and Transcriber')
    parser.add_argument('--config_folder', help='Path to configuration folder', default='configurations/generic')
    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Subparser for full process: download, transcribe, and process prompts
    parser_full = subparsers.add_parser('full_process', help='Download, transcribe, and process prompts')
    parser_full.add_argument('urls', nargs='+', help='YouTube URLs to download and process')

    # Subparser for downloading YouTube videos
    parser_download = subparsers.add_parser('download', help='Download YouTube videos')
    parser_download.add_argument('urls', nargs='+', help='YouTube URLs to download')

    # Subparser for transcribing local audio files
    parser_transcribe = subparsers.add_parser('transcribe', help='Transcribe local audio files')
    parser_transcribe.add_argument('folders', nargs='+', help='Folders containing mp3 files to transcribe')

    # Subparser for processing prompts on transcribed files
    parser_prompts = subparsers.add_parser('process_prompts', help='Process prompts on transcribed files')
    parser_prompts.add_argument('folders', nargs='+', help='Folders containing transcribed files')

    return parser.parse_args()

def load_config(config_folder):
    if not os.path.exists(config_folder):
        print(f"Error: Configuration folder '{config_folder}' not found.")
        sys.exit(1)

    # Load LLM config
    llm_config_path = os.path.join(config_folder, 'llm_config.txt')
    if not os.path.exists(llm_config_path):
        print(f"Error: llm_config.txt not found in '{config_folder}'.")
        sys.exit(1)
    config = {}
    with open(llm_config_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                config[key.strip()] = value.strip()
    required_keys = ['model', 'max_tokens', 'openai_api_key']
    for key in required_keys:
        if key not in config:
            print(f"Error: '{key}' is missing in llm_config.txt.")
            sys.exit(1)

    # Load prompts folder
    prompts_folder = os.path.join(config_folder, 'prompts')
    if not os.path.exists(prompts_folder):
        print(f"Error: Prompts folder '{prompts_folder}' not found in configuration folder.")
        sys.exit(1)
    config['prompts_folder'] = prompts_folder

    # Load Whisper config
    whisper_config_path = os.path.join(config_folder, 'whisper_config.txt')
    whisper_config = {}
    if os.path.exists(whisper_config_path):
        with open(whisper_config_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    whisper_config[key.strip()] = value.strip()
    else:
        whisper_config = {}

    return config, whisper_config

def sanitize_filename(filename):
    return "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()

def download_youtube_video(url, output_dir):
    try:
        print(f"Downloading video from URL: {url}")
        ydl_opts_info = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            title = info_dict.get('title', 'video')
            sanitized_title = sanitize_filename(title)
            print(f"RAW title: {title}")
            print(f"Sanitized title: {sanitized_title}")

        video_folder = os.path.join(output_dir, sanitized_title)
        os.makedirs(video_folder, exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(video_folder, f"{sanitized_title}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
            'quiet': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_file = os.path.join(video_folder, f"{sanitized_title}.mp3")
        print(f"Downloaded and saved audio to: {audio_file}")
        return audio_file, video_folder, sanitized_title
    except Exception as e:
        print(f"Error downloading video from {url}: {e}")
        sys.exit(1)

def split_audio_file(file_path, max_size_bytes=24 * 1024 * 1024):
    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)
    file_size = os.path.getsize(file_path)
    if file_size <= max_size_bytes:
        return [file_path]

    print(f"Audio file '{file_path}' is larger than {max_size_bytes} bytes. Splitting into smaller chunks...")
    chunk_length_ms = duration_ms * max_size_bytes / file_size
    chunks = make_chunks(audio, int(chunk_length_ms))
    base, ext = os.path.splitext(file_path)
    chunk_files = []
    for i, chunk in enumerate(chunks):
        chunk_filename = f"{base}_part{i}{ext}"
        chunk.export(chunk_filename, format="mp3")
        chunk_files.append(chunk_filename)
        print(f"Created chunk: {chunk_filename}")
    return chunk_files

def transcribe_audio_files(audio_files, config, whisper_config):
    for audio_file in audio_files:
        print(f"Transcribing audio file: {audio_file}")
        audio_parts = split_audio_file(audio_file)
        transcripts_txt = []
        transcripts_srt = []
        for part in audio_parts:
            transcripts = transcribe_with_whisper_api(part, config['openai_api_key'], whisper_config)
            srt_content = transcripts['srt']
            plain_text = extract_text_from_srt(srt_content)
            transcripts_txt.append(plain_text)
            transcripts_srt.append(srt_content)
            if part != audio_file:
                os.remove(part)
        full_transcript_txt = "\n".join(transcripts_txt)
        full_transcript_srt = "\n".join(transcripts_srt)
        output_dir = os.path.dirname(audio_file)

        transcript_file_txt = os.path.join(output_dir, 'transcript.txt')
        with open(transcript_file_txt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_txt)
        print(f"Saved transcription to: {transcript_file_txt}")

        transcript_file_srt = os.path.join(output_dir, 'transcript.srt')
        with open(transcript_file_srt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_srt)
        print(f"Saved transcription to: {transcript_file_srt}")

def transcribe_with_whisper_api(audio_file, openai_api_key, whisper_config):
    # Initialize the OpenAI client
    client = openai.OpenAI(api_key=openai_api_key)
    
    transcripts = {}
    params = {}

    # Process whisper configuration and supported parameters
    for key, value in whisper_config.items():
        if key == 'temperature':
            params[key] = float(value)
        elif key in ['language', 'prompt', 'response_format', 'max_alternatives', 'profanity_filter']:
            params[key] = value

    try:
        with open(audio_file, 'rb') as f:
            print(f"Sending audio file '{audio_file}' to Whisper API for transcription...")
            
            # Use the new API structure
            response = client.audio.transcriptions.create(
                file=f,
                model="whisper-1",
                response_format='srt',  # Transcribe in SRT format
                **params
            )
            transcripts['srt'] = response  # Save SRT response

        return transcripts
    except Exception as e:
        print(f"Error transcribing audio file '{audio_file}': {e}")
        sys.exit(1)


def process_prompts_on_transcripts(folders, config):
    prompts_folder = config['prompts_folder']
    prompt_files = [os.path.join(prompts_folder, f) for f in os.listdir(prompts_folder) if os.path.isfile(os.path.join(prompts_folder, f))]
    if not prompt_files:
        print(f"Error: No prompt files found in '{prompts_folder}'.")
        sys.exit(1)

    for folder in folders:
        if not os.path.exists(folder):
            print(f"Error: Folder '{folder}' not found.")
            continue

        transcript_txt = os.path.join(folder, 'transcript.txt')
        transcript_srt = os.path.join(folder, 'transcript.srt')
        if not os.path.exists(transcript_txt) and not os.path.exists(transcript_srt):
            print(f"No transcript files found in folder '{folder}'.")
            continue

        transcribed_file = {'base': os.path.join(folder, 'transcript')}
        if os.path.exists(transcript_txt):
            transcribed_file['txt'] = transcript_txt
        if os.path.exists(transcript_srt):
            transcribed_file['srt'] = transcript_srt

        print(f"Processing prompts on transcripts in folder: {folder}")
        for prompt_file in prompt_files:
            process_single_prompt(prompt_file, transcribed_file, folder, config)


def process_single_prompt(prompt_file, transcribed_file, folder, config):
    # Read the prompt content from the file
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt_content = f.read()

    prompt_name = os.path.splitext(os.path.basename(prompt_file))[0]
    prompt_ext = os.path.splitext(prompt_file)[1].lower()
    print(f"Processing prompt: {prompt_name}")

    # Initialize OpenAI client
    client = openai.OpenAI(api_key=config['openai_api_key'])
    model = config['model']
    max_tokens = config['max_tokens']

    # Use appropriate transcribed file based on extension
    if prompt_ext == '.srt':
        user_content_file = transcribed_file.get('srt')
    else:
        user_content_file = transcribed_file.get('txt')

    if not user_content_file or not os.path.exists(user_content_file):
        print(f"Error: Transcribed file '{user_content_file}' not found.")
        return

    # Read the user content from the transcribed file
    with open(user_content_file, 'r', encoding='utf-8') as f:
        user_content = f.read()

    messages = [
        {"role": "system", "content": prompt_content},
        {"role": "user", "content": user_content}
    ]

    try:
        # Use the updated ChatCompletion API
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=int(max_tokens)
        )
        assistant_content = response.choices[0].message.content  # Use dot notation to access content

        # Ensure unique output filename
        output_filename = f"{prompt_name}.prompt.txt"
        output_file = os.path.join(folder, output_filename)
        file_number = 1
        while os.path.exists(output_file):
            file_number += 1
            output_filename = f"{prompt_name}.{file_number}.prompt.txt"
            output_file = os.path.join(folder, output_filename)

        # Save the assistant's response
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(assistant_content)
        print(f"Saved response to: {output_file}")

    except Exception as e:
        print(f"Error processing prompt '{prompt_name}': {e}")



def main():
    args = parse_arguments()
    config, whisper_config = load_config(args.config_folder)

    if args.mode == 'full_process':
        output_dir = os.path.join(os.getcwd(), 'videos')
        os.makedirs(output_dir, exist_ok=True)
        all_folders = []
        for url in args.urls:
            audio_file, video_folder, sanitized_title = download_youtube_video(url, output_dir)
            transcribe_audio_files([audio_file], config, whisper_config)
            all_folders.append(video_folder)
        process_prompts_on_transcripts(all_folders, config)

    elif args.mode == 'download':
        output_dir = os.path.join(os.getcwd(), 'videos')
        os.makedirs(output_dir, exist_ok=True)
        for url in args.urls:
            download_youtube_video(url, output_dir)

    elif args.mode == 'transcribe':
        for folder in args.folders:
            if not os.path.exists(folder):
                print(f"Error: Folder '{folder}' not found.")
                continue
            audio_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.mp3')]
            if not audio_files:
                print(f"No mp3 files found in folder '{folder}'.")
                continue
            transcribe_audio_files(audio_files, config, whisper_config)

    elif args.mode == 'process_prompts':
        process_prompts_on_transcripts(args.folders, config)

if __name__ == "__main__":
    main()
