import argparse
import os
import sys
import re
import yt_dlp
import openai
import concurrent.futures
import datetime
import subprocess

# Install the required libraries if not already installed
try:
    import srt
except ImportError:
    print("The 'srt' library is not installed. Installing now...")
    os.system(f"{sys.executable} -m pip install srt")
    import srt

# Set the desired audio bitrate for downloaded MP3 files
AUDIO_BITRATE = '12k'  # You can adjust this value as needed

def extract_text_from_srt(srt_content):
    """
    Extracts the plain text from the given SRT content.
    
    Parameters:
    srt_content (str): The content of the SRT file as a string.
    
    Returns:
    str: The extracted plain text.
    """
    subtitles = list(srt.parse(srt_content))
    texts = [subtitle.content for subtitle in subtitles]
    return '\n'.join(texts)

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

        # Extract info for title and sanitization
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            title = info_dict.get('title', 'video')
            sanitized_title = sanitize_filename(title)
            print(f"RAW title: {title}")
            print(f"Sanitized title: {sanitized_title}")

        # Create directory for downloaded files
        video_folder = os.path.join(output_dir, sanitized_title)
        os.makedirs(video_folder, exist_ok=True)

        # yt-dlp options to download the original audio format (webm/m4a)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(video_folder, f"{sanitized_title}.%(ext)s"),
            'quiet': False,
        }

        # Download the original audio (e.g., webm or m4a) using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])

            # Get the downloaded file's information
            info_dict = ydl.extract_info(url, download=False)
            actual_ext = info_dict.get('ext', 'webm')  # Get the actual extension used

        # Locate the downloaded audio file with the correct extension
        original_audio_path = os.path.join(video_folder, f"{sanitized_title}.{actual_ext}")
        ogg_file = os.path.join(video_folder, f"{sanitized_title}.ogg")

        # Convert original audio to ogg using ffmpeg with specified parameters
        ffmpeg_command = [
            'ffmpeg', '-i', original_audio_path, '-vn', '-map_metadata', '-1', '-ac', '1',
            '-c:a', 'libopus', '-b:a', AUDIO_BITRATE, '-application', 'voip', ogg_file
        ]

        print(f"Converting {original_audio_path} to OGG format with specified parameters.")
        subprocess.run(ffmpeg_command, check=True)

        print(f"Downloaded and converted audio saved to: {ogg_file}")
        return ogg_file, video_folder, sanitized_title

    except Exception as e:
        print(f"Error downloading or converting video from {url}: {e}")
        sys.exit(1)

def split_audio_ffmpeg(input_file, start_time, end_time, output_file):
    # Convert start_time and end_time to a format suitable for ffmpeg
    start_time_str = str(datetime.timedelta(milliseconds=start_time))
    duration_ms = end_time - start_time
    duration_str = str(datetime.timedelta(milliseconds=duration_ms))

    command = [
        'ffmpeg', '-y', '-i', input_file,
        '-ss', start_time_str, '-t', duration_str,
        '-ac', '1', '-c:a', 'libopus', '-b:a', AUDIO_BITRATE, '-application', 'voip', output_file
    ]
    
    subprocess.run(command, check=True)

def get_audio_duration(file_path):
    try:
        # Use ffprobe to get duration
        command = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', f'"{file_path}"'
        ]
        result = subprocess.run(" ".join(command), shell=True, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip()) * 1000  # Convert seconds to milliseconds
        return duration
    except Exception as e:
        print(f"Error retrieving audio duration: {e}")
        return None

