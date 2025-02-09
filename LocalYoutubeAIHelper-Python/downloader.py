import os
import re
import subprocess
from yt_dlp import YoutubeDL
from utilities import sanitize_filename, is_youtube_url, setup_logging
logger = setup_logging()

class Downloader:
    def __init__(self, config):
        """
        Initializes the Downloader with the provided configuration.
        """
        self.audio_bitrate = config.get('audio_bitrate', '12k')
        self.output_dir = config.get('default_output_dir', 'output')

    @staticmethod
    def is_valid_media_file(file_path):
        """
        Check if the file is a valid media file by extension.
        """
        valid_extensions = ['.mp4', '.mkv', '.mp3', '.wav', '.webm']
        _, ext = os.path.splitext(file_path)
        return ext.lower() in valid_extensions
    
    def download_youtube_video(self, url_or_id, output_dir=None):
        """
        Downloads a YouTube video, extracts audio, and converts it to OGG format.

        Args:
            url_or_id (str): The YouTube URL or video ID to download.
            output_dir (str): The directory to save the downloaded files.

        Returns:
            tuple: (audio_file_path, video_folder_path, sanitized_title)
        """
        try:
            # Set output directory
            output_dir = output_dir or self.output_dir

            # Validate the URL or extract video ID
            if not is_youtube_url(url_or_id):
                video_id = url_or_id
                url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                url = url_or_id
                video_id = self.extract_youtube_id(url)

            if not video_id:
                raise ValueError("Invalid YouTube URL or video ID.")

            # Extract video metadata
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'video')
                sanitized_title = sanitize_filename(title)

            logger.info(f"Downloading video: {title} ({video_id})")

            # Create directory for video files
            video_folder = os.path.join(output_dir, sanitized_title)
            os.makedirs(video_folder, exist_ok=True)

            # Save video metadata
            file_details_path = os.path.join(video_folder, 'file_details.txt')
            with open(file_details_path, 'w') as file:
                file.write(f"youtube_id={video_id}\n")
            logger.info(f"Saved video details to {file_details_path}")

            # Download video audio
            audio_path = os.path.join(video_folder, f"{sanitized_title}.%(ext)s")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_path,
                'quiet': False,
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                info_dict = ydl.extract_info(url, download=False)
                actual_ext = info_dict.get('ext', 'webm')  # Get the actual extension used

            downloaded_audio_path = os.path.join(video_folder, f"{sanitized_title}.{actual_ext}")

            # Convert audio to OGG format
            ogg_file_path = self.convert_to_ogg(downloaded_audio_path, video_folder, sanitized_title)

            logger.info(f"Download and conversion complete: {ogg_file_path}")
            return ogg_file_path, video_folder, sanitized_title

        except Exception as e:
            logger.error(f"Error downloading or processing video: {e}")
            raise

    def convert_to_ogg(self, input_path, output_dir, output_name):
        """
        Converts an audio file to OGG format using ffmpeg.

        Args:
            input_path (str): Path to the input audio file.
            output_dir (str): Directory to save the converted file.
            output_name (str): Name of the output file (without extension).

        Returns:
            str: Path to the converted OGG file.
        """
        ogg_file_path = os.path.join(output_dir, f"{output_name}.ogg")
        ffmpeg_command = [
            'ffmpeg', '-i', input_path, '-vn', '-map_metadata', '-1', '-ac', '1',
            '-c:a', 'libopus', '-b:a', self.audio_bitrate, '-application', 'voip', ogg_file_path
        ]
        try:
            subprocess.run(ffmpeg_command, check=True)
            #os.remove(input_path)  # Clean up the original file
            logger.info(f"Converted {input_path} to OGG: {ogg_file_path}")
            return ogg_file_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            raise

    @staticmethod
    def extract_youtube_id(url):
        """
        Extracts the YouTube video ID from a URL.

        Args:
            url (str): The YouTube URL.

        Returns:
            str: The extracted video ID, or None if extraction fails.
        """
        youtube_id_pattern = re.compile(
            r'(?:v=|\/|be\/|embed\/|shorts\/|youtu\.be\/|\/v\/|\/e\/|watch\?v=|&v=|youtube\.com\/watch\?v=)([0-9A-Za-z_-]{11})'
        )
        match = youtube_id_pattern.search(url)
        return match.group(1) if match else None
