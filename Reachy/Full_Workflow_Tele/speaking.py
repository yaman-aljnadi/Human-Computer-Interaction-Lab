# speaking.py
from openai import OpenAI
import config
import os

class Voice:
    def __init__(self):
        print("Initializing OpenAI Voice...")
        if not config.OPENAI_API_KEY:
            print("ERROR: OpenAI API Key missing in config.py")
        
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        print("Voice Ready (OpenAI).")

    def synthesize(self, text, output_filename, emotion="neutral"):
        """
        Generates audio using OpenAI API.
        """
        
        if not text or len(text.strip()) == 0:
            print("[Voice] Warning: Received empty text to speak. Skipping.")
            return False
            
        # Select voice
        selected_voice = config.ROBOT_VOICE
        print(f"[Voice] Generating speech: '{text[:20]}...' using voice: {selected_voice}")

        try:
            response = self.client.audio.speech.create(
                model=config.TTS_MODEL,
                voice=selected_voice,
                input=text,
                # response_format="wav"  # <-- ADD THIS LINE to fix the format crash
            )
            
            response.stream_to_file(output_filename)
            return True
            
        except Exception as e:
            print(f"OpenAI TTS Error: {e}")
            return False