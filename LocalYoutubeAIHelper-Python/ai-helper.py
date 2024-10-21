import argparse
import os
import sys
import re
import shutil
import json
import requests
from pytube import YouTube
from pydub import AudioSegment
from pydub.utils import make_chunks

# Install the openai library if not already installed
try:
    import openai
except ImportError:
    print("The 'openai' library is not installed. Installing now...")
    os.system(f"{sys.executable} -m pip install openai")
    import openai

# Install pydub if not already installed
try:
    from pydub import AudioSegment
except ImportError:
    print("The 'pydub' library is not installed. Installing now...")
    os.system(f"{sys.executable} -m pip install pydub")
    from pydub import AudioSegment

def parse_arguments():
    parser = argparse.ArgumentParser(description='Video Downloader and Transcriber')
    subparsers = parser.add_subparsers(dest='mode', required=True)

    # Subparser for downloading and transcribing YouTube videos
    parser_download = subparsers.add_parser('download_and_transcribe', help='Download and transcribe YouTube videos')
    parser_download.add_argument('urls', nargs='+', help='YouTube URLs to download and transcribe')
    parser_download.add_argument('--config_folder', help='Path to configuration folder', default='configurations/default')

    # Subparser for transcribing local files
    parser_transcribe = subparsers.add_parser('transcribe_files', help='Transcribe local audio files')
    parser_transcribe.add_argument('files', nargs='+', help='Audio files to transcribe')
    parser_transcribe.add_argument('--config_folder', help='Path to configuration folder', default='configurations/default')

    # Subparser for processing prompts on already transcribed files
    parser_prompts = subparsers.add_parser('process_prompts', help='Process prompts on transcribed files')
    parser_prompts.add_argument('transcripts', nargs='+', help='Transcribed text files to process prompts on')
    parser_prompts.add_argument('--config_folder', help='Path to configuration folder', default='configurations/default')

    return parser.parse_args()

def load_config(config_folder):
    if not os.path.exists(config_folder):
        print(f"Error: Configuration folder '{config_folder}' not found.")
        sys.exit(1)
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
    # Add prompts_folder to config
    prompts_folder = os.path.join(config_folder, 'prompts')
    if not os.path.exists(prompts_folder):
        print(f"Error: Prompts folder '{prompts_folder}' not found in configuration folder.")
        sys.exit(1)
    config['prompts_folder'] = prompts_folder
    return config

