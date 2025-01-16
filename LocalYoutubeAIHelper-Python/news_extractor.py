import os
import json
import logging
from serpapi import GoogleSearch
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
from utilities import ensure_directory_exists

# worldnewsapi imports
import worldnewsapi
from worldnewsapi.rest import ApiException

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Adjust as needed

class NewsExtractor:
    """
    A helper class to:
      1) Search for news articles using SerpApi (Google News engine)
      2) Retrieve full text for each article from worldnewsapi
      3) Keep only one successful text per highlight/story,
         skipping others if one is already found.
    """

    def __init__(self, config):
        """
        Initialize NewsExtractor with config.

        Args:
            config (dict): Should contain:
                - 'news_api_key' (SerpApi key)
                - 'worldnews_api_key' (WorldNewsAPI key)
        """
        # SerpApi key
        self.serp_api_key = config.get('news_api_key', '')
        if not self.serp_api_key:
            raise ValueError("No 'news_api_key' (SerpApi key) found in config.")
        logger.info("Initialized SerpApi key successfully.")

        # worldnewsapi key
        self.worldnews_api_key = config.get('worldnews_api_key', '')
        if not self.worldnews_api_key:
            raise ValueError("No 'worldnews_api_key' (WorldNewsAPI) found in config.")
        logger.info("Initialized WorldNewsAPI key successfully.")

        # Prepare time range for SerpApi searches (past 24 hours)
        now = datetime.utcnow()
        self.now_str = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.past_24_hours_str = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        logger.info(f"Configured SerpApi search time range: {self.past_24_hours_str} to {self.now_str}")

        # Setup worldnewsapi configuration
        self.worldnews_config = worldnewsapi.Configuration(host="https://api.worldnewsapi.com")
        self.worldnews_config.api_key['apiKey'] = self.worldnews_api_key
        self.worldnews_config.api_key['headerApiKey'] = self.worldnews_api_key
        logger.debug("worldnewsapi configuration set up successfully.")

    def fetch_news(self, query="", num_results=5, topic_token=None):
        """
        Fetches news from SerpApi’s Google News (headlines + article links).

        Args:
            query (str): The search query (e.g., 'Artificial Intelligence').
            num_results (int): Number of results to return.
            topic_token (str): Optional token for a specific Google News topic (e.g., topStories).

        Returns:
            list: Raw results from SerpApi (list of dicts).
        """
        logger.info(f"Initiating SerpApi request with query='{query}', "
                    f"num_results={num_results}, topic_token={topic_token}")

        params = {
            'api_key': self.serp_api_key,
            'engine': 'google_news',
            'q': query,
            'tbs': f'cdr:1,cd_min:{self.past_24_hours_str},cd_max:{self.now_str}',
            'num': num_results,
            'tbm': 'nws'
        }
        if topic_token:
            params['topic_token'] = topic_token

        search = GoogleSearch(params)
        results = search.get_dict()
        raw_items = results.get('news_results', [])

        logger.info(f"SerpApi returned {len(raw_items)} item(s). "
                    f"Returning up to {num_results} of them.")

        return raw_items[:num_results]

    def parse_news_response(self, raw_results):
        """
        Converts SerpApi's news results into a list of articles, each with:
          - title
          - link
          - date
          - source
          - text (retrieved from worldnewsapi)

        If a highlight has text, we keep that and skip all stories.
        Otherwise we parse stories, keeping only the first that returns text.

        For a simpler top-level item, we parse it once, skipping if empty.

        Args:
            raw_results (list): List of dicts from SerpApi.

        Returns:
            list: A list of fully enriched article dicts.
        """
        logger.info(f"Parsing raw SerpApi results: {len(raw_results)} top-level item(s).")
        valid_articles = []

        def parse_article(data):
            """Normalize a single SerpApi article dict into a simpler dict."""
            return {
                'title': data.get('title', 'No Title'),
                'link': data.get('link', ''),
                'date': data.get('date', ''),
                'source': data.get('source', {}).get('name', ''),
            }

        for idx, item in enumerate(raw_results, start=1):
            logger.debug(f"Processing item {idx}/{len(raw_results)} from SerpApi result.")

            # CASE 1: The item has 'highlight' + optional 'stories'
            if 'highlight' in item:
                logger.debug("Item has 'highlight' structure. Attempting to parse highlight first.")
                # First, parse the highlight
                highlight_article = parse_article(item['highlight'])
                highlight_text = self._try_extract_full_text(highlight_article['link'])

                if highlight_text:
                    # If we successfully extracted text from highlight, add it and skip stories
                    highlight_article['text'] = highlight_text
                    valid_articles.append(highlight_article)
                    logger.debug("Highlight article accepted; skipping stories.")
                else:
                    # If highlight text is empty, parse stories, but stop at the first success
                    stories = item.get('stories', [])
                    logger.debug(f"Highlight empty, checking {len(stories)} stories for the first success.")
                    found_story = False
                    for s_idx, story in enumerate(stories, start=1):
                        story_article = parse_article(story)
                        story_text = self._try_extract_full_text(story_article['link'])
                        if story_text:
                            # Found the first valid story, add it, skip the rest
                            story_article['text'] = story_text
                            valid_articles.append(story_article)
                            found_story = True
                            logger.debug(f"Story {s_idx} accepted with non-empty text, skipping further stories.")
                            break
                    if not found_story:
                        logger.debug("No story found with non-empty text, skipping entire item.")
            
            # CASE 2: The item is a simpler top-level article
            else:
                logger.debug("Item has a simpler top-level structure. Parsing directly.")
                article = parse_article(item)
                article_text = self._try_extract_full_text(article['link'])
                if article_text:
                    article['text'] = article_text
                    valid_articles.append(article)
                    logger.debug("Article accepted with non-empty text.")
                else:
                    logger.debug("Article skipped due to empty or failed text extraction.")

        logger.info(f"Parsing complete. Kept {len(valid_articles)} article(s) total.")
        return valid_articles
    
    def _save_news_to_file(self, news_items: List[Dict[str, Any]], out_path: str):
        """
        Saves a list of news articles to a local JSON file.
        The structure is: { "date": "YYYY-MM-DD", "items": [...] }
        """
        ensure_directory_exists(os.path.dirname(out_path))
        data = {
            "date": date.today().isoformat(),
            "items": news_items
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _load_news_from_file(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Reads a local JSON file with structure { "date": "...", "items": [...] } 
        and returns the 'items' list. If file not found or invalid, return [].
        """
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("items", [])
                return items
        except Exception:
            return []
    
    def get_general_news(self, num_results=5, topic_token=None):
        """
        Convenience method to fetch 'general' or 'top stories' news from SerpApi
        and retrieve full text from worldnewsapi.

        Args:
            num_results (int): Number of results.
            topic_token (str): (Optional) SerpApi topStories token.

        Returns:
            list: List of articles (dict), each with text, skipping empties.
        """
        
        today_str = date.today().isoformat()
        filename = f"news_general_{today_str}.json"
        filepath = os.path.join("news", filename)
        if not os.path.exists(filepath):
            # Fetch from external sources
            print("[DEBUG] No local general news file found. Fetching fresh data from APIs...")
            # For example, we might fetch 5 or 10 news items
            raw = self.fetch_news("", num_results, topic_token=topic_token)
            articles = self.parse_news_response(raw)
            # articles is a list of dict, each with title, link, date, text, etc.
            self._save_news_to_file(articles, filepath)
        else:
            print("[DEBUG] Found local general news file. Reading from disk...")
        
            # Now read the file
        articles = self._load_news_from_file(filepath)
        if not articles:
            return "No general news found (empty file)."
            
        # logger.info("Fetching general news ...")
        # raw = self.fetch_news("", num_results, topic_token=topic_token)
        # articles = self.parse_news_response(raw)
        # logger.info(f"Fetched {len(articles)} 'general' news article(s) with non-empty text.")
        # return articles
        lines = []
        for i, art in enumerate(articles, 1):
            lines.append(
                f"{i}. {art.get('title','No Title')} "
                f"({art.get('source','Unknown')})\n"
                f"   Date: {art.get('date','N/A')}\n"
                f"   Link: {art.get('link','')}\n"
                f"   Text excerpt: {art.get('text','')}...\n"
            )
        return "\n".join(lines)

    def get_ai_news(self, num_results=5):
        """
        Convenience method to fetch 'AI' news from SerpApi and retrieve full text.

        Args:
            num_results (int): Number of results.

        Returns:
            list: List of articles (dict), each with text, skipping empties.
        """
        today_str = date.today().isoformat()
        filename = f"news_ai_{today_str}.json"
        filepath = os.path.join("news", filename)

        if not os.path.exists(filepath):
            print("[DEBUG] No local AI news file found. Fetching fresh data from APIs...")
            raw = self.fetch_news("AI", num_results)
            articles = self.parse_news_response(raw)
            self._save_news_to_file(articles, filepath)
        else:
            print("[DEBUG] Found local AI news file. Reading from disk...")
        
        articles = self._load_news_from_file(filepath)
        if not articles:
            return "No AI news found (empty file)."

        lines = []
        for i, art in enumerate(articles, 1):
            lines.append(
                f"{i}. {art.get('title','No Title')} "
                f"({art.get('source','Unknown')})\n"
                f"   Date: {art.get('date','N/A')}\n"
                f"   Link: {art.get('link','')}\n"
                f"   Text excerpt: {art.get('text','')[0:150]}...\n"
            )
        return "\n".join(lines)
        # logger.info("Fetching AI news ...")
        # raw = self.fetch_news("AI", num_results)
        # articles = self.parse_news_response(raw)
        # logger.info(f"Fetched {len(articles)} 'AI' news article(s) with non-empty text.")
        # return articles

    def _try_extract_full_text(self, url):
        """
        Attempts to retrieve the full text of an article from worldnewsapi.
        Returns the text if successful, otherwise empty string.

        Args:
            url (str): The article URL.

        Returns:
            str: The extracted text if found, or '' if not.
        """
        if not url:
            logger.debug("No valid URL provided, returning empty text.")
            return ''

        logger.debug(f"Attempting to extract text from URL: {url}")
        try:
            with worldnewsapi.ApiClient(self.worldnews_config) as api_client:
                api_instance = worldnewsapi.NewsApi(api_client)
                analyze = True  # We want the text
                response = api_instance.extract_news(url, analyze)
                response_dict = response.to_dict()
                article_text = response_dict.get('text', '').strip()

                if article_text:
                    logger.debug(f"Successfully extracted {len(article_text)} characters of text from {url}")
                else:
                    logger.debug(f"No text returned from worldnewsapi for {url}")
                return article_text
        except ApiException as e:               
            logger.error(f"worldnewsapi ApiException extracting text from {url}: {e}")
            if e.reason=="Payment Required":
                return '...' # This is a special case for the free tier
            return ''
        except Exception as ex:
            logger.error(f"Unexpected error using worldnewsapi on {url}: {ex}")
            return ''
