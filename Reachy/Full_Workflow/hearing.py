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
        
        # KEY ADJUSTMENT 1: Patience
        # How long (in seconds) of silence to wait before considering the sentence "done".
        # Default is 0.8. Increasing this lets you pause to think without being cut off.
        self.recognizer.pause_threshold = 1.5 
        
        # Optional: dynamic energy adjustment helps if the room is noisy !doesn't really help but it's somethign (: 
        self.recognizer.dynamic_energy_threshold = True 
        
        print("Ears Ready.")

    def listen(self):
        """
        Captures audio.
        Blocks (waits) indefinitely until user speaks.
        Stops listening only when user stops speaking.
        """
        with self.microphone as source:
            # Adjust for ambient noise once at the start is usually enough,
            # but doing it every time is safer if environment changes.
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("Listening... (Waiting for speech)")
            
            try:
                # timeout=None: Wait forever for sound to start.
                # phrase_time_limit=None: Listen until silence (no hard time limit).
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=None)
                
                with open(config.TEMP_INPUT_AUDIO, "wb") as f:
                    f.write(audio.get_wav_data())
                return True
            
            except Exception as e:
                # This catches errors, but usually timeout errors won't happen now.
                print(f"Mic Error: {e}")
                return False

    def transcribe(self):
        """Transcribes the temp audio file using Whisper."""
        if os.path.exists(config.TEMP_INPUT_AUDIO):
            result = self.model.transcribe(config.TEMP_INPUT_AUDIO)
            return result["text"].lower().strip()
        return ""