def split_audio_file(file_path, chunk_length_ms=4 * 60 * 60 * 1000, overlap_ms=10000):
    # Check the file size and skip splitting if under 24.8 MB
    file_size = os.path.getsize(file_path)
    if file_size <= 24.8 * 1024 * 1024:
        return [{'file_path': file_path, 'start_time': 0, 'is_temp': False}]
    
    # Get duration of audio file
    duration_ms = get_audio_duration(file_path)
    if duration_ms is None:
        return []

    print(f"Audio file '{file_path}' is larger than 24.8 MB. Splitting into 4-hour chunks with 10s overlap...")
    chunks = []
    start = 0
    while start < duration_ms:
        end = min(start + chunk_length_ms, duration_ms)
        chunk_filename = f"{os.path.splitext(file_path)[0]}_part{start // 1000}-{end // 1000}.ogg"
        
        # Use ffmpeg to create the chunk
        split_audio_ffmpeg(file_path, start, end, chunk_filename)
        chunks.append({'file_path': chunk_filename, 'start_time': start, 'is_temp': True})
        
        print(f"Created chunk: {chunk_filename}, Start time: {start} ms")
        start += chunk_length_ms - overlap_ms
    
    return chunks

def transcribe_audio_files(audio_files, config, whisper_config):
    openai.api_key = config['openai_api_key']

    for audio_file in audio_files:
        print(f"Transcribing audio file: {audio_file}")
        chunks = split_audio_file(audio_file)
        output_dir = os.path.dirname(audio_file)
        transcripts_srt = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(transcribe_chunk, chunk, whisper_config, config) for chunk in chunks]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                transcripts_srt.extend(result['srt'])  # result['srt'] is a list of srt.Subtitle objects

        # Combine and write SRT transcripts
        # Sort subtitles by start time
        transcripts_srt.sort(key=lambda x: x.start)
        # Re-number subtitles
        for i, subtitle in enumerate(transcripts_srt, 1):
            subtitle.index = i
        # Generate SRT content
        full_transcript_srt = srt.compose(transcripts_srt)

        transcript_file_temp_srt = os.path.join(output_dir, 'transcript.temp.srt')
        with open(transcript_file_temp_srt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_srt)

        # TODO :: Clean up the transcript only if there are multiple chunks
        cleaned_transcript_srt = full_transcript_srt        
       
        transcript_file_srt = os.path.join(output_dir, 'transcript.srt')
        with open(transcript_file_srt, 'w', encoding='utf-8') as f:
            f.write(cleaned_transcript_srt)
        print(f"Saved cleaned transcription to: {transcript_file_srt}")

        # Extract text from cleaned SRT and save as TXT
        full_transcript_txt = extract_text_from_srt(cleaned_transcript_srt)
        transcript_file_txt = os.path.join(output_dir, 'transcript.txt')
        with open(transcript_file_txt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_txt)
        print(f"Saved text transcription to: {transcript_file_txt}")

        # Convert cleaned SRT to custom format and save as llmsrt
        llmsrt_content, total_length_seconds = convert_srt_to_custom_format(cleaned_transcript_srt)
        transcript_file_llmsrt = os.path.join(output_dir, 'transcript.llmsrt')
        with open(transcript_file_llmsrt, 'w', encoding='utf-8') as f:
            f.write(llmsrt_content)
        print(f"Saved simplified transcription to: {transcript_file_llmsrt}")

def transcribe_chunk(chunk, whisper_config, config):
    openai_api_key = config['openai_api_key']
    audio_file = chunk['file_path']
    start_time_ms = chunk['start_time']
    is_temp = chunk['is_temp']
    transcripts = transcribe_with_whisper_api(audio_file, openai_api_key, whisper_config)
    srt_content = transcripts['srt']
    # Adjust SRT timings
    adjusted_subtitles = adjust_srt_timestamps(srt_content, start_time_ms)
    # Remove chunk file if it's a temporary split
    if is_temp:
        os.remove(audio_file)
    return { 'srt': adjusted_subtitles}

def adjust_srt_timestamps(srt_content, start_time_ms):
    subtitles = list(srt.parse(srt_content))
    start_time = datetime.timedelta(milliseconds=start_time_ms)
    for subtitle in subtitles:
        subtitle.start += start_time
        subtitle.end += start_time
    return subtitles

