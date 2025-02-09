import os
import subprocess
import sys

from youtube_update import YouTubeUpdater
from config import load_config_from_folder, CONFIG, WHISPER_CONFIG

def find_active_stream_id():
    """
    Attempts to find an active (live) stream on your channel. If none is active,
    returns the most recently completed live stream ID. If still not found, returns None.
    """
    updater = YouTubeUpdater(CONFIG)

    # -----------------------------------------------------
    # 1) Try to find an active broadcast via YouTube Search
    # -----------------------------------------------------
    #   search -> type=video, eventType=live, order=date => if any item, take its videoId
    try:
        search_response = (
            updater.service.search()
            .list(
                part="id",
                channelId=updater.channel_id,
                type="video",
                eventType="live",
                order="date",
                maxResults=1
            )
            .execute()
        )
        items = search_response.get("items", [])
        if items:
            active_video_id = items[0]["id"]["videoId"]
            print(f"[INFO] Found active live stream ID: {active_video_id}")
            return active_video_id
    except Exception as e:
        print("[WARN] Could not find active live stream:", e)

    # If all fails, return None
    print("[ERROR] No active or completed streams found. Returning None.")
    return None

def main():
    # Check if the caller passed the --full-process flag
    full_process_flag = ""
    if "--full-process" in sys.argv:
        full_process_flag = "--full-process"

    # 1) Attempt to discover the active live stream ID
    video_id = find_active_stream_id()
    if not video_id:
        print("No active stream found. Aborting.")
        return
    
    # 2) Build the path to your activate script (.venv\Scripts\activate.bat)
    venv_activate = os.path.abspath(os.path.join(".venv", "Scripts", "activate.bat"))
    if not os.path.isfile(venv_activate):
        print(f"[ERROR] Cannot find venv activate script at: {venv_activate}")
        return
    
    # 3) Launch livechatbot.py in a new cmd window with the environment activated.
    #    We pass the --full-process flag (if specified) and the video ID.
    cmd_livechatbot = (
        f'start cmd /k "call \"{venv_activate}\" && python livechatbot.py {full_process_flag} {video_id}"'
    )
    subprocess.Popen(cmd_livechatbot, shell=True)
    print(f"[LAUNCH] Live Chat Bot started with stream ID: {video_id}")

    # 4) Launch live_transcriber.py in another new cmd window (again with the venv activated)
    cmd_transcriber = (
        f'start cmd /k "call \"{venv_activate}\" && python live_transcriber.py"'
    )
    subprocess.Popen(cmd_transcriber, shell=True)
    print("[LAUNCH] Live Transcriber started in a separate window.")

if __name__ == "__main__":
    main()
