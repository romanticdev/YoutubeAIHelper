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
USE_AZURE_OPENAI = os.getenv('USE_AZURE_OPENAI', 'false').lower() == 'true'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY', '')
AZURE_DEPLOYMENT_NAME = os.getenv('AZURE_DEPLOYMENT_NAME', '')
AZURE_API_VERSION = os.getenv('AZURE_API_VERSION', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

logger.info(f"We are using {'Azure' if USE_AZURE_OPENAI else 'OpenAI SDK'}")
if USE_AZURE_OPENAI:
    logger.info(f"Azure OpenAI API Key Loaded: {'Yes' if AZURE_OPENAI_API_KEY else 'No'}")
    logger.info(f"Azure OpenAI Endpoint: {AZURE_OPENAI_ENDPOINT}")
    logger.info(f"Azure Deployment Name: {AZURE_DEPLOYMENT_NAME}")
else:    
    logger.info(f"OpenAI API Key Loaded: {'Yes' if OPENAI_API_KEY else 'No'}")

DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'gpt-4o')
MAX_TOKENS = int(os.getenv('MAX_TOKENS', 16000))
TEMPERATURE = float(os.getenv('TEMPERATURE', 0.7))
TOP_P = float(os.getenv('TOP_P', 1.0))

# Audio settings
AUDIO_BITRATE = os.getenv('AUDIO_BITRATE', '12k')  # Default to 12 kbps

# Paths
DEFAULT_OUTPUT_DIR = os.getenv('DEFAULT_OUTPUT_DIR', 'videos')
DEFAULT_CONFIG_FOLDER = os.getenv('DEFAULT_CONFIG_FOLDER', 'configurations/generic')
PROMPTS_FOLDER = os.path.join(DEFAULT_CONFIG_FOLDER, 'prompts')
WHISPER_DEPLOYMENT = os.getenv('WHISPER_DEPLOYMENT','')

# Whisper-specific configuration
WHISPER_CONFIG = {
    'temperature': float(os.getenv('WHISPER_TEMPERATURE', '0.7')),
    'response_format': os.getenv('WHISPER_RESPONSE_FORMAT', 'verbose_json'),
    'language': os.getenv('WHISPER_LANGUAGE', 'en'),
    'deployment_name': WHISPER_DEPLOYMENT
}

# General settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Combined configuration for convenience
CONFIG = {
    'scopes': SCOPES,
    'token_file': TOKEN_FILE,
    'client_secret_file': CLIENT_SECRET_FILE,
    'use_azure_openai': USE_AZURE_OPENAI,
    'openai_api_key': OPENAI_API_KEY,
    'azure_openai_endpoint': AZURE_OPENAI_ENDPOINT,
    'azure_openai_api_key': AZURE_OPENAI_API_KEY,
    'azure_deployment_name': AZURE_DEPLOYMENT_NAME,
    'azure_openai_api_version' : AZURE_API_VERSION,
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
    
     # Check for improve_srt_content: either text or file path
    prompt_content = whisper_config.get('improve_srt_content', '')
    prompt_file_path = os.path.join(resolved_config_folder, prompt_content)

    
    if not prompt_content:
        logger.debug("No 'improve_srt_content' found in whisper_config.txt.")
    elif os.path.isfile(prompt_file_path):
        # If it's a file path, read the content from the file
        logger.info(f"Loading 'improve_srt_content' from file: {prompt_content}")
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read().strip()
            whisper_config['improve_srt_content'] = prompt_content
        except Exception as e:
            logger.error(f"Failed to load prompt content from file '{prompt_content}': {e}")
    else:
        # If it's a text prompt, just use it directly
        whisper_config['improve_srt_content'] = prompt_content
        logger.info("Using 'improve_srt_content' as a direct text prompt.")
        
    return config, whisper_config