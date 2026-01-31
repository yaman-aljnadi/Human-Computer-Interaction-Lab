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

    def turn_on(self):
        """Passes the turn_on command to the SDK."""
        self.sdk.turn_on()

    def turn_off_smoothly(self):
        """Passes the turn_off_smoothly command to the SDK."""
        self.sdk.turn_off_smoothly()

    # --- Accessors for Body Parts (Needed for movement.py) ---
    @property
    def head(self):
        return self.sdk.head

    @property
    def r_arm(self):
        return self.sdk.r_arm

    @property
    def l_arm(self):
        return self.sdk.l_arm

    # --- Existing Helper Methods ---
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
            
            if wait:
                time.sleep(3) 

    def disconnect(self):
        self.sdk.disconnect()