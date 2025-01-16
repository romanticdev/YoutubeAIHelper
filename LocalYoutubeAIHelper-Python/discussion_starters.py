import os
from utilities import load_file_content, ensure_directory_exists, load_variable_content
from prompt_processor import PromptProcessor
from config import CONFIG, WHISPER_CONFIG, load_config_from_folder
from youtube_update import YouTubeUpdater
from downloader import Downloader
from transcriber import Transcriber
from prompt_processor import PromptProcessor
from news_extractor import NewsExtractor


class DiscussionStarters:
    def __init__(self, config, whisper_config, number_of_streams=3):
        self.config = config
        self.whisper_config = whisper_config
        self.prompt_processor = PromptProcessor(config)
        self.downloader = Downloader(config)
        self.youtube_updater = YouTubeUpdater(config)
        self.prompt_processor = PromptProcessor(config)
        self.transcriber = Transcriber(config, whisper_config)
        self.number_of_streams = number_of_streams
        
        self.news_extractor = NewsExtractor(config)

    def prepare_last_streams(self):
        """
        Ensures we have the last N completed live streams locally.
        1. Uses YouTubeUpdater to get last N streams (video IDs).
        2. Checks local `videos/` folder to find matches (looking for file_details.txt).
        3. If not found locally, download the video.
        4. Return a list of local directories corresponding to the N streams.
        """
        
        video_ids = self.youtube_updater.get_last_streams(self.number_of_streams)
        if not video_ids:
            # Handle no videos found
            return []

        videos_path = self.config.get('default_output_dir', 'videos')
        ensure_directory_exists(videos_path)

        local_stream_dirs = []

        for vid_id in video_ids:
            matched_dir = self.find_local_stream_by_id(vid_id)
            if not matched_dir:
                # Download the video
                url = f"https://www.youtube.com/watch?v={vid_id}"
                # The downloader returns (ogg_file_path, video_folder, sanitized_title)
                _, video_folder, _ = self.downloader.download_youtube_video(url, videos_path)
                matched_dir = video_folder
                
            self.ensure_transcription_and_prompts(matched_dir)
            local_stream_dirs.append(matched_dir)

        return local_stream_dirs

    def find_local_stream_by_id(self, youtube_id):
        """
        Searches the local `videos/` directory for a folder containing a `file_details.txt`
        with `youtube_id=<youtube_id>`.
        If found, returns the folder path; otherwise returns None.
        """
        videos_path = self.config.get('default_output_dir', 'videos')
        if not os.path.exists(videos_path):
            return None

        for folder in os.listdir(videos_path):
            folder_path = os.path.join(videos_path, folder)
            if os.path.isdir(folder_path):
                file_details_path = os.path.join(folder_path, 'file_details.txt')
                if os.path.isfile(file_details_path):
                    content = load_file_content(file_details_path)
                    # Check if youtube_id matches
                    for line in content.splitlines():
                        if line.strip().startswith('youtube_id='):
                            found_id = line.strip().split('=', 1)[1]
                            if found_id == youtube_id:
                                return folder_path
        return None
    
    
    def ensure_transcription_and_prompts(self, video_folder):
        """
        Ensures that the given `video_folder` has a transcript and that prompts (like summaries) are run.
        Steps:
        - Check if transcript.txt exists. If not, run transcription.
        - Run prompt_processor to generate summaries or other configured prompts.

        This mimics the 'full-process' for a single video folder.
        """
        transcript_txt_path = os.path.join(video_folder, 'transcript.txt')

        # Transcribe if transcript doesn't exist
        if not os.path.exists(transcript_txt_path):
            self.transcriber.transcribe_folder(video_folder)
            self.transcriber.improve_transcription(video_folder)

        # Now run prompts (e.g., summary or other configured prompts)
        # Ensure we have prompts. If you have a summary prompt or other prompts in the configuration,
        # they will be run here. The prompt_processor by default processes all prompts in the
        # `prompts` folder of the current configuration.
        prompt_txt_path = os.path.join(video_folder, 'summary.prompt.txt')
        if not os.path.exists(prompt_txt_path):
            self.prompt_processor.process_prompts_on_transcripts([video_folder])
    
    def load_context(self):
        streams = self.prepare_last_streams()
        if len(streams) < self.number_of_streams:
            # Handle case if fewer than 6 processed streams exist.
            # For now, just return what we have or raise an error.
            pass

        current_stream = streams[0]  # last processed stream
        previous_streams = streams[1:]

        # Load current transcript
        current_transcript_path = os.path.join(current_stream, 'transcript.txt')
        current_transcript = load_file_content(current_transcript_path, "No transcript found.")

        # Load summaries for previous 5 streams
        summaries = []
        for s in previous_streams:
            summary = load_variable_content("summary", s)
            summaries.append(f"Stream: {s}\n{summary}")

        previous_summaries = "\n\n".join(summaries)
        
        top_stories_token = self.config.get('google_top_stories_token', 'CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZxYUdjU0FtVnVHZ0pWVXlnQVAB')
        
        general_news_raw = self.news_extractor.get_general_news(num_results=3, topic_token=top_stories_token)
        ai_news_raw = self.news_extractor.get_ai_news(num_results=3)
        # we will use 6*4 = 24 tokens for news (from 50 daily)

        return current_transcript, previous_summaries, general_news_raw, ai_news_raw

    def build_prompt(self, current_transcript, previous_summaries, world_news, ai_news):
        # Load the discussion_starters prompt template
        prompt_file = os.path.join(self.config['prompts_folder'], 'discussion_starters.custom')
        base_prompt = load_file_content(prompt_file, "No prompt template found.")

        # Perform variable substitution
        prompt = base_prompt.replace("{{CURRENT_TRANSCRIPT}}", current_transcript)
        prompt = prompt.replace("{{NUMBER_OF_STREAMS}}", str(self.number_of_streams))
        prompt = prompt.replace("{{PREVIOUS_SUMMARIES}}", previous_summaries)
        prompt = prompt.replace("{{WORLD_NEWS}}", world_news)
        prompt = prompt.replace("{{AI_NEWS}}", ai_news)

        return prompt

    def generate_questions(self):
        current_transcript, previous_summaries, world_news, ai_news = self.load_context()
        prompt_content = self.build_prompt(current_transcript, previous_summaries, world_news, ai_news)

        # Use the PromptProcessor to call the model
        messages = [
            {"role": "user", "content": prompt_content},
        ]

        # Directly call create_chat_completion here or add a dedicated prompt file:
        response = self.prompt_processor.client.create_chat_completion(messages=messages)
        return response.choices[0].message.content
    
    
    def _format_news_for_prompt(self, news_list):
        """
        Given a list of news article dicts, build a bullet-point string
        for use in prompt context.
        """
        if not news_list:
            return "No news available."

        lines = []
        for i, article in enumerate(news_list, 1):
            line = (
                f"{i}. {article.get('title','No Title')} "
                f"(Source: {article.get('source','Unknown')})\n"
                f"   Link: {article.get('link')}\n"
                f"   Date: {article.get('date')}\n"
                f"   Text: {article.get('text')}\n"
            )
            lines.append(line)
        return "\n".join(lines)