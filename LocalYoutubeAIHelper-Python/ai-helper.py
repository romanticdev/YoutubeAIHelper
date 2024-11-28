import argparse
import os
import sys
import re
import yt_dlp
import openai
import concurrent.futures
import multiprocessing
import datetime
import subprocess
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = 'token.json'
CLIENT_SECRET_FILE = 'client_secret_878642139292-8put57tbnlji1ut0f011lqpb2sq5bpda.apps.googleusercontent.com.json'  
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']



# Install the required libraries if not already installed
try:
    import srt
except ImportError:
    print("The 'srt' library is not installed. Installing now...")
    os.system(f"{sys.executable} -m pip install srt")
    import srt

# Set the desired audio bitrate for downloaded MP3 files
AUDIO_BITRATE = '12k'  # You can adjust this value as needed

# Authenticate to YouTube API
def authenticate_youtube():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('youtube', 'v3', credentials=creds)

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

    # New Subparser for updating YouTube videos
    parser_update = subparsers.add_parser('update_youtube', help='Update YouTube videos based on folder details')
    parser_update.add_argument('folder', help='Folder containing file_details.txt and optional title/description/keywords files')


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

def is_youtube_url(url):
    # Simple regex to check if the input is a valid YouTube URL
    youtube_url_pattern = re.compile(
        r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
    )
    return bool(youtube_url_pattern.match(url))

def download_youtube_video(url_or_id, output_dir):
    try:
        # Determine if input is a full URL or just a video ID
        if not is_youtube_url(url_or_id):
            # Assume it's a video ID and construct a URL
            video_id = url_or_id
            url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            url = url_or_id
            video_id = extract_youtube_id(url)
        
        if not video_id:
            print("Error: Could not extract a valid YouTube video ID.")
            sys.exit(1)

        print(f"Downloading video from URL/ID: {url} / {video_id}")
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

        # Save the YouTube video ID to file_details.txt
        file_details_path = os.path.join(video_folder, 'file_details.txt')
        with open(file_details_path, 'w') as file_details:
            file_details.write(f"youtube_id={video_id}\n")
        print(f"Saved YouTube ID to {file_details_path}")

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

def extract_youtube_id(url):
    # Enhanced regex to handle standard, shortened, and embedded YouTube URLs
    youtube_id_pattern = re.compile(
        r'(?:v=|\/|be\/|embed\/|shorts\/|youtu\.be\/|\/v\/|\/e\/|watch\?v=|&v=|youtu\.be\/|v\/|\/watch\?v=|youtube\.com\/watch\?v=|embed\/|watch\?.*&v=|\/embed\/|\/v\/)([0-9A-Za-z_-]{11})'
    )
    match = youtube_id_pattern.search(url)
    return match.group(1) if match else None       

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
        word_srt =[]

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(transcribe_chunk, chunk, whisper_config, config) for chunk in chunks]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                transcripts_srt.extend(result['srt'])  # result['srt'] is a list of srt.Subtitle objects
                word_srt.extend(result['word_srt'])
        # Combine and write SRT transcripts
        # Sort subtitles by start time
        transcripts_srt.sort(key=lambda x: x.start)
        word_srt.sort(key=lambda x: x.start)
        # Re-number subtitles
        for i, subtitle in enumerate(transcripts_srt, 1):
            subtitle.index = i

        for i, subtitle in enumerate(word_srt, 1):
            subtitle.index = i
        # Generate SRT content
        full_transcript_srt = srt.compose(transcripts_srt)

        full_transcript_word_srt = srt.compose(word_srt)

        transcript_file_temp_srt = os.path.join(output_dir, 'transcript.temp.srt')
        transcript_file_word_srt = os.path.join(output_dir, 'transcript.word.srt')
        with open(transcript_file_temp_srt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_srt)

        with open(transcript_file_word_srt, 'w', encoding='utf-8') as f:
            f.write(full_transcript_word_srt)

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
    srt_content = transcripts['segment_srt']
    word_content = transcripts['word_srt']
    # Adjust SRT timings
    adjusted_subtitles = adjust_srt_timestamps(srt_content, start_time_ms)
    adjusted_word_subtitles = adjust_srt_timestamps(word_content, start_time_ms)
    # Remove chunk file if it's a temporary split
    if is_temp:
        os.remove(audio_file)
    return { 'srt': adjusted_subtitles, 'word_srt': adjusted_word_subtitles}

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

def generate_segment_srt(segments):
    srt_content = []
    for i, segment in enumerate(segments):
        start = format_time(segment['start'])
        end = format_time(segment['end'])
        text = segment['text'].strip()
        srt_content.append(f"{i + 1}\n{start} --> {end}\n{text}\n")
    return ''.join(srt_content)

def generate_word_srt(words):
    srt_content = []
    for i, word_info in enumerate(words):
        start = format_time(word_info['start'])
        end = format_time(word_info['end'])
        text = word_info['word'].strip()
        srt_content.append(f"{i + 1}\n{start} --> {end}\n{text}\n")
    return ''.join(srt_content)

