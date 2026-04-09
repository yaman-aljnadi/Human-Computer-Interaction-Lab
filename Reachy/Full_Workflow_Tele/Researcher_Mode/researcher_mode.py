import time
import threading
import os
import cv2
import pygame
import numpy as np
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView

TASK_DURATIONS = {
    1: 420,  # Task 1: 7 minutes
    2: 120,  # Task 2: 2 minutes
    3: 300,  # Task 3: Change Later
    4: 300   # Task 4: Change Later
}

# Re-use your exact safety limits
LIMITS_CONFIG = {
    'r_arm.shoulder.pitch': {'limit': -62.0, 'dir': 'less', 'buffer_warn': 10.0}, 
    'r_arm.shoulder.roll_out': {'limit': -70.0, 'dir': 'less', 'buffer_warn': 15.0}, 
    'r_arm.elbow.pitch': {'limit': -125.0,'dir': 'less', 'buffer_warn': 8.0}, 
    'l_arm.shoulder.pitch': {'limit': -62.0, 'dir': 'less', 'buffer_warn': 10.0}, 
    'l_arm.shoulder.roll_out': {'limit': 70.0, 'dir': 'greater', 'buffer_warn': 15.0}, 
    'l_arm.elbow.pitch': {'limit': -128.0,'dir': 'less', 'buffer_warn': 8.0}, 
}

