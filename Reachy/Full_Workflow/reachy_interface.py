import time
import os
import cv2
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView
import config

import contextlib  
import wave

from mutagen.mp3 import MP3 
from mutagen.wave import WAVE

class ReachyRobot:
    def __init__(self):
        print(f"Connecting to Reachy at {config.REACHY_IP}...")
        self.sdk = ReachySDK(host=config.REACHY_IP)
        if not self.sdk.is_connected():
            raise ConnectionError("Could not connect to Reachy 2.")
            
        try:
            self.sdk.audio.set_volume(80) 
        except:
            pass
        print("Reachy Connected.")

    def turn_on(self):
        """Passes the turn_on command to the SDK."""
        self.sdk.turn_on()

    def turn_off_smoothly(self):
        """Passes the turn_off_smoothly command to the SDK."""
        self.sdk.turn_off_smoothly()

    # Accessors for Body Parts (Needed for movement.py) 
    @property
    def head(self):
        return self.sdk.head

    @property
    def r_arm(self):
        return self.sdk.r_arm

    @property
    def l_arm(self):
        return self.sdk.l_arm

    # Existing Helper Methods 
    def get_frame(self):
        """Returns the left eye frame."""
        frame, _ = self.sdk.cameras.teleop.get_frame(CameraView.LEFT)
        return frame

    def look_forward(self):
        """Resets head position."""
        self.sdk.head.turn_on()
        self.sdk.head.look_at(x=1.0, y=0.0, z=0.0, duration=1.0)

    def play_audio(self, file_path, wait=True):
            """Uploads and plays audio. Calculates duration automatically."""
            if not os.path.exists(file_path):
                print(f"[Audio] Error: File not found: {file_path}")
                return

            # Calculate Duration
            duration = 5.0 # Default fallback
            try:
                if file_path.endswith('.mp3'):
                    audio = MP3(file_path)
                    duration = audio.info.length
                # THIS BLOCK HANDLES THE WAV FILE
                elif file_path.endswith('.wav'):
                    with contextlib.closing(wave.open(file_path, 'r')) as f:
                        frames = f.getnframes()
                        rate = f.getframerate()
                        duration = frames / float(rate)
                        
                print(f"[Audio] Detected duration: {duration:.2f} seconds")
            except Exception as e:
                print(f"[Audio] Could not read duration: {e}. Using default.")

            # Upload and Play
            print(f"[Audio] Uploading {file_path}...")
            self.sdk.audio.upload_audio_file(file_path)
            print("[Audio] Playing...")
            self.sdk.audio.play_audio_file(file_path)
                
            # Wait (Blocking)
            if wait:
                time.sleep(duration)

    def look_at_smooth(self, x, y, z):
        """
        Fast update for head tracking. 
        Clears previous commands to prevent 'memory' lag.
        """
        try:
            # IMPORTANT: Clear the queue so he doesn't "remember" old movements
            self.sdk.head.cancel_all_goto()
            
            # Duration must be slightly larger than your loop speed (latency)
            self.sdk.head.look_at(x=x, y=y, z=z, duration=0.2, wait=False)
        except Exception as e:
            print(f"Head Error: {e}")
            
    def disconnect(self):
        self.sdk.disconnect()