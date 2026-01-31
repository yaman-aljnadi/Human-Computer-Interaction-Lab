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
                if self.is_processing:
                    time.sleep(0.5)
                    continue

                # No arguments needed now. It will block here until you speak.
                if self.ears.listen():
                    text = self.ears.transcribe()
                    if text:
                        # Check if PTT was used (same logic as before)
                        was_ptt_active = (time.time() - self.last_ptt_time) < 1.5
                        
                        print(f"User said: '{text}'")
                        self.handle_command(text, ptt_override=was_ptt_active)

    def handle_command(self, text, ptt_override=False):
            """Decides what to do based on user text."""
            
            # 1. Stop Commands
            if "stop chatting" in text or "stop conversation" in text:
                print(">>> Switching to COMMAND MODE")
                self.conversation_mode = False
                self.speak_system("Okay, I am back to command mode.")
                return

            # 2. Conversation Mode (Now Routes to process_request)
            if self.conversation_mode or ptt_override:
                self.is_processing = True
                # DIRECTLY call the new processing hub
                # This runs in the listener thread, so it won't freeze your camera!
                self.process_request(text) 
                return

            # 3. Specific Commands (Command Mode)
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
            print("Live Stream Active. Press 'q' to quit. Hold 't' to talk.")
            
            while self.running:
                frame = self.robot.get_frame()

                if frame is not None:
                    # PTT Logic
                    key = cv2.waitKey(1)
                    if key == ord('q'):
                        self.running = False
                    elif key == ord('t'):
                        self.ptt_active = True
                        self.last_ptt_time = time.time()
                    else:
                        self.ptt_active = False

                    # UI Text
                    if self.ptt_active:
                        mode_text = "MODE: LISTENING (PTT)"
                        color = (255, 0, 0)
                    elif self.conversation_mode:
                        mode_text = "MODE: CHAT"
                        color = (0, 255, 0)
                    else:
                        mode_text = "MODE: COMMAND"
                        color = (0, 0, 255)

                    cv2.putText(frame, mode_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                    
                    # REMOVED: The check for self.pending_prompt is gone.
                    # The processing now happens in the listener thread.

                    cv2.imshow("Reachy's Vision", frame)

            cv2.destroyAllWindows()
            self.robot.disconnect()

    def process_request(self, text):
            """
            The new central processing hub.
            Replaces: process_vision_request
            """
            print(f"\n[Processing Request] User: {text}")
            
            # 1. The Router: Check if visual info is needed
            visual_keywords = ["see", "look", "what is this", "find", "describe", "where is"]
            needs_vision = any(keyword in text.lower() for keyword in visual_keywords)
            
            visual_context = None
            
            # 2. Path B: Vision is needed
            if needs_vision:
                print("[Router] Visual Request Detected. Engaging Eyes...")
                self.speak_system("Let me take a look.") 
                
                frame = self.robot.get_frame()
                if frame is not None:
                    # CHANGE HERE: We pass the 'text' (user's prompt) into the see function
                    print(f"[VLM Input] Focusing on: '{text}'")
                    visual_context = self.brain.see(frame, specific_prompt=text)
                    
                    print(f"[VLM Output] {visual_context}")
            
            # 3. Path A & B Converge: The LLM thinks
            print(f"[Router] Sending to Mind. Visual Context: {visual_context is not None}")
            
            # This calls the new brain.think which handles the merging
            response = self.brain.think(user_text=text, visual_context=visual_context)
            
            print(f"Reachy says: {response}")
            self.speak_and_wait(response)
            
            # Reset state
            self.is_processing = False

    def speak_and_wait(self, text):
            """Synthesizes speech, moves robot, and waits."""
            
            # 1. Synthesize Audio
            success = self.voice.synthesize(text, config.TEMP_OUTPUT_AUDIO)
            if not success: return

            # 2. Get Duration
            duration = 0
            if os.path.exists(config.TEMP_OUTPUT_AUDIO):
                with contextlib.closing(wave.open(config.TEMP_OUTPUT_AUDIO, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = frames / float(rate)

            print(f"[Speaking] Duration: {duration:.2f}s")

            # 3. START MOVEMENT (The robot starts looking alive)
            self.body.start_speaking_behavior()

            # 4. START AUDIO
            self.robot.play_audio(config.TEMP_OUTPUT_AUDIO, wait=False)
            
            # 5. WAIT
            # We sleep while the background thread wiggles the antennas
            time.sleep(duration + 0.5)

            # 6. STOP MOVEMENT (The robot goes back to rest)
            self.body.stop_speaking_behavior()

            # Cleanup
            if os.path.exists(config.TEMP_OUTPUT_AUDIO):
                os.remove(config.TEMP_OUTPUT_AUDIO)

if __name__ == '__main__':
    controller = ReachyController()
    controller.start()