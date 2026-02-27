import time
import threading
import os
import cv2
import config
import openvr

import socket
import json

# Import the logic modules (Reusing your existing files)
from hearing import Ears
from speaking import Voice
from brain import Brain
from safety_monitor import SafetyMonitor
from reachy_interface import ReachyRobotVR

class ReachyControllerVR:
    def __init__(self):
        print(">>> STARTING VR COMPANION MODE <<<")
        self.robot = ReachyRobotVR() # Use the passive interface
        self.ears = Ears()
        self.voice = Voice()
        self.brain = Brain() 

        self.udp_ip = "127.0.0.1" # Localhost (sending to the same computer)
        self.udp_port = 5006      # The port Unity will listen on
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # State flags
        self.running = True
        self.is_processing = False
        self.conversation_mode = True # Default to True for VR usage usually
        self.is_muted = False

        self.safety_monitor = SafetyMonitor(self.robot, self.speak_system)
        
        # --- NEW: OPENVR SETUP ---
        self.vrsystem = None
        self.right_controller_id = None
        self.left_controller_id = None
        
        try:
            openvr.init(openvr.VRApplication_Background)
            self.vrsystem = openvr.VRSystem()
            print("[VR Input] OpenVR Initialized successfully.")
        except openvr.OpenVRError as e:
            print(f"[VR Input] OpenVR init failed (Is SteamVR running?): {e}")

    def start(self):
        """Starts the main loop and listener thread."""
        # Audio Greeting (No Wave)
        print("System Ready. Greeting user...")
        self.speak_and_wait("System online.")

        self.safety_monitor.start()

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
        # Define flexible lists of trigger phrases
        pause_commands = [
            "stop chatting", "stop conversation", "pause conversation", 
            "be quiet", "mute yourself", "stop talking", "go to sleep",
            "hold on a second"
        ]
        
        resume_commands = [
            "start conversation", "resume", "resume chatting", 
            "wake up", "unmute", "start talking", "let's talk", 
            "let's chat", "are you there"
        ]
        
        # Stop Command Logic
        if any(command in text for command in pause_commands):
            if self.conversation_mode: # Only trigger if currently talking
                self.conversation_mode = False
                self.speak_system("Pausing conversation.")
            return

        # Resume Command Logic
        if any(command in text for command in resume_commands):
            if not self.conversation_mode: # Only trigger if currently paused
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

        # For Unity Feedback
        subtitle_data = {
            "speech": response_text, 
            "emotion": emotion
        }
        try:
            self.sock.sendto(json.dumps(subtitle_data).encode('utf-8'), (self.udp_ip, self.udp_port))
        except Exception as e:
            print(f"UDP Error: {e}")
        ###

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

    def update_controller_ids(self):
        """Finds the device IDs for the left and right controllers."""
        if not self.vrsystem: 
            return
            
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            device_class = self.vrsystem.getTrackedDeviceClass(i)
            if device_class == openvr.TrackedDeviceClass_Controller:
                role = self.vrsystem.getControllerRoleForTrackedDeviceIndex(i)
                if role == openvr.TrackedControllerRole_RightHand:
                    self.right_controller_id = i
                elif role == openvr.TrackedControllerRole_LeftHand:
                    self.left_controller_id = i

    def check_vr_button_state(self):
        """Checks controller state and prints raw debug info."""
        if not self.vrsystem:
            return False
            
        if self.right_controller_id is None and self.left_controller_id is None:
            self.update_controller_ids()
            
        # 1 << 1 is usually B/Y. 1 << 7 is usually A/X on Quest.
        MENU_BUTTON_BITMASK = 1 << 1 
            
        # Check Right Controller
        if self.right_controller_id is not None:
            result, state = self.vrsystem.getControllerState(self.right_controller_id)
            if result and state.ulButtonPressed > 0:
                # \r overwrites the current line to prevent spamming your terminal
                print(f"\r[VR Debug] Right Controller Raw State: {state.ulButtonPressed}       ", end="")
                if bool(state.ulButtonPressed & MENU_BUTTON_BITMASK): 
                    print() # Move to a new line before triggering chat mode
                    return True

        # Check Left Controller
        if self.left_controller_id is not None:
            result, state = self.vrsystem.getControllerState(self.left_controller_id)
            if result and state.ulButtonPressed > 0:
                print(f"\r[VR Debug] Left Controller Raw State: {state.ulButtonPressed}        ", end="")
                if bool(state.ulButtonPressed & MENU_BUTTON_BITMASK):
                    print() # Move to a new line
                    return True
                
        return False
    
    def toggle_chat_mode(self):
        """Toggles the conversation mode via physical button press."""
        self.conversation_mode = not self.conversation_mode
        
        if self.conversation_mode:
            print("\n[VR Controller] Conversation Resumed.")
            # Run in a background thread to prevent freezing the display loop
            threading.Thread(target=self.speak_system, args=("Resuming conversation.",), daemon=True).start()
        else:
            print("\n[VR Controller] Conversation Paused.")
            threading.Thread(target=self.speak_system, args=("Pausing conversation.",), daemon=True).start()

    def display_loop(self):
        print("Display Active. Press 'q' to quit, 'm' to mute.")
        button_was_pressed = False 

        while self.running:
            is_button_pressed = self.check_vr_button_state() 

            if is_button_pressed and not button_was_pressed:
                self.toggle_chat_mode()
                button_was_pressed = True
            elif not is_button_pressed:
                button_was_pressed = False

            frame = self.robot.get_frame()

            # --- NEW: Package the HUD Data for Unity ---
            threat_level = self.safety_monitor.highest_threat_level
            # Extract just the text from the (level, text, color) tuples
            safety_texts = [msg[1] for msg in self.safety_monitor.status_messages]

            hud_data = {
                "is_muted": self.is_muted,
                "conversation_mode": self.conversation_mode,
                "threat_level": threat_level,
                "safety_messages": safety_texts
            }

            # Fire the data to Unity over UDP instantly
            try:
                self.sock.sendto(json.dumps(hud_data).encode('utf-8'), (self.udp_ip, self.udp_port))
            except Exception as e:
                pass # Ignore occasional network drops

            if frame is not None:
                key = cv2.waitKey(1)
                if key == ord('q'):
                    self.running = False
                elif key == ord('m'):
                    self.is_muted = not self.is_muted
                    print(f"Muted: {self.is_muted}")

                # Show the clean debug window on your PC monitor (no text overlay)
                cv2.imshow("Reachy VR Vision (Debug - No HUD)", frame)

        cv2.destroyAllWindows()
        self.safety_monitor.stop()
        self.robot.disconnect()



if __name__ == '__main__':
    controller = ReachyControllerVR()
    controller.start()