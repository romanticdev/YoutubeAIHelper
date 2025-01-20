import time
from datetime import datetime
import json
import os
import sys

from youtube_update import YouTubeUpdater
from discussion_starters import DiscussionStarters
from prompt_processor import PromptProcessor
from config import CONFIG, WHISPER_CONFIG, load_config_from_folder
from ai_client import AIClient
from utilities import load_file_content, setup_logging

from livechatbot_functions import tools_functions
from tools import (
    get_last_stream_context,
    get_last_5_streams_summaries,
    get_latest_ai_news,
    get_latest_general_news,
    get_stream_info,
    get_current_realtime_stream_content
)

logger = setup_logging()

def _fetch_recent_transcript_chars(max_chars=1000):
    """
    Retrieves the current real-time transcription text (via get_current_realtime_stream_content)
    and returns up to the last `max_chars`.
    """
    full_text = get_current_realtime_stream_content()  # from tools.py
    return full_text[-max_chars:] if len(full_text) > max_chars else full_text

def split_into_chunks(text, max_per_chunk=200, max_chunks=5, max_total=1000):
    """
    Splits 'text' into chunks of up to 'max_per_chunk' characters,
    capping the total output at 'max_total' characters or 'max_chunks' chunks.

    Returns a list of chunk strings.
    """
    # 1) Limit the text to max_total overall
    text = text[:max_total]

    # 2) Chunk it in increments of max_per_chunk
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_per_chunk
        chunks.append(text[start:end])
        start = end
        # If we already have max_chunks, append '...' if there's leftover, then break
        if len(chunks) == max_chunks and start < len(text):
            chunks[-1] = chunks[-1] + "..."
            break

    return chunks

