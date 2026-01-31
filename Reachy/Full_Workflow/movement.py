import time
import threading
import random

class BodyLanguage:
    def __init__(self, robot):
        self.robot = robot
        self.is_active = False
        self._thread = None

    def start_speaking_behavior(self):
        """Starts the background movement thread."""
        if self.is_active: 
            return 
            
        self.is_active = True
        self._thread = threading.Thread(target=self._behavior_loop)
        self._thread.start()

    def stop_speaking_behavior(self):
        """Signals the thread to stop and waits for it to finish."""
        self.is_active = False
        if self._thread:
            self._thread.join()
        
        # Return to neutral after speaking
        self.neutral_stance()

    def neutral_stance(self):
        """Gently returns antennas to zero and head to center."""
        print("[Body] Returning to rest...")
        # Reset Antennas
        self.robot.head.l_antenna.goto(0, duration=1.0, wait=False)
        self.robot.head.r_antenna.goto(0, duration=1.0, wait=False)
        
        # Reset Head Position (Look forward)
        self.robot.head.look_at(x=1.0, y=0.0, z=0.0, duration=1.0, wait=False)

    def _behavior_loop(self):
        """The loop that runs WHILE Reachy is speaking."""
        while self.is_active:
            # 1. Random Antenna Emotion
            # We pick a random angle between 30 and 80 degrees for "excitement"
            l_pos = random.randint(30, 80)
            r_pos = random.randint(30, 80)
            
            # 2. Subtle Head Bob (Nodding/Emphasis)
            # We keep X fixed (1.0 meter forward)
            # We vary Z slightly (Up/Down) to mimic head nodding
            # We vary Y slightly (Left/Right) for natural drift
            head_pitch = random.choice([-0.05, 0, 0.05]) # Slight Up/Down
            head_yaw = random.choice([-0.1, 0, 0.1])     # Slight Left/Right

            # Execute movements
            self.robot.head.l_antenna.goto(l_pos, duration=0.8, wait=False)
            self.robot.head.r_antenna.goto(r_pos, duration=0.8, wait=False)
            
            self.robot.head.look_at(
                x=1.0, 
                y=head_yaw, 
                z=head_pitch, 
                duration=1.0, 
                wait=False
            )
            
            # Wait before the next movement so it doesn't look jittery
            time.sleep(1.2)