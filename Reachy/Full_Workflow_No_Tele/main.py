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

import pyaudio

class ReachyController:
    def __init__(self):
        self.robot = ReachyRobot()
        self.body = BodyLanguage(self.robot)
        self.robot.head.turn_on()
        
        self.running = True
        self.is_muted = False
        
        self.tracker = HeadTracker(self.robot)
        self.tracking_active = True 

        self.playback_lock = threading.Lock() 
        self.is_briefing_time = False

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

    def check_if_muted(self, force_mute=None):
        """Callback for the brain to know if it should ignore the mic."""
        if force_mute:
            self.is_briefing_time = True
            self.is_muted = True
            print(">>> Intro Finished: Mic Permanently Locked for Briefing.")
            
        # Return True if temporarily muted OR permanently locked
        return self.is_muted or self.is_briefing_time

    def play_generated_audio(self, filepath):
        """
        Triggered by the Brain. We spawn a separate thread here so 
        the audio playback doesn't freeze the OpenAI WebSocket loop!
        """
        print(f"[Main] Audio file ready. Spawning playback thread...")
        threading.Thread(target=self._playback_routine, args=(filepath,)).start()

    def _playback_routine(self, filepath):
        """Handles the precise timing and muting for Reachy's speech."""
        
        with self.playback_lock:
            
            if not self.tracking_active:
                self.body.start_speaking_behavior()
            
            was_muted = self.is_muted
            self.is_muted = True 
            
            duration = 5.0 
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

            # --- CHANGED: Route audio based on experiment condition ---
            if config.EXPERIMENT_CONDITION == "copilot":
                print("[Main] Copilot Mode: Playing audio locally via computer.")
                # Run locally in a thread so it doesn't block our sleep timer
                threading.Thread(target=self.play_audio_locally, args=(filepath,)).start()
            else:
                print("[Main] Embodied Mode: Playing audio on Reachy.")
                self.robot.play_audio(filepath, wait=False)
            
            time.sleep(duration + 1.0)
            
            if not self.is_briefing_time:
                self.is_muted = was_muted
            
            if not self.tracking_active:
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

    def play_audio_locally(self, filepath):
        """Plays a wav file through the computer's default speakers."""
        try:
            wf = wave.open(filepath, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            
            data = wf.readframes(1024)
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(1024)
                
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            print(f"[Main] Local audio playback failed: {e}")

    def trigger_dance(self):
        """Called automatically by the Brain when the LLM decides to dance."""
        # Use a thread so the WebSocket connection doesn't freeze!
        threading.Thread(target=self.perform_song).start()

    def start(self):
        # Wave animation
        wave_thread = threading.Thread(target=self.body.perform_wave)
        wave_thread.start()

        # 2. Start the Brain's listening/WebSocket loop (Keep ONLY this one)
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