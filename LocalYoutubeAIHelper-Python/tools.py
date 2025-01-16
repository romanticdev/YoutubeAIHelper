# tools.py
import os
from utilities import load_file_content, \
ensure_directory_exists, load_variable_content, get_active_transcript_file
from discussion_starters import DiscussionStarters
from news_extractor import NewsExtractor
from config import CONFIG, WHISPER_CONFIG, load_config_from_folder


discussion = DiscussionStarters(config=CONFIG, whisper_config=WHISPER_CONFIG,number_of_streams=5)
news = NewsExtractor(config=CONFIG)


def get_last_stream_context() -> str:
    """
    Returns a short context from the last live stream.
    """
    streams = discussion.prepare_last_streams()
    if not streams:
        return "No streams available."
    last_stream = streams[0]

    current_transcript_path = os.path.join(last_stream, 'transcript.txt')
    current_transcript = load_file_content(current_transcript_path, "No transcript found.")
    full_context = f"Full content from the last stream in text format: {current_transcript}"
    return full_context

def get_last_5_streams_summaries() -> str:
    """
    Returns multiple summaries from the last streams.
    """
    streams = discussion.prepare_last_streams()
    if not streams:
        return "No streams available."

    summaries = []
    index = 1
    for s in streams:
        summary = load_variable_content("summary", s)
        summaries.append(f"Stream {index} summary: {s}\n{summary}")
        index += 1

    previous_summaries = "\n\n".join(summaries)
    return f"Summaries of 5 previous streams (indexing is from the most distant to most recent):\n{previous_summaries}"


def get_latest_ai_news() -> str:
    """
    Returns a single, random AI news item from the extracted news list.
    """

    ai_news = news.get_ai_news(num_results=5)
    if not ai_news:
        return "No AI news available."
    # Return just the first one or a random item
    return f"Latest AI News : {ai_news}"


def get_latest_general_news() -> str:
    """
    Returns a single, random general news item.    
    """  
    general_news = news.get_general_news(num_results=5)
    if not general_news:
        return "No general news available."
    return f"The Latest General News : {general_news}"

def get_stream_info() -> str:
    """
    Reads a 'stream_info.txt' file that provides global context about the host, 
    or the series of streams. 
    Returns its content or 'No info found' if missing.
    """
    # For example, we assume 'stream_info.txt' is in the same folder 
    # as your config, or we can read from a known path.
    ai_config, whisper_config = load_config_from_folder('configurations/aibot')
    config_folder = ai_config['config_folder']
    info_path = os.path.join(config_folder, 'stream_info.txt')
    info_content = load_file_content(info_path, "No global stream info found.")
    return info_content

def get_current_realtime_stream_content() -> str:
    path = get_active_transcript_file("transcripts", cutoff_minutes=60)
    if not os.path.exists(path):
        return "No real-time transcription available yet."
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if len(content) > 5000:
        return "..." + content[-5000:]
    return content