def format_time(seconds):
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

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

    params["timestamp_granularities"]=["word","segment"]
    params["response_format"] = "verbose_json"

    try:
        with open(audio_file, 'rb') as f:
            print(f"Sending audio file '{audio_file}' to Whisper API for transcription...")

            # Use the OpenAI API to transcribe the audio file
            response = client.audio.transcriptions.create(
                file=f,
                model="whisper-1",
                **params
            )

            # Parse the JSON response
            transcription = response

            # Generate segment-based SRT
            segment_srt = generate_segment_srt(transcription.segments)

            # Generate word-based SRT
            word_srt = generate_word_srt(transcription.words)

            return {
                'segment_srt': segment_srt,
                'word_srt': word_srt
            }

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

def load_variable_content(variable_name, folder):
    """
    Load the content of the file with the largest number in '{{variable}}.prompt.{{number}}.txt'.
    Treat '{{variable}}.prompt.txt' as having number 0.
    """
    # Initialize variable files list, treating the default file without a number as number 0
    variable_files = []
    default_file = os.path.join(folder, f"{variable_name}.prompt.txt")
    
    if os.path.exists(default_file):
        variable_files.append((default_file, 0))  # Treat as number 0

    # Search for numbered files
    pattern = re.compile(rf"{variable_name}\.(\d+)\.prompt\.txt$")
    
    for file_name in os.listdir(folder):
        match = pattern.match(file_name)
        if match:
            file_number = int(match.group(1))
            file_path = os.path.join(folder, file_name)
            variable_files.append((file_path, file_number))

    if not variable_files:
        return None

    # Select the file with the highest number
    file_with_largest_number = max(variable_files, key=lambda x: x[1])[0]

    #print(f"we choose {file_with_largest_number} from {variable_files}")
    
    with open(file_with_largest_number, 'r', encoding='utf-8') as file:
        return file.read()
    


def process_prompts_on_transcripts(folders, config):
    prompts_folder = config['prompts_folder']
    prompt_files = [
        os.path.join(prompts_folder, f)
        for f in os.listdir(prompts_folder)
        if os.path.isfile(os.path.join(prompts_folder, f)) and f.lower().endswith(('.txt', '.srt'))
        ]
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
        # Track generated files
        generated_files = []

        # Use multiprocessing to process each prompt in parallel
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            tasks = [
                pool.apply_async(
                    process_single_prompt,
                    args=(prompt_file, transcribed_file, folder, config)
                ) for prompt_file in prompt_files
            ]
            for task in tasks:
                result = task.get()
                if result:
                    generated_files.append(result)

        # Substitute variables in the generated files after all prompts are processed
        substitute_variables_in_files(folder, generated_files)

def substitute_variables_in_files(folder, generated_files):
    """
    Substitute '{{variable}}' in the specified generated files with the corresponding prompt content.
    """
    # Iterate only over generated files
    for file_name in generated_files:
        file_path = os.path.join(folder, file_name)
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        updated = False

        # Replace {{variable}} placeholders
        for variable_name in re.findall(r'{{(.*?)}}', content):
            replacement = load_variable_content(variable_name, folder)
            if replacement:
                updated = True
                print(f"Variable {variable_name} was found for file {file_name}")
                content = content.replace(f'{{{{{variable_name}}}}}', replacement)

        if updated:
            # Save the updated content back to the file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            print(f"Variables substituted in: {file_path}")


def generate_and_save_response(client, model, messages, temperature, max_tokens, top_p, response_format, output_extension, folder, prompt_name):
    try:
        # Generate the response using the OpenAI API
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=int(max_tokens),
            top_p=top_p,
            response_format=response_format
        )
        assistant_content = response.choices[0].message.content  # Use dot notation to access content

        # Ensure unique output filename
        output_filename = f"{prompt_name}{output_extension}"
        output_file = os.path.join(folder, output_filename)
        file_number = 1
        while os.path.exists(output_file):
            file_number += 1
            output_filename = f"{prompt_name}.{file_number}{output_extension}"
            output_file = os.path.join(folder, output_filename)

        # Save the assistant's response
        with open(output_file, 'w', encoding='utf-8') as f:
            if '.json' in output_extension:
                output_data = json.loads(assistant_content)
                json.dump(output_data, f, indent=4)
            else:
                f.write(assistant_content)
        print(f"Saved response to: {output_file}")
        return output_filename  # Return the output filename
    except Exception as e:
        print(f"Error processing prompt '{prompt_name}': {e}")


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
    temperature = float(config.get('temperature', 0.7))
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
        # Check for the presence of a corresponding JSON schema file
        schema_file = os.path.join(os.path.dirname(prompt_file), f"{prompt_name}.schema.json")
        if os.path.exists(schema_file):
            # Load the JSON schema
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema = json.load(f)

            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{prompt_name}_response",
                    "schema": schema,
                    "strict": True
                }
            }
            output_extension = '.prompt.json'
        else:
            response_format = None
            output_extension = '.prompt.txt'

        generated_file = generate_and_save_response(
            client=client,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            response_format=response_format,
            output_extension=output_extension,
            folder=folder,
            prompt_name=prompt_name
        )
        return generated_file  # Return the generated file name
    except Exception as e:
        print(f"Error processing prompt '{prompt_name}': {e}")

