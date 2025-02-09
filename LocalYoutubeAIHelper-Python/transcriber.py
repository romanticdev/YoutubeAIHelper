import os
import concurrent.futures
import datetime
import srt
import json
import subprocess
import tiktoken
import math
from ai_client import AIClient
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
        self.client = AIClient(self.config,self.whisper_config)

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
        
    def improve_transcription(self, folder):
        """
        Improve transcription of SRT files in a specified folder.

        Args:
            folder (str): Path to the folder containing audio files.
        """
        logger.info(f"Improving transcription for folder: {folder}")
        transcript_file =  os.path.join(folder, 'transcript.srt')
        srt_files= []
        if os.path.isfile(transcript_file):
            srt_files = [transcript_file]
        if not srt_files:
            logger.warning(f"No SRT files found in folder: {folder}")
            return
        self.improve_transcription_file(srt_files)
    
    def split_srt_file_by_tokens(self, srt_content, max_tokens, token_safety_percentage=0.75):
        """
        Splits SRT content into chunks based on token limit.
        
        Args:
            srt_content (str): Content of the SRT file.
            max_tokens (int): Maximum tokens allowed per request.
            token_safety_percentage (float): Safety margin to prevent exceeding token limit.
        
        Returns:
            List[List[srt.Subtitle]]: List of subtitle chunks.
        """
        subtitles = list(srt.parse(srt_content))
        tokenizer = tiktoken.encoding_for_model(self.config['default_model'])
        safe_token_limit = math.floor(max_tokens * token_safety_percentage)

        chunks = []
        current_chunk = []
        current_tokens = 0

        for subtitle in subtitles:
            raw_srt_block = srt.compose([subtitle])
            # Calculate the number of tokens for the raw SRT block
            subtitle_tokens = len(tokenizer.encode(raw_srt_block))
            
            # If adding this subtitle exceeds the safe token limit, finalize the current chunk
            if current_tokens + subtitle_tokens > safe_token_limit:
                chunks.append(current_chunk)
                current_chunk = [subtitle]
                current_tokens = subtitle_tokens
            else:
                current_chunk.append(subtitle)
                current_tokens += subtitle_tokens

        # Append any remaining subtitles
        if current_chunk:
            chunks.append(current_chunk)

        return chunks
      
    def improve_transcription_file(self, srt_files):
        """
        Improves transcription of SRT files by correcting grammatical errors and punctuation.
        """
        
        ## TODO
        ## - divide input srt file into chunks and improve each chunk and than combines them back
        ## - allow custom model to execute improve-srt action
        ## - support prompt or prompt file as input for the prompt.

        for srt_file in srt_files:
            logger.info(f"Improving transcription in file: {srt_file}")
            output_dir = os.path.dirname(srt_file)
            original_srt_content = load_file_content(srt_file)

            prompt_content = self.whisper_config.get('improve_srt_content', '')
            if not prompt_content:
                logger.error("We don't have 'improve_srt_content' in whisper_config.txt to process")
                return
            
            max_tokens = self.config.get('max_tokens', 4096)
            try:
                max_tokens = int(max_tokens)
            except ValueError:
                logger.error(f"Invalid 'max_tokens' value in configuration: {self.config.get('max_tokens')}. Using default value of 4096.")
                max_tokens = 4096

            # Split the SRT content into manageable chunks
            #subtitle_chunks = self.split_srt_file(original_srt_content)
            subtitle_chunks = self.split_srt_file_by_tokens(original_srt_content, max_tokens)
            logger.info(f"Divided SRT file into {len(subtitle_chunks)} token-safe chunks.")
            corrected_subtitles = []
            
            for chunk_index, chunk_subtitles in enumerate(subtitle_chunks):
                logger.info(f"Sending chunk {chunk_index+1}/{len(subtitle_chunks)} for improvement")
                chunk_srt_content = srt.compose(chunk_subtitles)
                
                messages = [
                    {"role": "system", "content": prompt_content},
                    {"role": "user", "content": chunk_srt_content},
                ]

                response = self.client.create_chat_completion(
                    messages=messages
                    ) 
                
                assistant_content = response.choices[0].message.content

                # Parse the corrected chunk and add to the list
                corrected_chunk_subtitles = list(srt.parse(assistant_content))
                corrected_subtitles.extend(corrected_chunk_subtitles)

            # Re-index subtitles
            for i, subtitle in enumerate(corrected_subtitles, 1):
                subtitle.index = i

            # Compose the full corrected SRT content
            corrected_srt_content = srt.compose(corrected_subtitles)
            
            # Define file paths
            transcript_srt = os.path.join(output_dir, 'transcript.srt')
            transcript_txt = os.path.join(output_dir, 'transcript.txt')
            transcript_llmsrt = os.path.join(output_dir, 'transcript.llmsrt')

            # Backup original files if they exist
            self.backup_file(transcript_srt, 'transcript.original.srt')
            self.backup_file(transcript_txt, 'transcript.original.txt')
            self.backup_file(transcript_llmsrt, 'transcript.original.llmsrt')

            # Save the new transcript.srt
            with open(transcript_srt, 'w', encoding='utf-8') as f:
                f.write(corrected_srt_content)
            logger.info(f"Saved improved transcription to: {transcript_srt}")

            # Generate and save transcript.txt and transcript.llmsrt
            text_content = " ".join(subtitle.content for subtitle in corrected_subtitles)
            llmsrt_content = self.convert_to_llmsrt(corrected_subtitles)

            with open(transcript_txt, 'w', encoding='utf-8') as f:
                f.write(text_content)
            logger.info(f"Saved text transcript to: {transcript_txt}")

            with open(transcript_llmsrt, 'w', encoding='utf-8') as f:
                f.write(llmsrt_content)
            logger.info(f"Saved LLM-friendly transcript to: {transcript_llmsrt}")

    def backup_file(self, original_path, backup_filename):
        """
        Creates a backup of the original file if it exists.

        Args:
            original_path (str): Path to the original file.
            backup_filename (str): Name of the backup file.
        """
        if os.path.isfile(original_path):
            backup_path = os.path.join(os.path.dirname(original_path), backup_filename)
            os.rename(original_path, backup_path)
            logger.info(f"Backed up '{original_path}' to '{backup_path}'")
            
    def transcribe_chunk(self, chunk):
        """
        Transcribes a single audio chunk using Whisper API.

        Args:
            chunk (dict): Information about the audio chunk.

        Returns:
            dict: Dictionary containing segment-level and word-level transcripts.
        """
        try:   
            response = None         
            valid_params = {"file", "model", "prompt", "response_format", "temperature", "language","timestamp_granularities"}
            # Filter the whisper_config dictionary to include only valid parameters
            filtered_whisper_config = {k: v for k, v in self.whisper_config.items() if k in valid_params}
            
            with open(chunk['file_path'], 'rb') as audio_file:
                logger.info(f"Sending chunk to Whisper API: {chunk['file_path']}")
                response = self.client.transcribe_audio(
                    audio_file=audio_file,
                    **filtered_whisper_config
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
                start = datetime.timedelta(seconds=segment.start) + start_delta
                end = datetime.timedelta(seconds=segment.end) + start_delta
                if start >= end:
                    end = start + MIN_DURATION
                segments.append(srt.Subtitle(index=i + 1, start=start, end=end, content= (segment.text or '').strip()))

            # Process words
            for i, word in enumerate(response.words):
                start = datetime.timedelta(seconds=word.start) + start_delta
                end = datetime.timedelta(seconds=word.end) + start_delta
                if start >= end:
                    end = start + MIN_DURATION                
                words.append(srt.Subtitle(index=i + 1, start=start, end=end, content=(word.word or '').strip()))

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
        # with open(raw_responses_path, 'w', encoding='utf-8') as f:
        #     json.dump(dict(raw_responses), f, indent=4)

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
