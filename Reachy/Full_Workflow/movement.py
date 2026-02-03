import time
import threading
import random
import numpy as np

from reachy2_sdk.utils.utils import get_pose_matrix 

class BodyLanguage:
    def __init__(self, robot):
        self.robot = robot
        self.is_active = False
        self.is_dancing = False 
        self._thread = None
        self._dance_thread = None

    # SPEAKING BEHAVIOR
    def start_speaking_behavior(self):
        if self.is_active: return 
        self.is_active = True
        self._thread = threading.Thread(target=self._behavior_loop)
        self._thread.start()

    def stop_speaking_behavior(self):
        self.is_active = False
        if self._thread: self._thread.join()
        self.neutral_stance_head()

    # DANCING BEHAVIOR 
    def start_dancing_behavior(self):
        """Starts the robot dance thread."""
        if self.is_dancing: return
        
        print("[Body] Starting The Robot dance...")
        # Turn on arms stiff
        self.robot.r_arm.turn_on()
        self.robot.l_arm.turn_on()
        
        self.is_dancing = True
        self._dance_thread = threading.Thread(target=self._dance_loop)
        self._dance_thread.start()

    def stop_dancing_behavior(self):
        """Stops dancing and relaxes arms."""
        self.is_dancing = False
        if self._dance_thread:
            self._dance_thread.join()
        
        print("[Body] Dance complete. Relaxing arms.")
        # Turn off arms smoothly so they don't crash down
        self.robot.r_arm.turn_off_smoothly()
        self.robot.l_arm.turn_off_smoothly()
        self.neutral_stance_head()

    def neutral_stance_head(self):
        """Resets head only."""
        self.robot.head.l_antenna.goto(0, duration=2.0, wait=False)
        self.robot.head.r_antenna.goto(0, duration=2.0, wait=False)
        self.robot.head.look_at(x=1.0, y=0.0, z=0.0, duration=2.0, wait=False)

    def _dance_loop(self):
            """
            The Robot Dance Routine using JOINT COORDINATES.
            Format: [shoulder_pitch, shoulder_roll, elbow_yaw, elbow_pitch, wrist_roll, wrist_pitch, wrist_yaw]
            """
            # This is so confusing and I hate it 
            # 1. "The Box" (Elbows bent 90 degrees)
            # Right arm: elbow bent -90
            right_box = [0, 0, 0, -90, 0, 0, 0] 
            # Left arm: elbow bent -90
            left_box  = [0, 0, 0, -90, 0, 0, 0]

            # 2. "Sky Reach" (Right Up, Left Down)
            # Right: Shoulder pitch -60 (up)
            right_up = [-60, 0, 0, -45, 0, 0, 0]
            # Left: Shoulder pitch 40 (down)
            left_down = [40, 0, 0, -45, 0, 0, 0]

            # 3. "Swap" (Right Down, Left Up)
            right_down = [40, 0, 0, -45, 0, 0, 0]
            left_up    = [-60, 0, 0, -45, 0, 0, 0]

            moves = [
                (right_box, left_box),
                (right_up, left_down),
                (right_down, left_up),
                (right_box, left_box)
            ]

            while self.is_dancing:
                for r_pos, l_pos in moves:
                    if not self.is_dancing: break
                    
                    # Execute move using lists of angles
                    # !!! NEVER USE A DURATION LESS THAN 1 SEC OTHER WISE THE ARMS CRASH WILL CRASH OR PUNCH YOU IN THE FACE !!!
                    self.robot.r_arm.goto(r_pos, duration=3, wait=False)
                    self.robot.l_arm.goto(l_pos, duration=3, wait=False)
                    
                    # Head bob
                    self.robot.head.look_at(x=1.0, y=0.0, z=random.choice([-0.1, 0.1]), duration=1, wait=False)
                    
                    time.sleep(1) # Wait for the beat

    # Speaking Loop
    def _behavior_loop(self):
        while self.is_active:
            l_pos = random.randint(30, 80)
            r_pos = random.randint(30, 80)
            head_pitch = random.choice([-0.05, 0, 0.05])
            head_yaw = random.choice([-0.1, 0, 0.1])

            self.robot.head.l_antenna.goto(l_pos, duration=1, wait=False)
            self.robot.head.r_antenna.goto(r_pos, duration=1, wait=False)
            self.robot.head.look_at(x=1.0, y=head_yaw, z=head_pitch, duration=1.0, wait=False)
            time.sleep(1.2)