class LiveChatBot:
    def __init__(self, configName="configurations/aibot"):
        self.config, self.whisper_config = load_config_from_folder(configName)
        self.youtube_updater = YouTubeUpdater(self.config)
        self.prompt_processor = PromptProcessor(self.config)
        self.discussion_starters = DiscussionStarters(self.config, self.whisper_config)
        self.client = AIClient(self.config, self.whisper_config)
        
        # We’ll store conversation history so we can keep track over time
        self.conversation_history = []
        
        # Load system prompt from file
																
        system_prompt_path = os.path.join(self.config['config_folder'], 'chatbot_response.txt')
        self.system_message_template = load_file_content(
            system_prompt_path, 
            "You are a helpful assistant. Please keep messages under 200 chars."
        )

        # Load message filter prompt from file
        filter_prompt_path = os.path.join(self.config['config_folder'], 'message_filter.txt')
        self.message_filter_prompt = load_file_content(
            filter_prompt_path, 
            "If the user wants the bot's help, respond with OK. Otherwise respond: SKIP_MESSAGE."
        )

        # Convert function definitions into a bullet list for {{AVAILABLE_FUNCTIONS}}
        self.available_functions = tools_functions
        function_names = [f"- {fn['name']}" for fn in self.available_functions]
        joined_functions = "\n".join(function_names)

        # We'll store the final system message (with placeholders replaced)
        self.system_message = self.system_message_template.replace(
            "{{AVAILABLE_FUNCTIONS}}", joined_functions
        )
        
        # Initialize bot's author channel ID
        self.bot_author_channel_id = None

    def _call_tool(self, function_name, args):
        """
        Dispatch table for calling the actual tool functions in Python
        after the LLM requests them.
        """
        if function_name == "get_last_stream_context":
            return get_last_stream_context()
        elif function_name == "get_last_5_streams_summaries":
            return get_last_5_streams_summaries()
        elif function_name == "get_latest_ai_news":
            return get_latest_ai_news()
        elif function_name == "get_latest_general_news":
            return get_latest_general_news()
        elif function_name == "get_stream_info":
            return get_stream_info()
        elif function_name == "get_current_realtime_stream_content":
            return get_current_realtime_stream_content()
        else:
            return f"Unknown function: {function_name}"

    def connect_to_live_stream(self, video_id=None):
        active_stream = self.youtube_updater.find_active_live_stream(video_id=video_id)
        if active_stream:
            self.youtube_updater.post_live_chat_message(active_stream, "Hi everyone! Chatbot is active!")
            return active_stream
        return None
    
    def censor_text(self, text):
        # Call OpenAI's Moderation API
        response = self.client.client.moderations.create(
            input=text,
            model="text-moderation-latest"
        )
        
        # Categories object from the API response
        categories = response.results[0].categories
        
        # List of categories considered as profane
        profane_categories = [
        'hate', 'hate/threatening', 'self-harm', 'sexual', 'sexual/minors',
        'violence', 'violence/graphic', 'harassment', 'harassment/threatening',
        'self-harm/intent', 'self-harm/instructions', 'self-harm/graphic',
        'sexual/explicit', 'sexual/erotica', 'violence/intent', 'violence/instructions'
        ]
        
        # Check if any profane category is flagged
        flagged_categories = [
            category for category in profane_categories 
            if getattr(categories, category, False)
        ]
        if len(flagged_categories)>0:
            # Split text into wordss
            words = text.split()
            censored_words = []
            print(f"text moderation result {", ".join(flagged_categories)}")
            return 'Beep'
        else:
            # If no profane content is detected, return the original text
            return text
    
    def is_message_for_streamer(self, user_text, author_name=None, author_channel_id=None):
        # Define the number of recent messages to include for context
        context_length = 10
        recent_history = self.conversation_history[-context_length:]
        
        user_metadata = f"(User: {author_name}({author_channel_id})) " if author_name else ""

        # Grab the last ~1000 chars of the real-time transcript
        recent_transcript = _fetch_recent_transcript_chars(1000)

        messages = [
            {"role": "system", "content": "Determine if the following message is addressed to the streamer. Respond with 'yes' or 'no'."},
            {
                "role": "system",
                "content": f"Here is the last ~1000 characters of the live stream:\n{recent_transcript}"
            }
        ]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": f"{user_metadata}{user_text}"})

      
        response = self.client.create_chat_completion(messages=messages)
        # Evaluate the response to decide whether to respond
        content = response.choices[0].message.content.strip()
        logger.info(f"Message is for streamer response for comment from {user_metadata}: {content}")
        return content == 'yes'

    def should_respond_to_message(self, user_text, author_name=None, author_channel_id=None):
        """
        Determines whether the bot should respond to a message by evaluating
        the recent conversation history AND the last ~1000 characters from the 
        real-time transcript.
        """
        # Define the number of recent messages to include for context
        context_length = 50
        recent_history = self.conversation_history[-context_length:]
        
        user_metadata = f"(User: {author_name}({author_channel_id})) " if author_name else ""

        # Grab the last ~1000 chars of the real-time transcript
        recent_transcript = _fetch_recent_transcript_chars(1000)

        # Construct the messages payload with:
        #   - The filter prompt
        #   - The last ~1000 chars of real-time transcription (as system context)
        #   - The recent conversation history
        #   - The new user message
        messages = [
            {"role": "system", "content": self.message_filter_prompt},
            {
                "role": "system",
                "content": f"Here is the last ~1000 characters of the live stream:\n{recent_transcript}"
            }
        ]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": f"{user_metadata}{user_text}"})

        # Get the model's response
        response = self.client.create_chat_completion(messages=messages)

        # Evaluate the response to decide whether to respond
        content = response.choices[0].message.content.strip()
        logger.info(f"Message filter response for comment from {user_metadata}: {content}")
        return "SKIP_MESSAGE" not in content.upper()

	
    def handle_message(self, message, author_name=None, author_channel_id=None):
        """
        1. Decide if we skip or respond using should_respond_to_message().
        2. If respond, build a system + real-time context + history + user prompt.
        3. Possibly call a function if the LLM requests it.
        4. Return the final text.
        """

        user_metadata = f"(User: {author_name}({author_channel_id})) " if author_name else ""

        if not self.should_respond_to_message(message, author_name, author_channel_id):
            return None  # We’ll interpret None as skip
        
        # Step 2: Add the user’s message to conversation
        self.conversation_history.append({
            "role": "user",
            "content": f"{user_metadata}{message}"
        })

        # Include the last ~1000 chars of real-time transcript in the system context 
        recent_transcript = _fetch_recent_transcript_chars(1000)

        messages = [
            {
                "role": "system",
                "content": self.system_message
            },
            {
                "role": "system",
                "content": f"Here is the last ~1000 characters of the live stream:\n{recent_transcript}"
            }
        ] + self.conversation_history
		

        # Step 3: Create the chat completion
        response = self.client.create_chat_completion(
            messages=messages,
            functions=self.available_functions,
            function_call="auto"
        )
        
        finish_reason = response.choices[0].finish_reason
        
        if finish_reason == "function_call":
            fn_call = response.choices[0].message.function_call
            function_name = fn_call.name
            arguments = fn_call.arguments

            logger.info(f"Using function call: {function_name} with arguments: {arguments}")
            
            try:
                args_dict = json.loads(arguments) if arguments else {}
            except:
                args_dict = {}

            # Call the actual Python function
            tool_result = self._call_tool(function_name, args_dict)

            # Now we send the tool result back to the LLM for a final user-facing answer
            follow_up_messages = [
                {
                    "role": "system",
                    "content": "You called the function below. Summarize the result in a helpful answer."
                },
                {
                    "role": "function",
                    "name": function_name,
                    "content": tool_result
                }
            ]
            final_response = self.client.create_chat_completion(
                messages=messages + [response.choices[0].message] + follow_up_messages
            )
            final_content = final_response.choices[0].message.content
        else:
            final_content = response.choices[0].message.content
        
        # Add to conversation history WITHOUT "[You]" to avoid that in subsequent context
        self.conversation_history.append({"role": "assistant", "content": final_content})

        return final_content

    def run_bot_loop(self, video_id=None):
        stream_details = self.connect_to_live_stream(video_id)
        if not stream_details:
            logger.warning("No active stream.")
            return
        live_chat_id = stream_details
        join_time = time.time()
        next_page_token = None
        bot_id = self.youtube_updater.channel_id
        logger.info(f"Bot ID: {bot_id}")
        
        while True:
            try:
                chat_messages, next_page_token = self.youtube_updater.fetch_live_chat_messages(
                    live_chat_id, 
                    next_page_token
                )
                for msg in chat_messages:
                    message_time = msg["snippet"]["publishedAt"]
                    message_datetime = datetime.strptime(message_time, '%Y-%m-%dT%H:%M:%S.%f%z')
            
                    # Convert message_datetime to UNIX timestamp for comparison
                    message_timestamp = message_datetime.timestamp()
                    user_text = msg["snippet"]["textMessageDetails"]["messageText"]
                    author_channel_id = msg["authorDetails"]["channelId"]
                    author_name = msg["authorDetails"]["displayName"]

                    # Only respond to messages that appear AFTER we joined
                    if message_timestamp > join_time:
                        # Check if user_text is from the bot
                        if author_channel_id == bot_id:
                            continue
                        
                        reply = self.handle_message(
                            user_text,
                            author_name=author_name,
                            author_channel_id=author_channel_id
                        )
                        if reply:
                            # Now split the final reply into multiple messages if needed
                            chunks = split_into_chunks(reply, max_per_chunk=200, max_chunks=5, max_total=1000)
                            for idx, chunk in enumerate(chunks):
                                logger.info(f"Chatbot sending chunk {idx+1}/{len(chunks)} to {author_name}({author_channel_id}): {chunk}")
                                self.youtube_updater.post_live_chat_message(live_chat_id, chunk)
                            
                time.sleep(15)
            except Exception as e:
                logger.error(f"An error occurred in the chat bot loop: {e}", exc_info=True)

if __name__ == "__main__":
    bot = LiveChatBot()
    video_id = sys.argv[1] if len(sys.argv) > 1 else None
    bot.run_bot_loop(video_id)
