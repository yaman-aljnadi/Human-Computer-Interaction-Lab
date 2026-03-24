import time
import os
import threading
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

        # HEARING THE VOICE FROM REACHY 
        # try:
        #     self.sdk.audio.set_volume(80) S
        # except:
        #     pass
        # print("[VR Interface] Reachy Connected (Passive Mode).")
        # HEARING THE VOICE FROM THE HEADSET
        
        try:
            pygame.mixer.init()
            print("[VR Interface] Local Audio Mixer Ready for Headset.")
        except Exception as e:
            print(f"[Audio Init Error] {e}")

        # --- NEW: Tracking ID for audio interruptions ---
        self._current_audio_id = 0
        self._timed_stop_thread = None

    def get_frame(self):
        """Returns the left eye frame for the VLM."""
        if self.sdk.cameras.teleop is None:
            return None

        try:
            result = self.sdk.cameras.teleop.get_frame(CameraView.LEFT)
            if result is None:
                return None
            frame, _ = result
            return frame
        except Exception as e:
            print(f"[Camera] Error getting frame: {e}")
            return None

    def play_audio(self, file_path, wait=True):
        """Uploads and plays audio through the robot's speakers, with interrupt support."""
        if not os.path.exists(file_path):
            print(f"[Audio] Error: File not found: {file_path}")
            return

        # 1. Calculate EXACT duration
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

        # --- NEW: Update the Audio ID ---
        # By incrementing this, any older thread currently in its "wait" loop
        # will realize it has been interrupted and immediately stop waiting.
        self._current_audio_id += 1
        my_audio_id = self._current_audio_id

        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"[Audio Error] {e}")
            
        # 3. Wait exact duration, but allow for immediate interruptions
        if wait:
            start_time = time.time()
            
            # Replaced time.sleep() with a checking loop
            while (time.time() - start_time) < (duration + 0.3):
                # If a new audio file started playing, abort the wait!
                if my_audio_id != self._current_audio_id:
                    print("[Audio] Wait aborted: Speech interrupted by a new command.")
                    return 
                
                time.sleep(0.1) # Brief pause to prevent CPU pegging
            
            # --- Only unload if we are still the active audio track ---
            if my_audio_id == self._current_audio_id:
                pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload() 
                except AttributeError:
                    pass 

    def stop_audio(self):
        """Stops any currently playing audio and invalidates existing wait loops."""
        self._current_audio_id += 1
        pygame.mixer.music.stop()
        try:
            pygame.mixer.music.unload()
        except AttributeError:
            pass

    def play_audio_for_duration(self, file_path, duration_seconds):
        """Plays audio immediately and stops it after a fixed duration unless interrupted."""
        self.stop_audio()
        self.play_audio(file_path, wait=False)

        my_audio_id = self._current_audio_id

        def _stop_after_delay():
            time.sleep(duration_seconds)
            if my_audio_id == self._current_audio_id:
                self.stop_audio()

        self._timed_stop_thread = threading.Thread(target=_stop_after_delay, daemon=True)
        self._timed_stop_thread.start()

    def disconnect(self):
        self.sdk.disconnect()


    def get_torso_rgbd(self):
            """Returns the RGB frame and Depth frame from the torso camera."""
            if self.sdk.cameras.depth is None:
                return None, None

            try:
                # Get the color image
                rgb_result = self.sdk.cameras.depth.get_frame()
                # Get the 3D depth map
                depth_result = self.sdk.cameras.depth.get_depth_frame()

                if rgb_result is None or depth_result is None:
                    return None, None

                rgb_frame, _ = rgb_result
                depth_frame, _ = depth_result
                return rgb_frame, depth_frame
                
            except Exception as e:
                print(f"[Depth Camera] Error: {e}")
                return None, None
