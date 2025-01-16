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
        # e.g., 'chatbot_response.txt' in the same config folder
        system_prompt_path = os.path.join(self.config['config_folder'], 'chatbot_response.txt')
        self.system_message_template = load_file_content(system_prompt_path, 
            "You are a helpful assistant. Please keep messages under 200 chars."
        )

        # Load message filter prompt from file
        filter_prompt_path = os.path.join(self.config['config_folder'], 'message_filter.txt')
        self.message_filter_prompt = load_file_content(filter_prompt_path, 
            "If the user wants the bot's help, respond with OK. Otherwise respond: SKIP_MESSAGE.")

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

    def should_respond_to_message(self, user_text,  author_name=None, author_channel_id=None):
        """
        Determines whether the bot should respond to a message by evaluating
        the recent conversation history and the current user message.
        """
        # Define the number of recent messages to include for context
        context_length = 50
        recent_history = self.conversation_history[-context_length:]
        
        user_metadata = f"(User: {author_name}({author_channel_id})) " if author_name else ""

        # Construct the messages payload with recent history
        # TODO - get extended info about conversation history with this specific person
        # including chat bot replies 
        messages = [{"role": "system", "content": self.message_filter_prompt}]
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
        2. If respond, build a system+history+user prompt.
        3. Possibly call a function if the LLM requests it.
        4. Return the final text.
        """
        
        user_metadata = f"(User: {author_name}({author_channel_id})) " if author_name else ""

        if not self.should_respond_to_message(message,author_name, author_channel_id):
            return None  # We’ll interpret None as skip
        
        # Step 2: Add the user’s message to conversation
        self.conversation_history.append({
            "role": "user",
            "content": f"{user_metadata}{message}"
        }) 
        
        messages = [
            {
                "role": "system",
                "content": self.system_message
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
        
        # Add to conversation history
        self.conversation_history.append({"role": "assistant", "content": f"[You]{final_content}"})
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
                chat_messages, next_page_token = self.youtube_updater.fetch_live_chat_messages(live_chat_id, next_page_token)
                for msg in chat_messages:
                    message_time = msg["snippet"]["publishedAt"]
                    message_datetime = datetime.strptime(message_time, '%Y-%m-%dT%H:%M:%S.%f%z')
            
                    # Convert message_datetime to UNIX timestamp for comparison
                    message_timestamp = message_datetime.timestamp()
                    user_text = msg["snippet"]["textMessageDetails"]["messageText"]
                    author_channel_id = msg["authorDetails"]["channelId"]
                    author_name = msg["authorDetails"]["displayName"]

                    # Only respond to messages that appear after we joined
                    if message_timestamp > join_time:
                        # Check if user_text is from the bot
                        if author_channel_id == bot_id:
                            continue
                        
                        reply = self.handle_message(user_text,author_name=author_name, author_channel_id=author_channel_id) 
                        if reply:
                            reply = f"{reply}"
                            if len(reply) > 200:
                                logger.warning(f"Chatbot Reply too long: {reply}")
                                reply = reply[:197] + "..."
                            logger.info(f"Chatbot Replying to {author_name}({author_channel_id}): {reply}")
                            self.youtube_updater.post_live_chat_message(live_chat_id, f"{reply}")
                time.sleep(15)
            except Exception as e:
                logger.error(f"An error occurred in the chat bot loop: {e}", exc_info=True)

if __name__ == "__main__":
    bot = LiveChatBot()
    video_id = sys.argv[1] if len(sys.argv) > 1 else None
    bot.run_bot_loop(video_id)