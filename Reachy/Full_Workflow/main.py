import time
import threading
import os
import cv2
import re
import config
import wave
import contextlib


from movement import BodyLanguage
from hearing import Ears
from speaking import Voice
from brain import Brain
from reachy_interface import ReachyRobot

class ReachyController:
    def __init__(self):
        self.robot = ReachyRobot()
        self.ears = Ears()
        self.voice = Voice()
        self.brain = Brain() 

        self.body = BodyLanguage(self.robot) # Pass the robot instance
        self.robot.head.turn_on() # Ensure motors are stiff/ready
        
        self.running = True
        self.is_processing = False
        
        # Modes
        self.conversation_mode = False
        self.is_muted = False
        self.ptt_active = False # Flag for UI feedback
        self.last_ptt_time = 0  # Timestamp for logic synch
        
        self.pending_prompt = None

    def start(self):
        """Starts the main loop and listener thread."""
        listener_thread = threading.Thread(target=self.listen_loop)
        listener_thread.daemon = True
        listener_thread.start()

        self.display_loop()

    def listen_loop(self):
        while self.running:
            # Check if processing response (existing logic)
            if self.is_processing:
                time.sleep(0.5)
                continue
            
            # If muted, we sleep briefly and skip the listening step
            if self.is_muted:
                time.sleep(0.5)
                continue

            # It will block here until you speak.
            if self.ears.listen():
                text = self.ears.transcribe()
                if text:
                    was_ptt_active = (time.time() - self.last_ptt_time) < 1.5
                    print(f"User said: '{text}'")
                    self.handle_command(text, ptt_override=was_ptt_active)

    def handle_command(self, text, ptt_override=False):
            """Decides what to do based on user text."""
            
            # Stop Commands
            if "stop chatting" in text or "stop conversation" in text:
                print(">>> Switching to COMMAND MODE")
                self.conversation_mode = False
                self.speak_system("Okay, I am back to command mode.")
                return

            # Conversation Mode (Now Routes to process_request)
            if self.conversation_mode or ptt_override:
                self.is_processing = True
                # DIRECTLY call the new processing hub
                # This runs in the listener thread, so it won't freeze your camera!
                self.process_request(text) 
                return


            if "sing" in text.lower():
                print(">>> Singing Mode Activated")
                self.speak_and_wait("Okay, let me perform a song for you clear the dance floor for me.")
                
                self.body.start_dancing_behavior()
                
                # Check if file exists before trying to play
                if os.path.exists(config.SONG_FILE):
                    print(f"Playing {config.SONG_FILE}...")
                    self.robot.play_audio(config.SONG_FILE, wait=True)
                else:
                    print(f"ERROR: Could not find song file at {config.SONG_FILE}")
                    # Dance for 5 seconds anyway to test movement
                    time.sleep(5) 
                
                self.body.stop_dancing_behavior()
                self.is_processing = False
                return

            # Specific Commands (Command Mode)
            if "let's chat" in text:
                self.conversation_mode = True
                self.speak_system("I am ready to chat!")
                return

            # Simple movement commands can stay here
            elif "look at me" in text:
                self.robot.look_forward()
                self.speak_system("I am looking forward.")

    def speak_system(self, text):
        """Quick speech without VLM processing."""
        self.voice.synthesize(text, config.SYSTEM_AUDIO)
        self.robot.play_audio(config.SYSTEM_AUDIO)
        if os.path.exists(config.SYSTEM_AUDIO):
            os.remove(config.SYSTEM_AUDIO)


    def display_loop(self):
        print("Live Stream Active. Press 'q' to quit. Hold 't' to talk. Press 'm' to mute.")
        
        while self.running:
            frame = self.robot.get_frame()

            if frame is not None:
                # Key handling
                key = cv2.waitKey(1)
                if key == ord('q'):
                    self.running = False
                elif key == ord('t'):
                    self.ptt_active = True
                    self.last_ptt_time = time.time()
                
                # Mute Toggle 
                elif key == ord('m'):
                    self.is_muted = not self.is_muted
                    state = "MUTED" if self.is_muted else "UNMUTED"
                    print(f"Microphone is now {state}")
                
                
                else:
                    self.ptt_active = False

                # Priority order: Muted -> PTT -> Chat -> Command.  (for the UI)
                if self.is_muted:
                    mode_text = "MIC MUTED (Press 'm')"
                    color = (0, 0, 255) # Red
                elif self.ptt_active:
                    mode_text = "MODE: LISTENING (PTT)"
                    color = (255, 0, 0) # Blue
                elif self.conversation_mode:
                    mode_text = "MODE: CHAT"
                    color = (0, 255, 0) # Green
                else:
                    mode_text = "MODE: COMMAND"
                    color = (0, 0, 255) # Red

                cv2.putText(frame, mode_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                cv2.imshow("Reachy's Vision", frame)

        cv2.destroyAllWindows()
        self.robot.disconnect()

    def process_request(self, text):
        print(f"\n[Processing Request] User: {text}")
        # The Router: Check if visual info is needed
        visual_keywords = ["see", "look", "what is this", "find", "describe", "where is"]
        needs_vision = any(keyword in text.lower() for keyword in visual_keywords)
        
        visual_context = None
        
        # If Vision is needed
        if needs_vision:
            print("[Router] Visual Request Detected. Engaging Eyes...")
            self.speak_system("Let me take a look.") 
            
            frame = self.robot.get_frame()
            if frame is not None:
                # CHANGE HERE: We pass the 'text' (user's prompt) into the see function
                print(f"[VLM Input] Focusing on: '{text}'")
                visual_context = self.brain.see(frame, specific_prompt=text)
                
                print(f"[VLM Output] {visual_context}")
        
        # A & B Converge: The LLM thinks 
        print(f"[Router] Sending to Mind. Visual Context: {visual_context is not None}")
        
        # This calls the brain.think handles the merging
        response_text, emotion = self.brain.think(user_text=text, visual_context=visual_context)
        print(f"Reachy says ({emotion}): {response_text}")

        self.speak_and_wait(response_text, emotion)
        
        # Reset state
        self.is_processing = False

        if "sing" in text.lower():
            print(">>> Singing Mode Activated")
            self.speak_and_wait("Okay, let me perform a song for you.")
            
            # Add a buffer to ensure the Robot's audio device has released the previous TTS
            print("Preparing audio stream...")
            time.sleep(1.5) 

            # FORCE STOP LISTENING to clear ALSA/Mic conflicts
            self.is_processing = True 
            
            # Start the dance thread
            self.body.start_dancing_behavior()
            
            # Play the audio
            if os.path.exists(config.SONG_FILE):
                print(f"Playing {config.SONG_FILE}...")
                # The .mp3 will likely play reliably compared to the .wav
                self.robot.play_audio(config.SONG_FILE, wait=True)
            else:
                print(f"ERROR: Could not find song file at {config.SONG_FILE}")
                time.sleep(5) 
                        
            # Reset processing flag so he listens again
            self.is_processing = False
            return

    def speak_and_wait(self, text, emotion="neutral"):
        """Synthesizes speech (with emotion), moves robot, and waits."""
        
        # --- CHANGED HERE: Pass emotion to synthesize ---
        success = self.voice.synthesize(text, config.TEMP_OUTPUT_AUDIO, emotion)
        if not success: return

        # Get Duration (remains same)
        duration = 0
        if os.path.exists(config.TEMP_OUTPUT_AUDIO):
            import contextlib
            import wave
            # Note: OpenAI might output MP3. If wave.open fails, we might need 
            # to just trust a rough calculation or use pydub/mutagen to get length.
            # But the previous ReachyRobot.play_audio handles MP3 duration check!
            # So we rely on that for the actual play, but here we need duration for the sleep.
            
            # Quick fix: If it's MP3, we might need a library, OR just estimate:
            # English avg: 15 chars per second (rough estimate)
            duration = len(text) / 15.0 
            
            # If you want exact duration for MP3, you need 'mutagen' or 'pydub'
            # But let's try to see if we can read it or just use the estimation to keep it simple
            # since we don't want to install too many new libs.
            # Actually, your reachy_interface.py already imports Mutagen! Let's use it.
            try:
                from mutagen.mp3 import MP3
                audio = MP3(config.TEMP_OUTPUT_AUDIO)
                duration = audio.info.length
            except:
                pass # Fallback to estimate if mutagen fails or file is wav

        print(f"[Speaking] Duration: {duration:.2f}s")

        self.body.start_speaking_behavior()
        self.robot.play_audio(config.TEMP_OUTPUT_AUDIO, wait=False)
        
        time.sleep(duration + 0.5)

        self.body.stop_speaking_behavior()
        
        if os.path.exists(config.TEMP_OUTPUT_AUDIO):
            os.remove(config.TEMP_OUTPUT_AUDIO)

if __name__ == '__main__':
    controller = ReachyController()
    controller.start()