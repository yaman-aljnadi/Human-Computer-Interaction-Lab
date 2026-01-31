import speech_recognition as sr
import whisper
import os
import config

class Ears:
    def __init__(self):
        print(f"Loading Whisper Model ({config.WHISPER_MODEL_TYPE})...")
        self.model = whisper.load_model(config.WHISPER_MODEL_TYPE)
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        print("Ears Ready.")

    def listen(self, timeout=5, phrase_time_limit=10):
        """Captures audio from mic and saves to temp file."""
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            print("Listening...")
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                with open(config.TEMP_INPUT_AUDIO, "wb") as f:
                    f.write(audio.get_wav_data())
                return True
            except sr.WaitTimeoutError:
                return False
            except Exception as e:
                print(f"Mic Error: {e}")
                return False

    def transcribe(self):
        """Transcribes the temp audio file using Whisper."""
        if os.path.exists(config.TEMP_INPUT_AUDIO):
            result = self.model.transcribe(config.TEMP_INPUT_AUDIO)
            return result["text"].lower().strip()
        return ""