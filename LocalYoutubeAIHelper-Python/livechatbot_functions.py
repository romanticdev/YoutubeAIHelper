# livechatbot_functions.py

tools_functions = [
    {
        "name": "get_last_stream_context",
        "description": "Get a full context in text form from the last live stream on this channel",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "strict": True, 
        }
    },
    {
        "name": "get_last_5_streams_summaries",
        "description": "Get summaries from the last 5 streams on this channel",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "strict": True, 
        }
    },
    {
        "name": "get_latest_ai_news",
        "description": "Get top 5 AI news items from the last 24 hours",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "strict": True, 
        }
    },
    {
        "name": "get_latest_general_news",
        "description": "Get top 5 general news items from the last 24 hours",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "strict": True, 
        }
    },
    {
        "name": "get_stream_info",
        "description": "Provides global context about the stream host or the overall stream series.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_current_realtime_stream_content",
        "description": "Return the latest real-time transcribed content from the ongoing stream right now (it contains information about what the host is talking with 5s delay )",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "strict": True
        }
    }
]
