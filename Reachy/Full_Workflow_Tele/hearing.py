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
        
        # Patience settings
        self.recognizer.pause_threshold = config.SPEECH_PAUSE_THRESHOLD
        self.recognizer.dynamic_energy_threshold = False # Set to False to prevent auto-adjusting to robot's own voice
        
        # CALIBRATION (Run Once)
        print("Calibrating background noise... (Please be quiet)")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            # slightly boost the threshold so it ignores quiet breathing/humming
            # self.recognizer.energy_threshold *= 1.1 --- IGNORE --- 
            
        print(f"Ears Ready. Threshold: {self.recognizer.energy_threshold}")

    def listen(self):
        """
        Captures audio.
        """
        with self.microphone as source:
            # REMOVED: self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            # Removing this eliminates the 0.5s delay every turn.
            
            print("Listening...")
            try:
                # Use the pre-calibrated threshold
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=None)
                
                with open(config.TEMP_INPUT_AUDIO, "wb") as f:
                    f.write(audio.get_wav_data())
                return True
            
            except Exception as e:
                print(f"Mic Error: {e}")
                return False

    def transcribe(self):
        """Transcribes the temp audio file using Whisper."""
        if os.path.exists(config.TEMP_INPUT_AUDIO):
            result = self.model.transcribe(config.TEMP_INPUT_AUDIO)
            text = result["text"].lower().strip()
            
            # Simple filter to ignore empty hallucinations
            if text in ["you", "thank you", "bye"]: 
                return ""
            return text
        return ""