class ResearcherMode:
    def __init__(self):
        print(">>> STARTING RESEARCHER BASELINE MODE (No AI) <<<")
        
        pygame.mixer.init()
        base_dir = os.path.dirname(__file__)
        try:
            self.sound_timer = pygame.mixer.Sound(os.path.join(base_dir, "Timer.mp3"))
            self.sound_warning = pygame.mixer.Sound(os.path.join(base_dir, "car-chime-warning.mp3"))
            self.metronome_path = os.path.join(base_dir, "60_Metronome.mp3")
            print("[Audio] Loaded Timer.mp3, Warning.mp3, and 60_Metronome.mp3 successfully.")
        except Exception as e:
            print(f"[Audio Error] Could not load sound files: {e}. Make sure they are in the same folder.")
            self.sound_timer, self.sound_warning, self.metronome_path = None, None, None

        print(f"[Network] Connecting to Reachy at 192.68.50.242 ...")
        self.sdk = ReachySDK(host="192.168.50.242")
        if not self.sdk.is_connected():
            raise ConnectionError("Could not connect to Reachy 2.")
        print("[Network] Connected successfully.")

        self.running = True
        self.current_task = 0
        self.task_start_time = 0
        self.task_active = False
        
        # Matching the LLM workflow
        self.milestones = {
            "t1_230": False, "t1_500": False, "t1_700": False,
            "t2_100": False, "t2_200": False
        }
        
        self.last_warning_time = 0
        self.warning_cooldown = 30.0  

    def play_sound(self, sound_obj):
        """Plays a sound on an available audio channel."""
        if sound_obj:
            sound_obj.play()

    def start_task(self, task_num):
        """Starts a task and its specific timer."""
        self.stop_metronome()
        self.current_task = task_num
        self.task_start_time = time.time()
        self.task_active = True
        
        # Reset milestones
        self.milestones = {k: False for k in self.milestones}
        
        duration_mins = TASK_DURATIONS[task_num] / 60
        print(f"\n[Experiment] Started Task {task_num}. Timer active.")
        self.play_sound(self.sound_timer) # Play sound on initial start
        if task_num == 2:
            self.start_metronome()

    def stop_task(self):
        """Manually ends the current task."""
        if self.task_active:
            print(f"\n[Experiment] Task {self.current_task} manually stopped.")
            self.task_active = False
            self.current_task = 0
            self.stop_metronome()

    def start_metronome(self):
        """Starts the Task 2 metronome loop."""
        if self.metronome_path:
            try:
                pygame.mixer.music.load(self.metronome_path)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"[Audio Error] Could not play metronome: {e}")

    def stop_metronome(self):
        """Stops the Task 2 metronome if it is playing."""
        pygame.mixer.music.stop()
        try:
            pygame.mixer.music.unload()
        except AttributeError:
            pass

    def timer_loop(self):
        """Background thread to monitor active task timers and trigger milestones."""
        while self.running:
            if self.task_active:
                elapsed = time.time() - self.task_start_time
                
                if self.current_task == 1:
                    if elapsed >= 150 and not self.milestones["t1_230"]:
                        self.milestones["t1_230"] = True
                        # Removed intermediate beep here
                        print("\n[Timer] Task 1: 2:30 milestone reached!")
                    
                    elif elapsed >= 300 and not self.milestones["t1_500"]:
                        self.milestones["t1_500"] = True
                        # Removed intermediate beep here
                        print("\n[Timer] Task 1: 5:00 milestone reached!")
                    
                    elif elapsed >= 420 and not self.milestones["t1_700"]:
                        self.milestones["t1_700"] = True
                        self.play_sound(self.sound_timer) # Kept completion beep
                        print("\n[Timer] Task 1: 7:00 completion reached!")
                        self.task_active = False
                        self.current_task = 0

                elif self.current_task == 2:
                    if elapsed >= 60 and not self.milestones["t2_100"]:
                        self.milestones["t2_100"] = True
                        # Removed intermediate beep here
                        print("\n[Timer] Task 2: 1:00 milestone reached!")
                    
                    elif elapsed >= 120 and not self.milestones["t2_200"]:
                        self.milestones["t2_200"] = True
                        self.play_sound(self.sound_timer) # Kept completion beep
                        print("\n[Timer] Task 2: 2:00 completion reached!")
                        self.task_active = False
                        self.current_task = 0
                        self.stop_metronome()
                        
                elif self.current_task in [3, 4]:
                    target_duration = TASK_DURATIONS[self.current_task]
                    if elapsed >= target_duration:
                        print(f"\n[Experiment] TIME'S UP for Task {self.current_task}!")
                        self.play_sound(self.sound_timer) # Kept completion beep
                        self.task_active = False
                        self.current_task = 0
                        self.stop_metronome()
                        
            time.sleep(0.5)

    def safety_loop(self):
        """Background thread to monitor joint limits and trigger warnings."""
        while self.running:
            try:
                joints = {
                    'r_arm.shoulder.pitch': self.sdk.r_arm.shoulder.pitch.present_position,
                    'r_arm.shoulder.roll_out': self.sdk.r_arm.shoulder.roll.present_position, 
                    'r_arm.elbow.pitch': self.sdk.r_arm.elbow.pitch.present_position,
                    'l_arm.shoulder.pitch': self.sdk.l_arm.shoulder.pitch.present_position,
                    'l_arm.shoulder.roll_out': self.sdk.l_arm.shoulder.roll.present_position,
                    'l_arm.elbow.pitch': self.sdk.l_arm.elbow.pitch.present_position,
                }
            except Exception:
                time.sleep(0.5)
                continue

            warning_triggered = False

            for key, limit_cfg in LIMITS_CONFIG.items():
                if key not in joints: continue
                val = joints[key]
                limit = limit_cfg['limit']
                buffer = limit_cfg['buffer_warn']
                
                if limit_cfg['dir'] == 'less':
                    if val < (limit + buffer): warning_triggered = True
                elif limit_cfg['dir'] == 'greater':
                    if val > (limit - buffer): warning_triggered = True

            current_time = time.time()
            if warning_triggered and (current_time - self.last_warning_time) > self.warning_cooldown:
                print(f"[Safety] Arm limit approached! Triggering warning sound. (Next warning available in {self.warning_cooldown}s)")
                self.play_sound(self.sound_warning)
                self.last_warning_time = current_time

            time.sleep(0.1)

    def display_loop(self):
        """Main loop for camera feed and keyboard inputs."""
        print("\n--- CONTROLS ---")
        print("Press '1', '2', '3', '4' to start tasks.")
        print("Press 'x' to stop the current task timer.")
        print("Press 'q' to quit.")
        print("----------------\n")
        
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank_frame, "Reachy Camera Feed", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        while self.running:
            if self.sdk.cameras.teleop is not None:
                result = self.sdk.cameras.teleop.get_frame(CameraView.LEFT)
                frame = result[0] if result else blank_frame
            else:
                frame = blank_frame

            if self.task_active:
                elapsed = int(time.time() - self.task_start_time)
                remaining = max(0, TASK_DURATIONS[self.current_task] - elapsed)
                mins, secs = divmod(remaining, 60)
                time_str = f"Task {self.current_task}: {mins:02d}:{secs:02d}"
                cv2.putText(frame, time_str, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

            cv2.imshow("Researcher Dashboard", frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                self.running = False
            elif key == ord('x'):
                self.stop_task()
            elif key in [ord('1'), ord('2'), ord('3'), ord('4')]:
                task_num = int(chr(key))
                self.start_task(task_num)

        cv2.destroyAllWindows()
        self.sdk.disconnect()
        print("Disconnected and exited.")

if __name__ == '__main__':
    mode = ResearcherMode()
    threading.Thread(target=mode.timer_loop, daemon=True).start()
    threading.Thread(target=mode.safety_loop, daemon=True).start()
    mode.display_loop()
