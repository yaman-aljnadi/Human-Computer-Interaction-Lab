# config.py
import torch
import os
from dotenv import load_dotenv

load_dotenv()
# Connection
REACHY_IP = '192.168.50.242'

# --- NEW: Experiment Condition ---
# Options: "embodied", "copilot", or "crowd"
EXPERIMENT_CONDITION = "crowd"

# Models
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
QWEN_MODEL_ID = "vikhyatk/moondream2"
# LLM_MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
OPENAI_LLM_MODEL = "gpt-4o"
WHISPER_MODEL_TYPE = "base.en"

# OPENAI TTS SETTINGS
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
TTS_MODEL = "gpt-4o-mini-tts"      

# OPENAI_REALTIME_MODEL = "gpt-realtime-mini-2025-12-15"
OPENAI_REALTIME_MODEL = "gpt-realtime-2025-08-28"

LISTEN_OVERLAP_TIME = 1.2
SPEECH_PAUSE_THRESHOLD = 2.5

# Map emotions to specific OpenAI Voices
# EMOTION_VOICE_MAP = {
#     "neutral": "alloy",
#     "happy": "shimmer",   # Bright & clear
#     "excited": "nova",    # Energetic
#     "sad": "onyx",        # Deep & serious
#     "angry": "onyx",      # Authoritative
#     "confused": "fable",  # Expressive
# }

ROBOT_VOICE = "alloy"

# Audio Files (Temp files)
TEMP_INPUT_AUDIO = "temp_command.wav"
TEMP_OUTPUT_AUDIO = "reachy_speech.wav" 
SYSTEM_AUDIO = "system_speech.mp3"

# Weird Stuff Delete later 
SONG_FILE = "End_of_Line_trimmed.mp3"