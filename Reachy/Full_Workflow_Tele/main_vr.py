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

        # Wizard of Oz
        self.experiment_started = False
        self.mic_muted = True # Start fully muted
        self.current_task = 0
        self.task_start_time = 0
        self.task_timer_active = False

        self.safety_monitor = SafetyMonitor(self.robot, self.speak_system)
        
        # --- INIT REALTIME BRAIN ---
        # embodied
        self.brain = RealtimeBrain(self.get_camera_data, self.is_mic_muted, condition="embodied")
        self.brain_loop = asyncio.new_event_loop()
        
        self.active_connection = None
        self.last_interaction_time = time.time()


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
        """Routes safety warnings directly to Reachy's mouth via OpenAI."""
        print(f"[System Override]: {text}")
        
        # We explicitly tell the LLM to use the exact body part description
        instruction = f"Your body just felt this: '{text}'. Tell the user this naturally in first-person, making sure to explicitly name the body part (e.g., 'Oh! My {text}!'). Do not read the raw numbers."
        
        if hasattr(self, 'brain') and self.brain.is_connected:
            asyncio.run_coroutine_threadsafe(
                self.brain.inject_proactive_thought(instruction), 
                self.brain_loop
            )

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
        
        # Package the tracker data into a string using only existing attributes
        report = f"Sorting Status: {self.vision_tracker.latest_status}\n"
        report += f"Block Counts: {self.vision_tracker.block_counts}\n"
        
        # Removed the 'detected_objects_report' line that was causing the crash
        
        return head_frame, report

    def start(self):
        self.safety_monitor.start()

        # Start the LLM Realtime loop in a background thread
        threading.Thread(target=self.start_realtime_thread, daemon=True).start()

        # Keep the display and VR inputs on the main thread
        self.display_loop()

    def is_mic_muted(self):
        """Callback for the brain to check if it should send audio."""
        return self.mic_muted
    
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
        print("WoZ Controls: 's'=Start/Unmute, '1-4'=Tasks, 'm'=Mute")
        
        while self.running:
            self.check_vr_button_state() 
            head_frame = self.robot.get_frame()
            torso_rgb, torso_depth = self.robot.get_torso_rgbd()

            if torso_rgb is not None and torso_depth is not None:
                processed_frame = self.vision_tracker.process_frame(torso_rgb, torso_depth)
                cv2.imshow("Reachy Depth Tracking", processed_frame)
                
            if head_frame is not None:
                cv2.imshow("Reachy VR Vision", head_frame)

            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                self.running = False
                self.brain.stop()
            elif key == ord('s'):
                if not self.experiment_started:
                    print("\n[WoZ] 'S' Pressed: Experiment Started! Mic Unmuted.")
                    self.experiment_started = True
                    self.mic_muted = False
            elif key == ord('m'):
                self.mic_muted = not self.mic_muted
                status = "MUTED" if self.mic_muted else "UNMUTED"
                print(f"\n[WoZ] 'M' Pressed: Microphone is now {status}")
            elif key == ord('1') and self.experiment_started:
                self.start_task(1)
            elif key == ord('2') and self.experiment_started:
                self.start_task(2)
            elif key == ord('3') and self.experiment_started:
                self.start_task(3)
            elif key == ord('4') and self.experiment_started:
                self.start_task(4)

        cv2.destroyAllWindows()

    def start_task(self, task_num):
        """WoZ helper to switch tasks and reset timers."""
        print(f"\n[WoZ] Starting Task {task_num}...")
        self.current_task = task_num
        self.task_start_time = time.time()
        self.task_timer_active = True
        
        # Inject the start prompt to Reachy
        if task_num == 1:
            asyncio.run_coroutine_threadsafe(
                self.brain.inject_proactive_thought("We are starting Task 1. Deliver your exact Task 1 Start script now."), 
                self.brain_loop
            )
        elif task_num == 2:
            asyncio.run_coroutine_threadsafe(
                self.brain.inject_proactive_thought("We are starting Task 2. Deliver your exact Task 2 Start script now."), 
                self.brain_loop
            )
        elif task_num == 4:
            asyncio.run_coroutine_threadsafe(
                self.brain.inject_proactive_thought("We are starting Task 4. Introduce the social sorting task and ask the user to pick up a block so you can tell them where it goes."), 
                self.brain_loop
            )


    async def proactive_engagement_loop(self):
        """Runs in the background and periodically pushes Reachy to engage based on Task timers."""
        
        # Track which milestones have been hit so we don't repeat them
        milestones = {"t1_230": False, "t1_500": False, "t1_730": False, "t1_1000": False,
                      "t2_100": False, "t2_200": False}
        
        while self.running:
            await asyncio.sleep(1) # Check every second
            
            if not self.brain.is_connected or not self.task_timer_active:
                continue
                
            elapsed_seconds = time.time() - self.task_start_time
            
            # --- TASK 1 TIMERS (10 Minutes) ---
            if self.current_task == 1:
                if elapsed_seconds >= 150 and not milestones["t1_230"]:
                    milestones["t1_230"] = True
                    await self.brain.inject_proactive_thought("2 minutes and 30 seconds have passed. Deliver your exact '2:30 mark' script for Task 1.")
                
                elif elapsed_seconds >= 300 and not milestones["t1_500"]:
                    milestones["t1_500"] = True
                    await self.brain.inject_proactive_thought("5 minutes have passed. Deliver your exact '5:00 mark' script for Task 1.")
                
                elif elapsed_seconds >= 450 and not milestones["t1_730"]:
                    milestones["t1_730"] = True
                    await self.brain.inject_proactive_thought("7 minutes and 30 seconds have passed. Deliver your exact '7:30 mark' script for Task 1.")
                
                elif elapsed_seconds >= 600 and not milestones["t1_1000"]:
                    milestones["t1_1000"] = True
                    self.task_timer_active = False # End timer
                    await self.brain.inject_proactive_thought("10 minutes have passed. Deliver your exact '10:00 mark' completion script for Task 1.")

            # --- TASK 2 TIMERS (2 Minutes) ---
            elif self.current_task == 2:
                if elapsed_seconds >= 60 and not milestones["t2_100"]:
                    milestones["t2_100"] = True
                    await self.brain.inject_proactive_thought("1 minute has passed. Deliver your exact '1:00 mark' script for Task 2.")
                
                elif elapsed_seconds >= 120 and not milestones["t2_200"]:
                    milestones["t2_200"] = True
                    self.task_timer_active = False # End timer
                    await self.brain.inject_proactive_thought("2 minutes have passed. Deliver your exact '2:00 mark' completion script for Task 2.")

if __name__ == '__main__':
    controller = ReachyControllerVR()
    controller.start()