def sanitize_filename(filename):
    # Remove invalid characters for filenames
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = re.sub(r'__+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized

def download_youtube_video(url, output_dir):
    try:
        print(f"Downloading video from URL: {url}")
        yt = YouTube(url)
        title = yt.title
        raw_title = title
        sanitized_title = sanitize_filename(title)
        print(f"RAW title: {raw_title}")
        print(f"Sanitized title: {sanitized_title}")
        print()
        video_folder = os.path.join(output_dir, sanitized_title)
        print(f"Creating folder: '{video_folder}'")
        os.makedirs(video_folder, exist_ok=True)
        audio_stream = yt.streams.filter(only_audio=True).first()
        output_path = audio_stream.download(output_path=video_folder, filename=sanitized_title + '.mp3')
        print(f"Downloaded and saved audio to: {output_path}")
        return output_path, video_folder, sanitized_title
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

def transcribe_audio_files(audio_files, config, output_dir):
    transcribed_files = []
    for audio_file in audio_files:
        print(f"Transcribing audio file: {audio_file}")
        # Split audio if larger than 25 MB
        audio_parts = split_audio_file(audio_file)
        transcripts_txt = []
        transcripts_srt = []
        for part in audio_parts:
            transcripts = transcribe_with_whisper_api(part, config)
            transcripts_txt.append(transcripts['txt'])
            transcripts_srt.append(transcripts['srt'])
            # Remove the chunk file if it's a temporary split
            if part != audio_file:
                os.remove(part)
        full_transcript_txt = "\n".join(transcripts_txt)
        full_transcript_srt = "\n".join(transcripts_srt)
        base_name = os.path.basename(audio_file)
        sanitized_base = sanitize_filename(os.path.splitext(base_name)[0])

        transcript_file_txt = os.path.join(output_dir, f"{sanitized_base}.txt")
        with open(transcript_file_txt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_txt)
        print(f"Saved transcription to: {transcript_file_txt}")

        transcript_file_srt = os.path.join(output_dir, f"{sanitized_base}.srt")
        with open(transcript_file_srt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_srt)
        print(f"Saved transcription to: {transcript_file_srt}")

        transcribed_files.append({'txt': transcript_file_txt, 'srt': transcript_file_srt, 'base': os.path.splitext(transcript_file_txt)[0]})
    return transcribed_files

def transcribe_with_whisper_api(audio_file, config):
    openai.api_key = config['openai_api_key']
    transcripts = {}
    try:
        with open(audio_file, 'rb') as f:
            print(f"Sending audio file '{audio_file}' to Whisper API for text transcription...")
            response = openai.Audio.transcribe("whisper-1", f, response_format='text')
            transcripts['txt'] = response

        with open(audio_file, 'rb') as f:
            print(f"Sending audio file '{audio_file}' to Whisper API for srt transcription...")
            response = openai.Audio.transcribe("whisper-1", f, response_format='srt')
            transcripts['srt'] = response

        return transcripts
    except Exception as e:
        print(f"Error transcribing audio file '{audio_file}': {e}")
        sys.exit(1)

def process_prompts_on_transcripts(transcribed_files, config):
    prompts_folder = config['prompts_folder']
    prompt_files = [os.path.join(prompts_folder, f) for f in os.listdir(prompts_folder) if f.endswith(('.txt', '.srt'))]
    if not prompt_files:
        print(f"Error: No prompt files found in '{prompts_folder}'.")
        sys.exit(1)
    for transcribed_file in transcribed_files:
        print(f"Processing prompts on transcript: {transcribed_file['base']}")
        for prompt_file in prompt_files:
            process_single_prompt(prompt_file, transcribed_file, transcribed_file['base'], config)

def process_single_prompt(prompt_file, transcribed_file, transcript_file_base, config):
    with open(prompt_file, 'r', encoding='utf-8') as f:
        prompt_content = f.read()
    prompt_name = os.path.splitext(os.path.basename(prompt_file))[0]
    prompt_ext = os.path.splitext(prompt_file)[1].lower()
    print(f"Processing prompt: {prompt_name}")
    openai.api_key = config['openai_api_key']
    model = config['model']
    max_tokens = config['max_tokens']

    # Use appropriate transcript file based on prompt file extension
    if prompt_ext == '.srt':
        user_content_file = transcribed_file.get('srt')
    else:
        user_content_file = transcribed_file.get('txt')

    if not user_content_file or not os.path.exists(user_content_file):
        print(f"Error: Transcribed file '{user_content_file}' not found.")
        sys.exit(1)

    with open(user_content_file, 'r', encoding='utf-8') as f:
        user_content = f.read()

    messages = [
        {"role": "system", "content": prompt_content},
        {"role": "user", "content": user_content}
    ]
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=int(max_tokens)
        )
        assistant_content = response['choices'][0]['message']['content']
        # Save response to file
        output_file = f"{transcript_file_base}_{prompt_name}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(assistant_content)
        print(f"Saved response to: {output_file}")
    except Exception as e:
        print(f"Error processing prompt '{prompt_name}': {e}")
        sys.exit(1)

def main():
    args = parse_arguments()
    config = load_config(args.config_folder)

    if args.mode == 'download_and_transcribe':
        output_dir = os.path.join(os.getcwd(), 'videos')
        os.makedirs(output_dir, exist_ok=True)
        all_transcribed_files = []
        for url in args.urls:
            audio_file, video_folder, sanitized_title = download_youtube_video(url, output_dir)
            transcribed_files = transcribe_audio_files([audio_file], config, video_folder)
            all_transcribed_files.extend(transcribed_files)
        process_prompts_on_transcripts(all_transcribed_files, config)

    elif args.mode == 'transcribe_files':
        all_transcribed_files = []
        for audio_file in args.files:
            if not os.path.exists(audio_file):
                print(f"Error: Audio file '{audio_file}' not found.")
                continue
            output_dir = os.path.dirname(audio_file)
            transcribed_files = transcribe_audio_files([audio_file], config, output_dir)
            all_transcribed_files.extend(transcribed_files)
        process_prompts_on_transcripts(all_transcribed_files, config)

    elif args.mode == 'process_prompts':
        transcribed_files = []
        for transcript_file in args.transcripts:
            if not os.path.exists(transcript_file):
                print(f"Error: Transcript file '{transcript_file}' not found.")
                continue
            # Determine the base name and look for both txt and srt files
            base_name = os.path.splitext(transcript_file)[0]
            transcript_files = {}
            if os.path.exists(base_name + '.txt'):
                transcript_files['txt'] = base_name + '.txt'
            if os.path.exists(base_name + '.srt'):
                transcript_files['srt'] = base_name + '.srt'
            transcript_files['base'] = base_name
            transcribed_files.append(transcript_files)
        process_prompts_on_transcripts(transcribed_files, config)

if __name__ == "__main__":
    main()
