# live_transcriber.py
import queue
import sounddevice as sd
import numpy as np
import whisper
import threading
import os
from utilities import get_active_transcript_file  
from datetime import datetime

CUTOFF_MINUTES = 60

# Load Whisper model
model = whisper.load_model("small")

SAMPLE_RATE = 16000
CHUNK_DURATION = 1.0  # seconds per callback chunk
BLOCKSIZE = int(SAMPLE_RATE * CHUNK_DURATION)
SILENCE_THRESHOLD = 0.0001  # Adjust based on your microphone/environment

def is_silent(audio_chunk):
    #print(f"Mean: {np.mean(np.abs(audio_chunk))}")
    return np.mean(np.abs(audio_chunk)) < SILENCE_THRESHOLD

audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    if status:
        print("Status:", status)
    # If stream is int16, convert to float32 in [-1, 1]
    data = indata[:, 0].astype(np.float32) / 32768.0
    audio_queue.put(data)

def transcribe_loop(transcript_path: str):
    """
    Continuously read from audio_queue, accumulate ~5s of audio, 
    call Whisper, then append transcript lines to TRANSCRIPTION_FILE.
    """
    buffer = np.array([], dtype=np.float32)
    use_prompt = True
    while True:
        chunk = audio_queue.get()  # Blocking call until we get audio data
        buffer = np.concatenate((buffer, chunk))

        # If buffer is at least 5s of audio, let's do a transcription
        if len(buffer) >= SAMPLE_RATE * 5:
            
            if not is_silent(buffer):
                result = model.transcribe(
                    buffer, 
                    fp16=False,
                    no_speech_threshold=0.5,
                    #logprob_threshold=-1.0,
                    language="en",
                    initial_prompt="I am doing a live stream on YouTube" if use_prompt else None
                )
                use_prompt = False
                text = result["text"].strip()
                if text:
                    with open(transcript_path, "a", encoding="utf-8") as f:
                        f.write(text + "\n")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}]: {text}")

            # Clear the buffer (or keep it if you want continuous context)
            buffer = np.array([], dtype=np.float32)

def main():
    transcript_path = get_active_transcript_file(
        dir_path="transcripts", 
        cutoff_minutes=CUTOFF_MINUTES
    )
    print(f"Using transcript file: {transcript_path}")
    stream = sd.InputStream(
        callback=audio_callback,
        channels=1,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCKSIZE,
        dtype='int16'
    )

    with stream:
        # Run transcribe_loop in a background thread so audio_callback isn't blocked
        t = threading.Thread(target=transcribe_loop, args=(transcript_path,), daemon=True)
        t.start()

        print("Real-time transcription running. Press Ctrl+C to stop.")
        while True:
            sd.sleep(1000)

if __name__ == "__main__":
    main()
