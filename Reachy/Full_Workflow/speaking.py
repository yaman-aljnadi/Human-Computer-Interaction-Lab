import wave
import torch
import config
from piper import PiperVoice

class Voice:
    def __init__(self):
        print(f"Loading Piper Voice: {config.PIPER_MODEL_PATH}...")
        try:
            self.voice = PiperVoice.load(config.PIPER_MODEL_PATH, use_cuda=torch.cuda.is_available())
        except Exception as e:
            print(f"Failed to load Piper: {e}")
            raise e
        print("Voice Ready.")

    def synthesize(self, text, output_filename):
        """Generates a WAV file from text."""
        try:
            with wave.open(output_filename, "wb") as wav_file:
                self.voice.synthesize_wav(text, wav_file)
            return True
        except Exception as e:
            print(f"TTS Error: {e}")
            return False