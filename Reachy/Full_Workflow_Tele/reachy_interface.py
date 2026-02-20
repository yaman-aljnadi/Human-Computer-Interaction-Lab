import time
import os
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView
import config
import contextlib  
import wave
from mutagen.mp3 import MP3 
import pygame

class ReachyRobotVR:
    def __init__(self):
        print(f"[VR Interface] Connecting to Reachy at {config.REACHY_IP}...")
        
        # Connect to SDK
        self.sdk = ReachySDK(host=config.REACHY_IP)
        
        if not self.sdk.is_connected():
            raise ConnectionError("Could not connect to Reachy 2.")
            
        # We DO NOT call self.sdk.turn_on() here. 
        # The VR system handles motor stiffness. We must stay passive.
        

        # HEARING THE VOICE FROM REACHY 
        # try:
        #     self.sdk.audio.set_volume(80) 
        # except:
        #     pass
        # print("[VR Interface] Reachy Connected (Passive Mode).")

        # HEARING THE VOICE FROM THE HEADSET
        try:
            pygame.mixer.init()
            print("[VR Interface] Local Audio Mixer Ready for Headset.")
        except Exception as e:
            print(f"[Audio Init Error] {e}")

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

        # 1. Calculate EXACT duration using calibrate_speech logic
        duration = 5.0 
        try:
            if file_path.endswith('.wav'):
                with contextlib.closing(wave.open(file_path, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = frames / float(rate)
            elif file_path.endswith('.mp3'):
                audio = MP3(file_path)
                duration = audio.info.length
        except Exception as e:
            print(f"[Audio] Could not read duration: {e}. Using default.")

        # # 2. Play the file on Reachy
        # # HEARING THE VOICE FROM REACHY 
        # try:
        #     self.sdk.audio.upload_audio_file(file_path)
        #     self.sdk.audio.play_audio_file(file_path)
        # except Exception as e:
        #     print(f"[Audio Error] {e}")

        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"[Audio Error] {e}")
            
        # 3. Wait exact duration + positive buffer to avoid loop listening
        if wait:
            # Add a small POSITIVE buffer (0.2s to 0.5s) to outlast the playback tail
            time.sleep(duration + 0.3)
            
            # --- NEW: Force Pygame to release the file lock ---
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload() 
            except AttributeError:
                pass # Safety catch for older Pygame versions

    def disconnect(self):
        self.sdk.disconnect()