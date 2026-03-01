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
from vision_tracker import VisionTracker

class ReachyControllerVR:
    def __init__(self):
        print(">>> STARTING VR COMPANION MODE (REALTIME) <<<")
        self.robot = ReachyRobotVR()
        self.vision_tracker = VisionTracker()
        
        self.udp_ip = "127.0.0.1"
        self.udp_port = 5006
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.running = True
        self.is_muted = False
        self.conversation_mode = True

        self.safety_monitor = SafetyMonitor(self.robot, self.speak_system)
        
        # --- INIT REALTIME BRAIN ---
        # embodied
        self.brain = RealtimeBrain(self.get_camera_frame, condition="embodied")
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

    def get_camera_data(self):
        """Callback for the brain to grab the VR view AND the CV report."""
        head_frame = self.robot.get_frame()
        
        # Package the tracker data into a string
        report = f"Sorting Status: {self.vision_tracker.latest_status}\n"
        report += f"Block Counts: {self.vision_tracker.block_counts}\n"
        report += "Detected Items:\n" + "\n".join(self.vision_tracker.detected_objects_report)
        
        return head_frame, report

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
            self.check_vr_button_state() 

            # Get the head camera for VR viewing (and OpenAI)
            head_frame = self.robot.get_frame()
            
            # --- NEW: Get the 3D Torso Camera frames ---
            torso_rgb, torso_depth = self.robot.get_torso_rgbd()

            # Process the torso vision if available
            if torso_rgb is not None and torso_depth is not None:
                # We now pass BOTH frames into the tracker
                processed_frame = self.vision_tracker.process_frame(torso_rgb, torso_depth)
                
                # Show the tracking on the torso camera feed
                cv2.imshow("Reachy Depth Tracking", processed_frame)
                
            # Keep showing the raw head camera for the VR headset
            if head_frame is not None:
                cv2.imshow("Reachy VR Vision", head_frame)

            key = cv2.waitKey(1)
            if key == ord('q'):
                self.running = False
                self.brain.stop()

        cv2.destroyAllWindows()

if __name__ == '__main__':
    controller = ReachyControllerVR()
    controller.start()