# config.py
import torch
import os

# Connection
REACHY_IP = '192.168.50.241'

# Models
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
QWEN_MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
LLM_MODEL_ID = "Qwen/Qwen1.5-1.8B-Chat"
WHISPER_MODEL_TYPE = "base.en"

# --- OPENAI TTS SETTINGS ---
OPENAI_API_KEY = "#" # <--- PASTE YOUR KEY HERE
TTS_MODEL = "tts-1"       

# Map emotions to specific OpenAI Voices
EMOTION_VOICE_MAP = {
    "neutral": "alloy",
    "happy": "shimmer",   # Bright & clear
    "excited": "nova",    # Energetic
    "sad": "onyx",        # Deep & serious
    "angry": "onyx",      # Authoritative
    "confused": "fable",  # Expressive
}

# Audio Files (Temp files)
TEMP_INPUT_AUDIO = "temp_command.wav"
TEMP_OUTPUT_AUDIO = "reachy_speech.wav" 
SYSTEM_AUDIO = "system_speech.wav"

# Weird Stuff Delete later 
SONG_FILE = "End_of_Line_trimmed.mp3"