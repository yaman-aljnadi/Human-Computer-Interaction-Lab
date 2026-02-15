import time
import os
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView
import config
import contextlib  
import wave
from mutagen.mp3 import MP3 

class ReachyRobotVR:
    def __init__(self):
        print(f"[VR Interface] Connecting to Reachy at {config.REACHY_IP}...")
        
        # Connect to SDK
        self.sdk = ReachySDK(host=config.REACHY_IP)
        
        if not self.sdk.is_connected():
            raise ConnectionError("Could not connect to Reachy 2.")
            
        # We DO NOT call self.sdk.turn_on() here. 
        # The VR system handles motor stiffness. We must stay passive.
        
        try:
            self.sdk.audio.set_volume(80) 
        except:
            pass
        print("[VR Interface] Reachy Connected (Passive Mode).")

    def get_frame(self):
        """Returns the left eye frame for the VLM."""
        if self.sdk.cameras.teleop is None:
            return None

        try:
            # We passively grab the frame. We do NOT move the head to look.
            result = self.sdk.cameras.teleop.get_frame(CameraView.LEFT)
            if result is None:
                return None
            frame, _ = result
            return frame
        except Exception as e:
            print(f"[Camera] Error getting frame: {e}")
            return None

    def play_audio(self, file_path, wait=True):
        """Uploads and plays audio through the robot's speakers."""
        if not os.path.exists(file_path):
            print(f"[Audio] Error: File not found: {file_path}")
            return

        # Calculate Duration (reused logic from your original code)
        duration = 5.0 
        try:
            if file_path.endswith('.mp3'):
                audio = MP3(file_path)
                duration = audio.info.length
            elif file_path.endswith('.wav'):
                with contextlib.closing(wave.open(file_path, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = frames / float(rate)
        except Exception as e:
            print(f"[Audio] Could not read duration: {e}. Using default.")

        # Play
        try:
            self.sdk.audio.upload_audio_file(file_path)
            self.sdk.audio.play_audio_file(file_path)
        except Exception as e:
            print(f"[Audio Error] {e}")
            
        if wait:
            # We wait so the script doesn't listen to its own voice
            time.sleep(duration - 0.5)

    def disconnect(self):
        self.sdk.disconnect()