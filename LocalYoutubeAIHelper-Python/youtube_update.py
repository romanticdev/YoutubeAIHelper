import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from utilities import load_file_content, setup_logging, load_variable_content, limit_tags_to_500_chars
from config import CONFIG

logger = setup_logging()

class YouTubeUpdater:
    def __init__(self, config):
        """
        Initializes the YouTubeUpdater with configuration settings.

        Args:
            config (dict): General configuration settings.
        """
        self.token_file = config['token_file']
        self.client_secret_file = config['client_secret_file']
        self.scopes = config['scopes']
        self.service = self.authenticate_youtube()

    def authenticate_youtube(self):
        """
        Authenticates to the YouTube API using OAuth2.

        Returns:
            googleapiclient.discovery.Resource: YouTube API service instance.
        """
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, self.scopes)
                creds = flow.run_local_server(port=0)

            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())

        return build('youtube', 'v3', credentials=creds)

    def get_video_details(self, video_id):
        """
        Retrieves details of a YouTube video by ID.

        Args:
            video_id (str): YouTube video ID.

        Returns:
            dict: Video details.
        """
        try:
            request = self.service.videos().list(
                part='snippet,contentDetails,statistics,status',
                id=video_id
            )
            response = request.execute()
            if response['items']:
                return response['items'][0]
            logger.error(f"No details found for video ID: {video_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving video details: {e}")
            return None

    def update_video(self, video_id, title=None, description=None, tags=None, category_id=None):
        """
        Updates a YouTube video's metadata.

        Args:
            video_id (str): YouTube video ID.
            title (str): New video title (optional).
            description (str): New video description (optional).
            tags (list): List of new tags (optional).
            category_id (str): New video category ID (optional).
        """
        try:
            # Fetch current details if necessary
            video_details = self.get_video_details(video_id)
            if not video_details:
                logger.error(f"Video ID '{video_id}' not found.")
                return

            snippet = video_details['snippet']
            if title:
                snippet['title'] = title
            if description:
                snippet['description'] = description
            if tags:
                snippet['tags'] = tags
            if category_id:
                snippet['categoryId'] = category_id

            request = self.service.videos().update(
                part='snippet',
                body={'id': video_id, 'snippet': snippet}
            )
            response = request.execute()
            logger.info(f"Updated video '{title or snippet['title']}' (ID: {video_id})")
        except Exception as e:
            logger.error(f"Error updating video: {e}")

    def process_update_youtube(self, folder):
        """
        Processes YouTube updates based on folder contents.

        Args:
            folder (str): Folder containing metadata files.
        """
        file_details_path = os.path.join(folder, 'file_details.txt')
        if not os.path.exists(file_details_path):
            logger.error(f"file_details.txt not found in folder: {folder}")
            return

        # Read YouTube ID from file_details.txt
        youtube_id = self.get_youtube_id_from_file(file_details_path)
        if not youtube_id:
            logger.error("YouTube ID not found in file_details.txt.")
            return

        # Load metadata
        title = load_variable_content('title',folder)
        description = load_variable_content('description',folder)
        tags = load_variable_content('keywords',folder) 
        if tags:
            tags = limit_tags_to_500_chars(tags)
            
        # Update video metadata
        self.update_video(
            video_id=youtube_id,
            title=title if title else None,
            description=description if description else None,
            tags=tags if tags else None,
            category_id=None  # Optionally, include category logic
        )

    @staticmethod
    def get_youtube_id_from_file(file_path):
        """
        Extracts the YouTube ID from file_details.txt.

        Args:
            file_path (str): Path to file_details.txt.

        Returns:
            str: YouTube ID, or None if not found.
        """
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if line.startswith('youtube_id='):
                        return line.split('=')[1].strip()
            return None
        except Exception as e:
            logger.error(f"Error reading YouTube ID from file: {e}")
            return None
