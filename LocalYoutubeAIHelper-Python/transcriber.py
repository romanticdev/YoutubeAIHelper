import os
import concurrent.futures
import datetime
import srt
import json
import openai
from utilities import setup_logging, ensure_directory_exists, load_file_content, save_file_content
from config import CONFIG

logger = setup_logging()

class Transcriber:
    def __init__(self, config, whisper_config):
        """
        Initializes the Transcriber with configuration settings.

        Args:
            config (dict): General configuration settings.
            whisper_config (dict): Whisper-specific configuration settings.
        """
        self.config = config
        self.whisper_config = whisper_config
        self.whisper_config['timestamp_granularities'] = ['word', 'segment']  # Ensure both word and segment levels
        openai.api_key = config['openai_api_key']

    def transcribe_audio_files(self, audio_files):
        """
        Transcribes a list of audio files using OpenAI's Whisper API.

        Args:
            audio_files (list): List of audio file paths.
        """
        for audio_file in audio_files:
            logger.info(f"Transcribing audio file: {audio_file}")
            chunks = self.split_audio_file(audio_file)
            output_dir = os.path.dirname(audio_file)
            transcripts = {'segments': [], 'words': [], 'raw_responses': [] }

            # Transcribe chunks in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self.transcribe_chunk, chunk) for chunk in chunks]
                for future in concurrent.futures.as_completed(futures):
                    chunk_result = future.result()
                    transcripts['segments'].extend(chunk_result['segments'])
                    transcripts['words'].extend(chunk_result['words'])
                    transcripts['raw_responses'].extend(chunk_result['response'])

            # Combine transcripts and save results
            self.save_transcripts(output_dir, transcripts)

    def transcribe_folder(self, folder):
        """
        Transcribes all audio files in a specified folder.

        Args:
            folder (str): Path to the folder containing audio files.
        """
        logger.info(f"Transcribing folder: {folder}")
        audio_files = [
            os.path.join(folder, file)
            for file in os.listdir(folder)
            if file.endswith('.ogg') or file.endswith('.mp3')
        ]
        if not audio_files:
            logger.warning(f"No audio files found in folder: {folder}")
            return
        self.transcribe_audio_files(audio_files)

    def transcribe_chunk(self, chunk):
        """
        Transcribes a single audio chunk using Whisper API.

        Args:
            chunk (dict): Information about the audio chunk.

        Returns:
            dict: Dictionary containing segment-level and word-level transcripts.
        """
        try:
            client = openai.OpenAI(api_key=self.config['openai_api_key'])

            with open(chunk['file_path'], 'rb') as audio_file:
                logger.info(f"Sending chunk to Whisper API: {chunk['file_path']}")
                response = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    **self.whisper_config
                )
                result = self.process_whisper_response(response, chunk['start_time'])
                if chunk['is_temp']:
                    os.remove(chunk['file_path'])  # Cleanup temporary chunk
                result['response']=response
                return result
        except Exception as e:
            logger.error(f"Error transcribing chunk: {e}")
            return {'segments': [], 'words': [], 'response': response}

    def process_whisper_response(self, response, start_time_ms):
        """
        Processes the Whisper API response to generate subtitles and word-level transcripts.

        Args:
            response (dict): Whisper API response.
            start_time_ms (int): Start time of the chunk in milliseconds.

        Returns:
            dict: Dictionary containing segment-level and word-level transcripts.
        """
        MIN_DURATION = datetime.timedelta(milliseconds=10)  # 0.01 seconds
        try:
            start_delta = datetime.timedelta(milliseconds=start_time_ms)
            segments = []
            words = []

            # Process segments
            for i, segment in enumerate(response.segments):
                start = datetime.timedelta(seconds=segment['start']) + start_delta
                end = datetime.timedelta(seconds=segment['end']) + start_delta
                if start >= end:
                    end = start + MIN_DURATION
                segments.append(srt.Subtitle(index=i + 1, start=start, end=end, content=segment.get('text', '').strip()))

            # Process words
            for i, word in enumerate(response.words):
                start = datetime.timedelta(seconds=word['start']) + start_delta
                end = datetime.timedelta(seconds=word['end']) + start_delta
                if start >= end:
                    end = start + MIN_DURATION                
                words.append(srt.Subtitle(index=i + 1, start=start, end=end, content=word.get('word', '').strip()))

            return {'segments': segments, 'words': words}
        except Exception as e:
            logger.error(f"Error processing Whisper response: {e}")
            return {'segments': [], 'words': []}

    def split_audio_file(self, file_path, chunk_length_ms=4 * 60 * 60 * 1000, overlap_ms=10000):
        """
        Splits an audio file into chunks for transcription.

        Args:
            file_path (str): Path to the audio file.
            chunk_length_ms (int): Length of each chunk in milliseconds.
            overlap_ms (int): Overlap between chunks in milliseconds.

        Returns:
            list: List of dictionaries containing chunk information.
        """
        file_size = os.path.getsize(file_path)
        if file_size <= 24.8 * 1024 * 1024:
            return [{'file_path': file_path, 'start_time': 0, 'is_temp': False}]

        duration_ms = self.get_audio_duration(file_path)
        if duration_ms is None:
            return []

        logger.info(f"Splitting audio file '{file_path}' into chunks...")
        chunks = []
        start = 0
        while start < duration_ms:
            end = min(start + chunk_length_ms, duration_ms)
            chunk_filename = f"{os.path.splitext(file_path)[0]}_part{start // 1000}-{end // 1000}.ogg"
            self.split_audio_ffmpeg(file_path, start, end, chunk_filename)
            chunks.append({'file_path': chunk_filename, 'start_time': start, 'is_temp': True})
            start += chunk_length_ms - overlap_ms
        return chunks

    def split_audio_ffmpeg(self, input_file, start_time, end_time, output_file):
        """
        Splits an audio file into a specific segment using ffmpeg.

        Args:
            input_file (str): Path to the input file.
            start_time (int): Start time of the segment in milliseconds.
            end_time (int): End time of the segment in milliseconds.
            output_file (str): Path to the output file.
        """
        start_time_str = str(datetime.timedelta(milliseconds=start_time))
        duration_str = str(datetime.timedelta(milliseconds=end_time - start_time))
        command = [
            'ffmpeg', '-y', '-i', input_file,
            '-ss', start_time_str, '-t', duration_str,
            '-ac', '1', '-c:a', 'libopus', '-b:a', self.config['audio_bitrate'], '-application', 'voip', output_file
        ]
        try:
            subprocess.run(command, check=True)
            logger.info(f"Created chunk: {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error splitting audio with ffmpeg: {e}")

    def get_audio_duration(self, file_path):
        """
        Gets the duration of an audio file using ffprobe.

        Args:
            file_path (str): Path to the audio file.

        Returns:
            float: Duration in milliseconds.
        """
        try:
            command = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', file_path
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return float(result.stdout.strip()) * 1000  # Convert seconds to milliseconds
        except Exception as e:
            logger.error(f"Error retrieving audio duration: {e}")
            return None

    def save_transcripts(self, output_dir, transcripts):
        """
        Saves the combined transcript as SRT, plain text, and word-level SRT files.

        Args:
            output_dir (str): Directory to save the transcript files.
            transcripts (dict): Dictionary containing segment-level and word-level transcripts.
        """
        # Ensure output directory exists
        ensure_directory_exists(output_dir)

        # Segment-level transcripts
        segments = transcripts['segments']
        segments.sort(key=lambda x: x.start)
        for i, segment in enumerate(segments, 1):
            segment.index = i
        srt_content = srt.compose(segments)
        text_content = " ".join(segment.content for segment in segments)

        # Word-level transcripts
        words = transcripts['words']
        words.sort(key=lambda x: x.start)
        for i, word in enumerate(words, 1):
            word.index = i
        word_srt_content = srt.compose(words)

        # Generate LLM-friendly SRT content
        llmsrt_content = self.convert_to_llmsrt(segments)

        # Save raw responses as JSON
        raw_responses = transcripts['raw_responses']
        raw_responses_path = os.path.join(output_dir, 'raw_responses.json')
        with open(raw_responses_path, 'w', encoding='utf-8') as f:
            json.dump(raw_responses, f, indent=4)

        # Save files
        save_file_content(os.path.join(output_dir, 'transcript.srt'), srt_content)
        save_file_content(os.path.join(output_dir, 'transcript.txt'), text_content)
        save_file_content(os.path.join(output_dir, 'transcript.word.srt'), word_srt_content)
        save_file_content(os.path.join(output_dir, 'transcript.llmsrt'), llmsrt_content)

        logger.info(f"Saved transcript files in {output_dir}")

    def convert_to_llmsrt(self, subtitles):
        """
        Converts SRT subtitles into a simplified format for LLMs.

        Args:
            subtitles (list): List of srt.Subtitle objects.

        Returns:
            str: Simplified transcript content.
        """
        formatted_lines = []
        for subtitle in subtitles:
            timestamp = str(subtitle.start).split('.')[0]  # Keep only HH:MM:SS
            formatted_lines.append(f"[{timestamp}] {subtitle.content}")
        return "\n".join(formatted_lines)
