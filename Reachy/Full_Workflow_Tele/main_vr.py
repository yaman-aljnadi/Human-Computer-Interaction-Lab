import time
import threading
import os
import cv2
import config

# Import the logic modules (Reusing your existing files)
from hearing import Ears
from speaking import Voice
from brain import Brain

# Import the NEW VR Interface
from reachy_interface import ReachyRobotVR

class ReachyControllerVR:
    def __init__(self):
        print(">>> STARTING VR COMPANION MODE <<<")
        self.robot = ReachyRobotVR() # Use the passive interface
        self.ears = Ears()
        self.voice = Voice()
        self.brain = Brain() 

        # State flags
        self.running = True
        self.is_processing = False
        self.conversation_mode = True # Default to True for VR usage usually
        self.is_muted = False
        
    def start(self):
        """Starts the main loop and listener thread."""
        
        # Audio Greeting (No Wave)
        print("System Ready. Greeting user...")
        self.speak_and_wait("System online. I am ready to assist you in Virtual Reality.")

        # Start Listening Thread
        listener_thread = threading.Thread(target=self.listen_loop)
        listener_thread.daemon = True
        listener_thread.start()

        # Start Display Loop (For debug on PC screen)
        self.display_loop()

    def listen_loop(self):
        print("[Listener] Mic Active.")
        while self.running:
            if self.is_processing or self.is_muted:
                time.sleep(0.5)
                continue
            
            # Note: We removed body.start_listening_behavior()
            
            if self.ears.listen():
                text = self.ears.transcribe()
                if text:
                    print(f"User said: '{text}'")
                    self.handle_command(text)

    def handle_command(self, text):
        """Decides what to do based on user text."""
        
        # Stop Command
        if "stop chatting" in text or "stop conversation" in text:
            self.conversation_mode = False
            self.speak_system("Pausing conversation.")
            return

        # Resume Command
        if "start conversation" in text or "resume" in text:
            self.conversation_mode = True
            self.speak_system("Resuming conversation.")
            return

        # If in chat mode, send to Brain
        if self.conversation_mode:
            self.is_processing = True
            self.process_request(text)

    def process_request(self, text):
        print(f"\n[Processing Request] User: {text}")
        
        # Define the passive camera callback
        def camera_callback():
            self.speak_system("Let me see.") 
            # In VR mode, we DO NOT move the head. We just grab what the user is looking at.
            return self.robot.get_frame()

        # Send to Brain
        # The brain returns emotion, but we ignore it since we can't move!
        response_text, emotion = self.brain.think(text, camera_callback)
        
        print(f"Reachy says: {response_text}")
        self.speak_and_wait(response_text)
        
        self.is_processing = False

    def speak_and_wait(self, text):
        """Synthesizes and plays speech without movement."""
        success = self.voice.synthesize(text, config.TEMP_OUTPUT_AUDIO)
        if success:
            self.robot.play_audio(config.TEMP_OUTPUT_AUDIO, wait=True)
            if os.path.exists(config.TEMP_OUTPUT_AUDIO):
                os.remove(config.TEMP_OUTPUT_AUDIO)

    def speak_system(self, text):
        """Quick system notifications."""
        self.voice.synthesize(text, config.SYSTEM_AUDIO)
        self.robot.play_audio(config.SYSTEM_AUDIO, wait=True)
        if os.path.exists(config.SYSTEM_AUDIO):
            os.remove(config.SYSTEM_AUDIO)

    def display_loop(self):
        print("Display Active. Press 'q' to quit, 'm' to mute.")
        while self.running:
            # We still show the camera feed on the PC for debugging
            # so you can see what the VLM is seeing.
            frame = self.robot.get_frame()

            if frame is not None:
                key = cv2.waitKey(1)
                if key == ord('q'):
                    self.running = False
                elif key == ord('m'):
                    self.is_muted = not self.is_muted
                    print(f"Muted: {self.is_muted}")

                # UI Overlay
                status = "MUTED" if self.is_muted else "LISTENING"
                color = (0, 0, 255) if self.is_muted else (0, 255, 0)
                cv2.putText(frame, f"VR COMPANION MODE | {status}", (30, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                cv2.imshow("Reachy VR Vision (Debug)", frame)

        cv2.destroyAllWindows()
        self.robot.disconnect()

if __name__ == '__main__':
    controller = ReachyControllerVR()
    controller.start()