import time
import threading
import asyncio
import os
import cv2
import config
import openvr
import socket
import json

from safety_monitor import SafetyMonitor
from reachy_interface import ReachyRobotVR
from realtime_brain import RealtimeBrain 

class ReachyControllerVR:
    def __init__(self):
        print(">>> STARTING VR COMPANION MODE (REALTIME) <<<")
        self.robot = ReachyRobotVR()
        
        self.udp_ip = "127.0.0.1"
        self.udp_port = 5006
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.running = True
        self.is_muted = False
        self.conversation_mode = True

        self.safety_monitor = SafetyMonitor(self.robot, self.speak_system)
        
        # --- INIT REALTIME BRAIN ---
        self.brain = RealtimeBrain(self.get_camera_frame, condition="Co-Pilot")
        self.brain_loop = asyncio.new_event_loop()
        
        # OpenVR Setup (Kept the same)
        self.vrsystem = None
        self.right_controller_id, self.left_controller_id = None, None
        try:
            openvr.init(openvr.VRApplication_Background)
            self.vrsystem = openvr.VRSystem()
        except openvr.OpenVRError as e:
            print(f"[VR Input] OpenVR init failed: {e}")

    def get_camera_frame(self):
        """Callback for the brain to grab the VR view."""
        return self.robot.get_frame()

    def speak_system(self, text):
        """Keep this for quick local safety warnings if desired."""
        print(f"[System Override]: {text}")

    def start_realtime_thread(self):
        """Runs the Async WebSocket in a separate thread."""
        asyncio.set_event_loop(self.brain_loop)
        try:
            self.brain_loop.run_until_complete(self.brain.start_session())
        except Exception as e:
            print(f"Realtime loop ended: {e}")

    def start(self):
        self.safety_monitor.start()

        # Start the LLM Realtime loop in a background thread
        threading.Thread(target=self.start_realtime_thread, daemon=True).start()

        # Keep the display and VR inputs on the main thread
        self.display_loop()


    
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
        print("Display Active. Press 'q' to quit.")
        
        while self.running:
            # Check VR buttons (You might want to map this to mute the mic in the future)
            self.check_vr_button_state() 

            frame = self.robot.get_frame()

            if frame is not None:
                key = cv2.waitKey(1)
                if key == ord('q'):
                    self.running = False
                    self.brain.stop()

                cv2.imshow("Reachy VR Vision", frame)

        cv2.destroyAllWindows()
        self.safety_monitor.stop()
        self.robot.disconnect()

if __name__ == '__main__':
    controller = ReachyControllerVR()
    controller.start()