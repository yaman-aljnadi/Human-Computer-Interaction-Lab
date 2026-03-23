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
        The Tron "End of Line" Dance Routine.
        Strictly respects kinematic mirroring: 
        Right shoulder roll MUST be negative to clear the waist.
        Left shoulder roll MUST be positive to clear the waist.
        """
        # Joint Order: [sh_pitch, sh_roll, el_yaw, el_pitch, wr_roll, wr_pitch, wr_yaw]
        
        # Pose 1: "The Grid" (Arms raised safely, bent 90 deg, flared OUT away from waist)
        r_grid = [-20, -30, 0, -90, 90, 0, 0]
        l_grid = [-20, 30, 0, -90, -90, 0, 0]

        # Pose 2: "The DJ" (Right hand near ear flared out, left arm forward mixing)
        r_dj = [-40, -40, 0, -100, -90, -20, 45]
        l_dj = [-10, 20, 0, -45, 90, 0, -45]

        # Pose 3: "The Interface" (Arms low but pushed WIDE away from the base, wrist sweep)
        r_low = [10, -45, 0, -30, 150, 0, -45]
        l_low = [10, 45, 0, -30, -150, 0, 45]

        # Pose 4: "The Override" (Angular lock forward, wrists reset)
        r_lock = [-20, -25, 0, -90, 0, 0, 45]
        l_lock = [-20, 25, 0, -90, 0, 0, -45]

        moves = [
            (r_grid, l_grid),
            (r_dj, l_dj),
            (r_low, l_low),
            (r_lock, l_lock)
        ]

        # Beat tracker
        step = 0

        while self.is_dancing:
            r_pos, l_pos = moves[step % len(moves)]
            
            # Execute sharp robotic move (1.5 seconds keeps it safe but snappy)
            self.robot.r_arm.goto(r_pos, duration=2, wait=False)
            self.robot.l_arm.goto(l_pos, duration=2, wait=False)
            
            # Antennas pop to the beat
            ant_pos = 45 if step % 2 == 0 else -45
            self.robot.head.l_antenna.goto(ant_pos, duration=1, wait=False)
            self.robot.head.r_antenna.goto(ant_pos, duration=1, wait=False)
            
            # Head scans the crowd side to side
            head_yaw = 0.2 if step % 2 == 0 else -0.2
            self.robot.head.look_at(x=1.0, y=head_yaw, z=0.0, duration=1, wait=False)
            
            # Sleep dictates the tempo of the transitions
            time.sleep(2) 
            step += 1

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