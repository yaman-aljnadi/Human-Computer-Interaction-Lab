import time
import threading
import os
import cv2
import re
import config

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
        
        self.running = True
        self.is_processing = False
        self.conversation_mode = False
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

            if self.ears.listen():
                text = self.ears.transcribe()
                if text:
                    print(f"User said: '{text}'")
                    self.handle_command(text)

    def handle_command(self, text):
        """Decides what to do based on user text."""
        
        if "stop chatting" in text or "stop conversation" in text:
            print(">>> Switching to COMMAND MODE")
            self.conversation_mode = False
            self.speak_system("Okay, I am back to command mode.")
            return

        if self.conversation_mode:
            print(f">>> Conversational Input: {text}")
            self.pending_prompt = f"Let's have a conversation. I said '{text}'."
            self.is_processing = True
            return

        if "let's chat" in text or "start conversation" in text:
            self.conversation_mode = True
            self.speak_system("I am ready to chat! What is on your mind?")
            return

        if "tell me what you see" in text or "describe" in text:
            self.pending_prompt = "Use two sentences to tell me what you see. Make it funny."
            self.is_processing = True

        elif "find" in text and "for me" in text:
            match = re.search(r"find (.*?) for me", text)
            if match:
                obj = match.group(1)
                self.pending_prompt = f"I am looking for {obj}. Tell me if you see it and where."
                self.is_processing = True

        elif "look at me" in text or "look forward" in text:
            self.is_processing = True
            self.robot.look_forward()
            self.speak_system("I am looking forward now.")
            self.is_processing = False

    def speak_system(self, text):
        """Quick speech without VLM processing."""
        self.voice.synthesize(text, config.SYSTEM_AUDIO)
        self.robot.play_audio(config.SYSTEM_AUDIO)
        if os.path.exists(config.SYSTEM_AUDIO):
            os.remove(config.SYSTEM_AUDIO)

    def process_vision_request(self, frame):
        """Sends image + prompt to Brain, then speaks result."""
        print("\n[Processing VLM Request...]")
        
        response_text = self.brain.think(frame, self.pending_prompt)
        print(f"Reachy says: {response_text}")

        # Speak result
        self.voice.synthesize(response_text, config.TEMP_OUTPUT_AUDIO)
        
        # Calculate approximate wait time based on text length or just wait
        # (Using a fixed 10s wait as per your original code logic, though dynamic is better)
        self.robot.play_audio(config.TEMP_OUTPUT_AUDIO) 
        time.sleep(10) 

        # Cleanup
        if os.path.exists(config.TEMP_OUTPUT_AUDIO):
            os.remove(config.TEMP_OUTPUT_AUDIO)
            
        self.pending_prompt = None
        self.is_processing = False
        print("[Ready to listen again]")

    def display_loop(self):
        """Main thread loop: GUI and Logic Trigger."""
        print("Live Stream Active. Press 'q' to quit.")
        
        while self.running:
            frame = self.robot.get_frame()

            if frame is not None:
                # Visualize Mode
                color = (0, 255, 0) if self.conversation_mode else (0, 0, 255)
                mode_text = "MODE: CHAT" if self.conversation_mode else "MODE: COMMAND"
                cv2.putText(frame, mode_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                # Check for processing request
                if self.pending_prompt is not None:
                    # We process synchronously here to freeze frame for analysis
                    self.process_vision_request(frame)

                cv2.imshow("Reachy's Vision", frame)

            key = cv2.waitKey(1)
            if key == ord('q'):
                self.running = False

        cv2.destroyAllWindows()
        self.robot.disconnect()

if __name__ == '__main__':
    controller = ReachyController()
    controller.start()