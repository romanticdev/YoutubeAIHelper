import re
import logging
import os

def setup_logging(log_level='INFO'):
    """
    Configures the logging system.

    Args:
        log_level (str): The logging level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR').

    Returns:
        logging.Logger: Configured logger instance.
    """
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(__name__)
    return logger

def sanitize_filename(filename):
    """
    Sanitizes a string to be used as a safe file or folder name.

    Args:
        filename (str): The original filename.

    Returns:
        str: Sanitized filename.
    """
    return "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()

def is_youtube_url(url):
    """
    Checks if a URL is a valid YouTube URL.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if the URL is a YouTube URL, False otherwise.
    """
    youtube_url_pattern = re.compile(
        r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
    )
    return bool(youtube_url_pattern.match(url))

def ensure_directory_exists(path):
    """
    Ensures a directory exists, creating it if necessary.

    Args:
        path (str): Path to the directory.

    Returns:
        str: The directory path (unchanged).
    """
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path

def limit_tags_to_500_chars(tags_string):
    """
    Limits the total length of a tags string to no more than 500 characters.
    The tags are expected to be in the format: 'tag1, tag2, tag3, ...'.

    Args:
        tags_string (str): A string of tags separated by commas.

    Returns:
        str: A trimmed string of tags not exceeding 500 characters.
    """
    tags_list = [tag.strip() for tag in tags_string.split(',')]
    result_tags = []
    current_length = 0

    for tag in tags_list:
        tag_length = len(tag) + (1 if result_tags else 0)  # Include comma for subsequent tags
        if ' ' in tag:
            tag_length += 2  # Account for quotes if spaces exist in a tag

        if current_length + tag_length > 500:
            break
        result_tags.append(tag)
        current_length += tag_length

    return ','.join(result_tags)

def format_duration(seconds):
    """
    Formats a duration in seconds into an HH:MM:SS string.

    Args:
        seconds (int): Duration in seconds.

    Returns:
        str: Formatted duration string.
    """
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def load_file_content(filepath, default_content=""):
    """
    Loads the content of a file, returning default content if the file doesn't exist.

    Args:
        filepath (str): Path to the file.
        default_content (str): Content to return if the file is not found.

    Returns:
        str: File content or default content.
    """
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    return default_content

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
    

def save_file_content(filepath, content):
    """
    Saves content to a file.

    Args:
        filepath (str): Path to the file.
        content (str): Content to save.
    """
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(content)
