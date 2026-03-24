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
        print(f">>> STARTING VR COMPANION MODE ({config.EXPERIMENT_CONDITION.upper()}) <<<")
        self.robot = ReachyRobotVR()
        self.vision_tracker = VisionTracker()
        
        # Failed Unity Connection Attempt 
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

        self.task_durations = {
            1: 420,
            2: 120,  
        }

        self.task_2_metronome_path = os.path.join(
            os.path.dirname(__file__),
            "Researcher_Mode",
            "60_Metronome.mp3",
        )


        # Track milestones at the class level
        self.milestones = {
            "t1_230": False, "t1_500": False, "t1_700": False,
            "t2_100": False, "t2_200": False
        }

        self.safety_monitor = SafetyMonitor(self.robot, self.speak_system)
        
        # --- INIT REALTIME BRAIN ---
        # UPDATED: We removed the hardcoded condition="embodied" because RealtimeBrain 
        # now handles it internally via config.EXPERIMENT_CONDITION.
        self.brain = RealtimeBrain(self.get_camera_data, self.is_mic_muted, self.stop_timers)
        self.brain_loop = asyncio.new_event_loop()
        
        self.active_connection = None
        self.last_interaction_time = time.time()

        # OpenVR Setup 
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
        
        # --- NEW: Branch the instruction based on condition ---
        if config.EXPERIMENT_CONDITION == "copilot":
            instruction = f"The robot just felt this: '{text}'. Tell the Operator this naturally, showing friendly concern. Explicitly name the body part but refer to it in the third person (e.g., 'Oh! The robot's {text}!'). Do not read the raw numbers."
        else:
            instruction = f"Your body just felt this: '{text}'. Tell the user this naturally in first-person, making sure to explicitly name the body part (e.g., 'Oh! My {text}!'). Do not read the raw numbers."
        
        if hasattr(self, 'brain') and self.brain.is_connected:
            # --- CHANGE 2: Prioritize tasks over warnings ---
            # If a task announcement is actively playing, ignore the warning completely.
            if self.brain.uninterruptible_active:
                print(f"[System Override] Warning suppressed to prioritize active task announcement.")
                return

            asyncio.run_coroutine_threadsafe(
                # Set uninterruptible=False so normal warnings don't block future tasks
                self.brain.inject_proactive_thought(instruction, uninterruptible=False), 
                self.brain_loop
            )

    def start_realtime_thread(self):
        asyncio.set_event_loop(self.brain_loop)
        try:
            self.brain_loop.create_task(self.proactive_engagement_loop())
            self.brain_loop.run_until_complete(self.brain.start_session())
        except Exception as e:
            print(f"Realtime loop ended: {e}")

    def get_camera_data(self):
        """Callback for the brain to grab the VR view AND the CV report."""
        head_frame = self.robot.get_frame()
        
        report = f"Sorting Status: {self.vision_tracker.latest_status}\n"
        report += f"Block Counts: {self.vision_tracker.block_counts}\n"
        
        return head_frame, report

    def start(self):
        self.safety_monitor.start()
        threading.Thread(target=self.start_realtime_thread, daemon=True).start()
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
            
        MENU_BUTTON_BITMASK = 1 << 1 
            
        if self.right_controller_id is not None:
            result, state = self.vrsystem.getControllerState(self.right_controller_id)
            if result and state.ulButtonPressed > 0:
                print(f"\r[VR Debug] Right Controller Raw State: {state.ulButtonPressed}       ", end="")
                if bool(state.ulButtonPressed & MENU_BUTTON_BITMASK): 
                    print() 
                    return True

        if self.left_controller_id is not None:
            result, state = self.vrsystem.getControllerState(self.left_controller_id)
            if result and state.ulButtonPressed > 0:
                print(f"\r[VR Debug] Left Controller Raw State: {state.ulButtonPressed}        ", end="")
                if bool(state.ulButtonPressed & MENU_BUTTON_BITMASK):
                    print() 
                    return True
                
        return False
    
    def toggle_chat_mode(self):
        """Toggles the conversation mode via physical button press."""
        self.conversation_mode = not self.conversation_mode
        
        if self.conversation_mode:
            print("\n[VR Controller] Conversation Resumed.")
            msg = "Resuming telemetry." if config.EXPERIMENT_CONDITION == "copilot" else "Resuming conversation."
            threading.Thread(target=self.speak_system, args=(msg,), daemon=True).start()
        else:
            print("\n[VR Controller] Conversation Paused.")
            msg = "Pausing telemetry." if config.EXPERIMENT_CONDITION == "copilot" else "Pausing conversation."
            threading.Thread(target=self.speak_system, args=(msg,), daemon=True).start()

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
                if self.task_timer_active and self.current_task in self.task_durations:
                    elapsed = int(time.time() - self.task_start_time)
                    remaining = max(0, self.task_durations[self.current_task] - elapsed)
                    mins, secs = divmod(remaining, 60)
                    time_str = f"Task {self.current_task}: {mins:02d}:{secs:02d}"
                    
                    # Draw a semi-transparent black background box so the text is always readable
                    overlay = head_frame.copy()
                    cv2.rectangle(overlay, (10, 10), (320, 60), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, head_frame, 0.4, 0, head_frame)
                    
                    # Draw the green timer text
                    cv2.putText(head_frame, time_str, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                
                # Show the final frame to the researcher
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
        self.robot.stop_audio()
        self.current_task = task_num
        self.task_start_time = time.time()
        self.task_timer_active = True
        
        self.milestones = {k: False for k in self.milestones}

        if task_num == 1:
            asyncio.run_coroutine_threadsafe(
                self.brain.inject_proactive_thought("We are starting Task 1. Deliver your exact Task 1 Start script now.", uninterruptible=True), 
                self.brain_loop
            )
        elif task_num == 2:
            self.robot.play_audio_for_duration(self.task_2_metronome_path, self.task_durations[2])
            asyncio.run_coroutine_threadsafe(
                self.brain.inject_proactive_thought("We are starting Task 2. Deliver your exact Task 2 Start script now.", uninterruptible=True), 
                self.brain_loop
            )
        elif task_num == 3:
            if config.EXPERIMENT_CONDITION == "copilot":
                prompt = "We are starting Task 3. Deliver your exact Task 3 Start script now. Await Operator data input."
            else:
                prompt = "We are starting Task 3. Introduce the social sorting task and ask the user to pick up a block so you can tell them where it goes."
            
            asyncio.run_coroutine_threadsafe(
                self.brain.inject_proactive_thought(prompt, uninterruptible=True), 
                self.brain_loop
            )

        elif task_num == 4:
            pass

    def stop_timers(self):
            """Callback to disable active task timers if the user finishes early."""
            print("[WoZ] Timers stopped via early completion tool.")
            self.task_timer_active = False
            self.robot.stop_audio()

    async def proactive_engagement_loop(self):
        """Runs in the background and periodically pushes Reachy to engage based on Task timers."""
        while self.running:
            await asyncio.sleep(1) 
            
            if not self.brain.is_connected or not self.task_timer_active:
                continue
                
            elapsed_seconds = time.time() - self.task_start_time
            
            # --- TASK 1 TIMERS (7 Minutes) ---
            if self.current_task == 1:
                if elapsed_seconds >= 150 and not self.milestones["t1_230"]:
                    self.milestones["t1_230"] = True
                    await self.brain.inject_proactive_thought("2 minutes and 30 seconds have passed. Deliver your exact '2:30 mark' script for Task 1.", uninterruptible=True)
                
                elif elapsed_seconds >= 300 and not self.milestones["t1_500"]:
                    self.milestones["t1_500"] = True
                    await self.brain.inject_proactive_thought("5 minutes have passed. Deliver your exact '5:00 mark' script for Task 1.", uninterruptible=True)
                
                elif elapsed_seconds >= 420 and not self.milestones["t1_700"]:
                    self.milestones["t1_700"] = True
                    self.task_timer_active = False
                    await self.brain.inject_proactive_thought("7 minutes have passed. Deliver your exact '7:00 mark' completion script for Task 1.", uninterruptible=True)

            # --- TASK 2 TIMERS (2 Minutes) ---
            elif self.current_task == 2:
                if elapsed_seconds >= 60 and not self.milestones["t2_100"]:
                    self.milestones["t2_100"] = True
                    await self.brain.inject_proactive_thought("1 minute has passed. Deliver your exact '1:00 mark' script for Task 2.", uninterruptible=True)
                
                elif elapsed_seconds >= 120 and not self.milestones["t2_200"]:
                    self.milestones["t2_200"] = True
                    self.task_timer_active = False 
                    self.robot.stop_audio()
                    await self.brain.inject_proactive_thought("2 minutes have passed. Deliver your exact '2:00 mark' completion script for Task 2.", uninterruptible=True)


if __name__ == '__main__':
    controller = ReachyControllerVR()
    controller.start()