def get_youtube_id_from_file(file_path):
    """
    Extracts the YouTube ID from file_details.txt.
    """
    with open(file_path, 'r') as file:
        for line in file:
            if line.startswith('youtube_id='):
                return line.split('=')[1].strip()
    return None

def get_video_details(video_id):
    """
    Retrieves video details from YouTube.
    """
    youtube = authenticate_youtube()

    request = youtube.videos().list(
        part='snippet,contentDetails,statistics,status,liveStreamingDetails',
        id=video_id
    )

    response = request.execute()
    if response['items']:
        return response['items'][0]  # Return the first (and only) item
    return None

def update_video(video_id, title=None, description=None, tags=None, category_id=None):
    """
    Updates the video details on YouTube.
    """
    youtube = authenticate_youtube()

    # Fetch current video details to get the existing category if not provided
    current_video_details = get_video_details(video_id)
    if not current_video_details:
        print(f"Error: Unable to retrieve current video details for video ID '{video_id}'.")
        return

    # Use the existing category if not provided
    if not category_id:
        category_id = current_video_details['snippet'].get('categoryId', '22')  # Default to '22' (People & Blogs)

    # Prepare the request body
    snippet_body = {
        'id': video_id,
        'snippet': {
            'categoryId': category_id
        }
    }
    
    # Only update fields if values are provided
    if title:
        snippet_body['snippet']['title'] = title
    else:
        snippet_body['snippet']['title'] = current_video_details['snippet']['title']
    
    if description:
        snippet_body['snippet']['description'] = description
    else:
        snippet_body['snippet']['description'] = current_video_details['snippet']['description']
    
    if tags:
        snippet_body['snippet']['tags'] = tags
    else:
        snippet_body['snippet']['tags'] = current_video_details['snippet'].get('tags', [])

    # Update the video with the new snippet
    request = youtube.videos().update(
        part='snippet',
        body=snippet_body
    )

    response = request.execute()
    print(f"Video updated successfully: {response['snippet']['title']}")

def limit_tags_to_500_chars(tags_string):
    """
    Limit the total length of a tags string to no more than 500 characters.
    The tags are expected to be in the format: 'tag1, tag2, tag3, ...'.
    This function will ensure words are not cut off and the total length does not exceed 500 characters.
    
    Parameters:
        tags_string (str): A string of tags separated by commas.

    Returns:
        str: A trimmed string of tags not exceeding 500 characters.
    """
    # Split the tags by commas and remove leading/trailing spaces from each tag
    tags_list = [tag.strip() for tag in tags_string.split(',')]
    
    # Initialize variables to keep track of length and result tags
    result_tags = []
    current_length = 0

    for tag in tags_list:
        # Calculate the length of the tag plus the comma (if it's not the first tag)
        if result_tags:
            tag_length = len(tag) + 1  # for the comma (no space)
        else:
            tag_length = len(tag)  # no comma before the first tag
        
        # Check if adding this tag would exceed the 500 character limit
        if current_length + tag_length > 500:
            break
        # it will use double quotation mark if tag has a space
        if ' ' in tag:
            tag_length+=2

        # Add the tag to the result and update the current length
        result_tags.append(tag)
        current_length += tag_length
        
    # print (f"Length is {current_length}")
    # Join the tags back into a single string, no extra spaces
    return ','.join(result_tags)


def process_update_youtube(folder):
    """
    Process the update_youtube mode using the specified folder.
    """
    file_details_path = os.path.join(folder, 'file_details.txt')
    if not os.path.exists(file_details_path):
        print(f"Error: file_details.txt not found in '{folder}'.")
        return

    # Get YouTube ID from file_details.txt
    youtube_id = get_youtube_id_from_file(file_details_path)
    if not youtube_id:
        print(f"Error: youtube_id not found in file_details.txt in '{folder}'.")
        return
    title = None
    description = None
    tags = None

    title = load_variable_content('title',folder)
    description = load_variable_content('description',folder)
    tags = load_variable_content('keywords',folder)
    if tags:
        tags = limit_tags_to_500_chars(tags)

    # Fetch the current video details
    current_video_details = get_video_details(youtube_id)
    if not current_video_details:
        print(f"Error: Unable to retrieve video details for video ID '{youtube_id}'.")
        return

    # Use the current category ID if not updating it
    category_id = current_video_details['snippet'].get('categoryId')

    # Update video properties based on available data
    update_video(
        youtube_id,
        title=title or current_video_details['snippet']['title'],
        description=description or current_video_details['snippet']['description'],
        tags=tags or current_video_details['snippet'].get('tags', []),
        category_id=category_id
    )



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
        for folder in all_folders:
            process_update_youtube(folder)

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

    elif args.mode == 'update_youtube':
        process_update_youtube(args.folder)

if __name__ == "__main__":
    main()
