import time
import os
import cv2
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView
import config

class ReachyRobot:
    def __init__(self):
        print(f"Connecting to Reachy at {config.REACHY_IP}...")
        self.sdk = ReachySDK(host=config.REACHY_IP)
        if not self.sdk.is_connected():
            raise ConnectionError("Could not connect to Reachy 2.")
        print("Reachy Connected.")

    def get_frame(self):
        """Returns the left eye frame."""
        frame, _ = self.sdk.cameras.teleop.get_frame(CameraView.LEFT)
        return frame

    def look_forward(self):
        """Resets head position."""
        self.sdk.head.turn_on()
        self.sdk.head.look_at(x=1.0, y=0.0, z=0.0, duration=1.0)

    def play_audio(self, file_path, wait=True):
        """Uploads and plays audio on the robot."""
        if os.path.exists(file_path):
            self.sdk.audio.upload_audio_file(file_path)
            self.sdk.audio.play_audio_file(file_path)
            
            # Simple wait mechanism, can be improved with duration calculation
            if wait:
                time.sleep(3) 
                # Note: You might want to calculate exact duration using wave frame count

    def disconnect(self):
        self.sdk.disconnect()