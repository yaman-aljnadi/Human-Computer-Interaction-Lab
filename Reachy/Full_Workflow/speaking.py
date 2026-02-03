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
        Selects voice based on the 'emotion' parameter.
        """
        # Select voice based on emotion map, default to 'alloy' if not found
        selected_voice = config.EMOTION_VOICE_MAP.get(emotion, "alloy")
        print(f"[Voice] Generating speech: '{text[:20]}...' using voice: {selected_voice}")

        try:
            response = self.client.audio.speech.create(
                model=config.TTS_MODEL,
                voice=selected_voice,
                input=text
            )
            
            # Save to file
            # OpenAI returns MP3 by default usually, but we can stream to file
            response.stream_to_file(output_filename)
            return True
            
        except Exception as e:
            print(f"OpenAI TTS Error: {e}")
            return False