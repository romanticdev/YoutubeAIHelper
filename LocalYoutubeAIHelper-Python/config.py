import os
from dotenv import load_dotenv
from utilities import setup_logging

logger = setup_logging()

current_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the .env file in the same directory
env_path = os.path.join(current_dir, 'local.env')

# Load environment variables from the .env file
load_dotenv(env_path)

# YouTube API configuration
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
TOKEN_FILE = os.getenv('TOKEN_FILE', 'token.json')
CLIENT_SECRET_FILE = os.getenv('CLIENT_SECRET_FILE', 'client_secret_youtube.json')

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
logger.info(f"OpenAI API Key Loaded: {'Yes' if OPENAI_API_KEY else 'No'}")

DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'gpt-4o')
MAX_TOKENS = int(os.getenv('MAX_TOKENS', 16000))

# Audio settings
AUDIO_BITRATE = os.getenv('AUDIO_BITRATE', '12k')  # Default to 12 kbps

# Paths
DEFAULT_OUTPUT_DIR = os.getenv('DEFAULT_OUTPUT_DIR', 'videos')
DEFAULT_CONFIG_FOLDER = os.getenv('DEFAULT_CONFIG_FOLDER', 'configurations/generic')
PROMPTS_FOLDER = os.path.join(DEFAULT_CONFIG_FOLDER, 'prompts')

# Whisper-specific configuration
WHISPER_CONFIG = {
    'temperature': float(os.getenv('WHISPER_TEMPERATURE', '0.7')),
    'response_format': os.getenv('WHISPER_RESPONSE_FORMAT', 'verbose_json'),
    'language': os.getenv('WHISPER_LANGUAGE', 'en')
}

# General settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Combined configuration for convenience
CONFIG = {
    'scopes': SCOPES,
    'token_file': TOKEN_FILE,
    'client_secret_file': CLIENT_SECRET_FILE,
    'openai_api_key': OPENAI_API_KEY,
    'default_model': DEFAULT_MODEL,
    'max_tokens': MAX_TOKENS,
    'audio_bitrate': AUDIO_BITRATE,
    'default_output_dir': DEFAULT_OUTPUT_DIR,
    'default_config_folder': DEFAULT_CONFIG_FOLDER,
    'prompts_folder': PROMPTS_FOLDER,
    'log_level': LOG_LEVEL,
}

def resolve_path(path):
    """
    Resolves a given path to an absolute path. If the path is relative, it is made
    relative to the directory containing the main script.

    Args:
        path (str): The path to resolve.

    Returns:
        str: An absolute path.
    """
    if os.path.isabs(path):
        return path
    # Relative to the directory where the script is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(base_dir, path))

def load_config_from_folder(config_folder):
    """
    Dynamically load configuration settings from a folder.

    Args:
        config_folder (str): Path to the configuration folder.

    Returns:
        tuple: (config, whisper_config) dictionaries with updated values.
    """
    config = CONFIG.copy()
    whisper_config = WHISPER_CONFIG.copy()

    # Resolve relative or absolute paths
    resolved_config_folder = resolve_path(config_folder)
    config_path = os.path.join(resolved_config_folder, 'llm_config.txt')
    whisper_path = os.path.join(resolved_config_folder, 'whisper_config.txt')

    config['prompts_folder'] = os.path.join(resolved_config_folder, 'prompts')

    # Load and update CONFIG
    if os.path.exists(config_path):
        logger.info(f"Loading configuration from: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    value = value.strip()
                    if value:  # Only override if value is non-empty
                        config[key.strip()] = value
                    else:
                        logger.debug(f"Skipped overriding '{key.strip()}' due to empty value.")

    # Load and update WHISPER_CONFIG
    if os.path.exists(whisper_path):
        logger.info(f"Loading Whisper configuration from: {whisper_path}")
        with open(whisper_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    value = value.strip()
                    if value:  # Only override if value is non-empty
                        whisper_config[key.strip()] = value
                    else:
                        logger.debug(f"Skipped overriding '{key.strip()}' due to empty value.")

    return config, whisper_config