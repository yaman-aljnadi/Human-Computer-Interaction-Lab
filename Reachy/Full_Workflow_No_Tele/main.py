import time
import threading
import asyncio
import os
import cv2
import config

import wave
import contextlib

from movement import BodyLanguage
from reachy_interface import ReachyRobot
from tracker import HeadTracker
from brain_realtime import RealtimeBrainNonTeleop 


class ReachyController:
    def __init__(self):
        self.robot = ReachyRobot()
        self.body = BodyLanguage(self.robot)
        self.robot.head.turn_on()
        
        self.running = True
        self.is_muted = False
        
        self.tracker = HeadTracker(self.robot)
        self.tracking_active = False 

        # Init the new async loop and brain
        self.brain_loop = asyncio.new_event_loop()
        self.brain = RealtimeBrainNonTeleop(
            get_frame_callback=self.get_camera_frame,
            get_mute_state_callback=self.check_if_muted,
            on_speech_ready_callback=self.play_generated_audio,
            on_dance_command_callback=self.trigger_dance
        )

    def get_camera_frame(self):
        """Callback for the brain to grab the camera view."""
        self.robot.look_forward()
        time.sleep(0.5) # Let servos settle before taking the picture
        return self.robot.get_frame()

    def check_if_muted(self):
        """Callback for the brain to know if it should ignore the mic."""
        return self.is_muted

    def play_generated_audio(self, filepath):
        """
        Triggered by the Brain. We spawn a separate thread here so 
        the audio playback doesn't freeze the OpenAI WebSocket loop!
        """
        print(f"[Main] Audio file ready. Spawning playback thread...")
        threading.Thread(target=self._playback_routine, args=(filepath,)).start()

    def _playback_routine(self, filepath):
        """Handles the precise timing and muting for Reachy's speech."""
        self.body.start_speaking_behavior()
        
        # 1. Hard mute the microphone
        was_muted = self.is_muted
        self.is_muted = True 
        
        # 2. Calculate EXACT duration of the .wav file
        duration = 5.0 # Fallback in case of read error
        try:
            import wave
            import contextlib
            with contextlib.closing(wave.open(filepath, 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                duration = frames / float(rate)
            print(f"[Main] Calculated audio duration: {duration:.2f}s")
        except Exception as e:
            print(f"[Main] Could not read duration: {e}")

        # 3. Play via SDK, but tell reachy_interface NOT to wait. 
        # We handle the waiting locally so we can perfectly control the mic.
        self.robot.play_audio(filepath, wait=False)
        
        # 4. Sleep for the duration of the audio PLUS a 1.0 second safety buffer.
        # This gives the SDK time to upload the file, and ensures the mic stays 
        # dead until the room echoes settle.
        time.sleep(duration + 1.0)
        
        # 5. Restore microphone state
        self.is_muted = was_muted
        self.body.stop_speaking_behavior()
        
        if os.path.exists(filepath):
            os.remove(filepath)

    def start_realtime_thread(self):
        """Runs the OpenAI WebSocket connection in the background."""
        asyncio.set_event_loop(self.brain_loop)
        try:
            self.brain_loop.run_until_complete(self.brain.start_session())
        except Exception as e:
            print(f"Realtime loop ended: {e}")

    def trigger_dance(self):
        """Called automatically by the Brain when the LLM decides to dance."""
        # Use a thread so the WebSocket connection doesn't freeze!
        threading.Thread(target=self.perform_song).start()

    def start(self):
        # Wave animation
        wave_thread = threading.Thread(target=self.body.perform_wave)
        wave_thread.start()
        wave_thread.join()

        # Start the Brain's listening/WebSocket loop
        threading.Thread(target=self.start_realtime_thread, daemon=True).start()

        self.display_loop()

    def display_loop(self):
        print("Live Stream Active.") 
        print("Controls: 'q': Quit | 'm': Mute | 's': Sing | 'f': Follow Face")
        
        while self.running:
            frame = self.robot.get_frame()

            if frame is not None:
                if self.tracking_active:
                    self.tracker.track_face(frame)
                    cv2.putText(frame, "MODE: FACE TRACKING", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

                key = cv2.waitKey(1)
                
                if key == ord('q'):
                    self.running = False
                    self.brain.stop()

                elif key == ord('f'):
                    self.tracking_active = not self.tracking_active
                    state = "ON" if self.tracking_active else "OFF"
                    print(f">>> Face Tracking {state}")
                    if self.tracking_active:
                        self.robot.look_forward() 
                
                elif key == ord('m'):
                    self.is_muted = not self.is_muted
                    state = "MUTED" if self.is_muted else "UNMUTED"
                    print(f"Microphone is now {state}")

                elif key == ord('s'):
                    threading.Thread(target=self.perform_song).start()

                # UI TEXT UPDATES
                if self.is_muted:
                    mode_text = "MIC MUTED (Press 'm')"
                    color = (0, 0, 255) # Red
                else:
                    mode_text = "MODE: CHAT (Listening...)" 
                    color = (0, 255, 0) # Green

                cv2.putText(frame, mode_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                cv2.imshow("Reachy's Vision", frame)

        cv2.destroyAllWindows()
        self.robot.disconnect()

    def perform_song(self):
        """The singing logic, triggered by UI button."""
        print(">>> Singing Mode Activated")
        
        # Mute the brain temporarily so it doesn't try to transcribe the song!
        was_muted = self.is_muted
        self.is_muted = True 
        
        time.sleep(1.0) 
        self.body.start_dancing_behavior()
        
        if os.path.exists(config.SONG_FILE):
            print(f"Playing {config.SONG_FILE}...")
            self.robot.play_audio(config.SONG_FILE, wait=True)
        else:
            print(f"ERROR: Song file not found at {config.SONG_FILE}")
            time.sleep(5) 
        
        self.body.stop_dancing_behavior()
        self.is_muted = was_muted # Restore previous mute state
        print(">>> Singing Complete")

if __name__ == '__main__':
    controller = ReachyController()
    controller.start()