def convert_srt_to_custom_format(srt_content):
    subtitles = list(srt.parse(srt_content))
    formatted_lines = []
    last_timestamp = "00:00:00"

    for subtitle in subtitles:
        hours = subtitle.start.seconds // 3600
        minutes = (subtitle.start.seconds % 3600) // 60
        seconds = subtitle.start.seconds % 60
        milliseconds = subtitle.start.microseconds // 1000
        timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        last_timestamp = timestamp
        formatted_line = f"[{timestamp}] {subtitle.content}"
        formatted_lines.append(formatted_line)

    # Calculate the total length in seconds from the last timestamp
    hours, minutes, seconds = map(int, last_timestamp.split(":"))
    total_length_seconds = hours * 3600 + minutes * 60 + seconds

    formatted_text = "\n".join(formatted_lines)
    return formatted_text, total_length_seconds

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

def clean_up_transcript(full_transcript_srt, config):
    # Initialize OpenAI API client
    client = openai.OpenAI(api_key=config['openai_api_key'])

    # Prepare messages for ChatGPT
    messages = [
        {
            "role": "system",
            "content": """You are an assistant that cleans up SRT transcripts 
            by removing duplicate subtitles caused by overlapping audio chunks.
            Return only the cleaned SRT content without any additional text, instructions,
            or explanations."""
        },
        {
            "role": "user",
            "content": f"""The following SRT transcript was generated from overlapping 
            audio chunks with about 5 seconds overlap between each chunk. The chunk size is
            30 minutes long, so expect most work at 30:00, 1:00:00 and so on.
            Please remove any duplicate subtitles caused by the overlap and 
            provide only the cleaned-up, properly formatted SRT content.\n\n{full_transcript_srt}"""
        },
    ]

    try:
        max_tokens = config['max_tokens']
        # Call OpenAI ChatCompletion API
        response = client.chat.completions.create(
            model=config['model'],
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        cleaned_transcript_srt = response.choices[0].message.content
        return cleaned_transcript_srt
    except Exception as e:
        print(f"Error cleaning up transcript: {e}")
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

        transcribed_file = {'base': os.path.join(folder, 'transcript')}
        transcript_txt = os.path.join(folder, 'transcript.txt')
        transcript_srt = os.path.join(folder, 'transcript.srt')
        transcript_llmsrt = os.path.join(folder, 'transcript.llmsrt')
        if os.path.exists(transcript_txt):
            transcribed_file['txt'] = transcript_txt
        if os.path.exists(transcript_srt):
            transcribed_file['srt'] = transcript_srt
        if os.path.exists(transcript_llmsrt):
            transcribed_file['llmsrt'] = transcript_llmsrt

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
    temperature = float(config.get('temperature', 1.0))
    top_p = float(config.get('top_p', 1.0))

    # Use appropriate transcribed file based on extension
    if prompt_ext == '.srt':
        user_content_file = transcribed_file.get('llmsrt')
    else:
        user_content_file = transcribed_file.get('txt')

    if not user_content_file or not os.path.exists(user_content_file):
        print(f"Error: Transcribed file '{user_content_file}' not found.")
        return

    total_length = 0

    # Read the user content from the transcribed file
    with open(user_content_file, 'r', encoding='utf-8') as f:
        user_content = f.read()

    if prompt_ext == '.srt':
        total_length = get_total_length_from_llmsrt(user_content)

    # Replace '{transcript_length}' in user_content with total_length, if it exists
    if '{transcript_length}' in user_content:
        user_content = user_content.replace('{transcript_length}', str(total_length))

    messages = [
        {"role": "system", "content": prompt_content},
        {"role": "user", "content": user_content}
    ]

    try:
        # Use the updated ChatCompletion API
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=int(max_tokens),
            top_p=top_p
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

def get_total_length_from_llmsrt(llmsrt_content):
    last_line = llmsrt_content.strip().split('\n')[-1]
    match = re.match(r'\[(\d{2}):(\d{2}):(\d{2})\]', last_line)
    if match:
        hours, minutes, seconds = map(int, match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds
    return 0

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
            audio_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.ogg')]
            if not audio_files:
                print(f"No ogg files found in folder '{folder}'.")
                continue
            transcribe_audio_files(audio_files, config, whisper_config)

    elif args.mode == 'process_prompts':
        process_prompts_on_transcripts(args.folders, config)

if __name__ == "__main__":
    main()
