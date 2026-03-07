import time
import threading

# --- CONFIGURATION ---
LIMITS_CONFIG = {
    # RIGHT ARM
    'r_arm.shoulder.pitch': {'limit': -52.0, 'dir': 'less', 'msg': "right shoulder is raised way too high", 'buffer_warn': 10.0, 'buffer_caut': 20.0}, 
    'r_arm.shoulder.roll_out': {'limit': -70.0, 'dir': 'less', 'msg': "right arm is stretched all the way out", 'buffer_warn': 15.0, 'buffer_caut': 25.0}, 
    'r_arm.elbow.pitch':       {'limit': -125.0,'dir': 'less', 'msg': "right elbow is tucked all the way in", 'buffer_warn': 8.0, 'buffer_caut': 15.0}, 

    # LEFT ARM
    'l_arm.shoulder.pitch': {'limit': -52.0, 'dir': 'less', 'msg': "left shoulder is raised way too high", 'buffer_warn': 10.0, 'buffer_caut': 20.0}, 
    'l_arm.shoulder.roll_out': {'limit': 70.0,  'dir': 'greater', 'msg': "left arm is stretched all the way out", 'buffer_warn': 15.0, 'buffer_caut': 25.0}, 
    'l_arm.elbow.pitch':       {'limit': -128.0,'dir': 'less', 'msg': "left elbow is tucked all the way in", 'buffer_warn': 8.0, 'buffer_caut': 15.0}, 
}



# --- NEW: VELOCITY CONFIGURATION ---
SPEED_LIMIT_DEG_PER_SEC = 70  # You will need to calibrate this number!
VIOLATION_THRESHOLD = 3          # Must exceed speed limit 3 times in a row to trigger

def get_safety_status(current_val, limit_val, direction, buffer_warn, buffer_caut):
    is_danger = False
    if direction == 'less' and current_val < limit_val:
        is_danger = True
        dist = abs(limit_val - current_val)
    elif direction == 'greater' and current_val > limit_val:
        is_danger = True
        dist = abs(current_val - limit_val)
    else:
        dist = abs(current_val - limit_val)

    if is_danger:
        return 3, (0, 0, 255), "DANGER" 
    elif dist <= buffer_warn: 
        return 2, (0, 165, 255), "WARNING" 
    elif dist <= buffer_caut: 
        return 1, (0, 255, 255), "CAUTION" 
    else:
        return 0, (0, 255, 0), "SAFE"


class SafetyMonitor:
    def __init__(self, robot_interface, speak_callback):
        self.robot = robot_interface
        self.speak_callback = speak_callback
        self.running = False
        
        self.highest_threat_level = 0
        self.status_messages = []
        
        self.last_spoken_time = 0
        self.cooldown = 5.0  

        # --- NEW: VELOCITY TRACKING STATE ---
        self.last_joint_states = {} # Stores (position, timestamp) for each joint
        self.speed_violation_counts = {key: 0 for key in LIMITS_CONFIG.keys()}

    def start(self):
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        print("[Safety Monitor] Active and monitoring joints for position AND speed.")

    def stop(self):
        self.running = False

    def _monitor_loop(self):
        while self.running:
            current_time = time.time()
            
            try:
                joints = {
                    'r_arm.shoulder.pitch': self.robot.sdk.r_arm.shoulder.pitch.present_position,
                    'r_arm.shoulder.roll_out': self.robot.sdk.r_arm.shoulder.roll.present_position, 
                    'r_arm.elbow.pitch': self.robot.sdk.r_arm.elbow.pitch.present_position,
                    
                    'l_arm.shoulder.pitch': self.robot.sdk.l_arm.shoulder.pitch.present_position,
                    'l_arm.shoulder.roll_out': self.robot.sdk.l_arm.shoulder.roll.present_position,
                    'l_arm.elbow.pitch': self.robot.sdk.l_arm.elbow.pitch.present_position,
                }
            except Exception as e:
                time.sleep(0.5)
                continue

            highest = 0
            messages = []
            speed_warning_triggered = False
            fastest_joint_name = ""

            for key, config in LIMITS_CONFIG.items():
                if key not in joints:
                    continue
                    
                val = joints[key]
                
                # 1. POSITION CHECK (Your existing logic)
                level, color, _ = get_safety_status(val, config['limit'], config['dir'], config['buffer_warn'], config['buffer_caut'])
                if level > 0:
                    status_text = f"{config['msg']} ({val:.1f})"
                    messages.append((level, status_text, color))
                    if level > highest:
                        highest = level

                # 2. VELOCITY CHECK (New logic)
                if key in self.last_joint_states:
                    last_val, last_time = self.last_joint_states[key]
                    dt = current_time - last_time
                    
                    # Prevent division by zero if loop runs too fast
                    if dt > 0.01: 
                        speed = abs(val - last_val) / dt
                        
                        if speed > SPEED_LIMIT_DEG_PER_SEC:
                            self.speed_violation_counts[key] += 1
                            # print(f"[Debug] {key} speed: {speed:.1f} deg/sec")
                        else:
                            # Reset if they slow down
                            self.speed_violation_counts[key] = 0
                            
                        # If they exceed the speed limit multiple frames in a row
                        if self.speed_violation_counts[key] >= VIOLATION_THRESHOLD:
                            speed_warning_triggered = True
                            fastest_joint_name = key.split('.')[0] + " " + key.split('.')[1] # e.g., "r_arm shoulder"
                            self.speed_violation_counts[key] = 0 # Reset after triggering
                
                # Update history for next loop
                self.last_joint_states[key] = (val, current_time)

            messages.sort(key=lambda x: x[0], reverse=True)
            self.highest_threat_level = highest
            self.status_messages = messages

            # 3. TRIGGER AUDIO (Positional limits take priority)
            if highest >= 2:
                self._trigger_warning(messages[0][1], highest, warning_type="position")
            elif speed_warning_triggered:
                self._trigger_warning(fastest_joint_name, level=2, warning_type="speed")

            time.sleep(0.1) 

    def _trigger_warning(self, msg, level, warning_type="position"):
        current_time = time.time()
        if (current_time - self.last_spoken_time) > self.cooldown:
            self.last_spoken_time = current_time
            
            if warning_type == "speed":
                # Clean up the joint name for speaking (e.g., "r_arm shoulder" -> "right shoulder")
                friendly_name = msg.replace("r_arm", "right").replace("l_arm", "left").replace("_", " ")
                full_msg = f"Whoa, slow down a bit! You're moving my {friendly_name} too fast!"
            else:
                if level == 3: 
                    full_msg = f"Stop! I can't go any further. Please, pull my {msg} back!"
                elif level == 2: 
                    full_msg = f"Oof... I'm really stretching here. My {msg} is starting to feel a lot of pressure."
                else:
                    full_msg = f"Careful, my {msg} feels a bit tight."
            
            print(f"[Safety Monitor - Embodied] {full_msg}")
            threading.Thread(target=self.speak_callback, args=(full_msg,), daemon=True).start()