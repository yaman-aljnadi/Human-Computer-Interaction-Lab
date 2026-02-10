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

    def start_listening_behavior(self):
        self.stop_speaking_behavior() 

        self.robot.head.l_antenna.goto(0.0, duration=0.5, wait=False)
        self.robot.head.r_antenna.goto(0.0, duration=0.5, wait=False)

    # SPEAKING BEHAVIOR
    def start_speaking_behavior(self, force_head_still=False):
        if self.is_active: return 
        
        self.is_active = True
        self.force_head_still = force_head_still # Store the flag
        
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

    def perform_wave(self):
        """
        Executes the startup wave animation.
        """
        print("[Body] Starting greeting wave...")
        self.robot.r_arm.turn_on()

        neutral_pos = [0, 0, 0, 0, 0, 0, 0]
        
        # Ready Position (Arm up)
        # dict: s.p: -30, s.r: 10, e.y: -10, e.p: -95, w.r: 0, w.p: -40, w.y: 0
        # Upper arm raised, elbow bent, palm facing forward (This is Hell to figure out and I hate it)
        wave_ready_pos = [-30, 10, -10, -95, 0, -40, 0]

        # Wave Left (Wrist roll -20)
        wave_left = [-30, 10, -10, -95, -20, -40, 0]

        # Wave Right (Wrist roll 20)
        wave_right = [-30, 10, -10, -95, 20, -40, 0]

        # --- EXECUTION ---
        # self.robot.r_arm.goto(neutral_pos, duration=3, wait=True)

        # Move to Ready
        self.robot.r_arm.goto(wave_ready_pos, duration=3, wait=True)

        # Waving Motion (Loop twice)
        for _ in range(2):
            self.robot.r_arm.goto(wave_left, duration=0.5, wait=True)
            self.robot.r_arm.goto(wave_right, duration=0.5, wait=True)

        # Return to Neutral
        self.robot.r_arm.goto(neutral_pos, duration=2, wait=True)
        
        # Relax
        self.robot.r_arm.turn_off_smoothly()
        print("[Body] Wave complete.")

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

            # 2. Always move Antennas (They don't conflict with tracking)
            self.robot.head.l_antenna.goto(l_pos, duration=1, wait=False)
            self.robot.head.r_antenna.goto(r_pos, duration=1, wait=False)

            # 3. ONLY move head if tracking is OFF
            if not self.force_head_still:
                self.robot.head.look_at(x=1.0, y=head_yaw, z=head_pitch, duration=1.0, wait=False)
            
            time.sleep(1.2)