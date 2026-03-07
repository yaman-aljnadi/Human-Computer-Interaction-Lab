import time
import threading
import config  # <-- NEW: Import config to check condition

# --- CONFIGURATION ---
LIMITS_CONFIG = {
    # RIGHT ARM
    'r_arm.shoulder.pitch': {'limit': -52.0, 'dir': 'less', 'msg': "right shoulder is raised way too high", 'sys_name': "right shoulder pitch", 'buffer_warn': 10.0, 'buffer_caut': 20.0}, 
    'r_arm.shoulder.roll_out': {'limit': -70.0, 'dir': 'less', 'msg': "right arm is stretched all the way out", 'sys_name': "right shoulder roll", 'buffer_warn': 15.0, 'buffer_caut': 25.0}, 
    'r_arm.elbow.pitch':       {'limit': -125.0,'dir': 'less', 'msg': "right elbow is tucked all the way in", 'sys_name': "right elbow pitch", 'buffer_warn': 8.0, 'buffer_caut': 15.0}, 

    # LEFT ARM
    'l_arm.shoulder.pitch': {'limit': -52.0, 'dir': 'less', 'msg': "left shoulder is raised way too high", 'sys_name': "left shoulder pitch", 'buffer_warn': 10.0, 'buffer_caut': 20.0}, 
    'l_arm.shoulder.roll_out': {'limit': 70.0,  'dir': 'greater', 'msg': "left arm is stretched all the way out", 'sys_name': "left shoulder roll", 'buffer_warn': 15.0, 'buffer_caut': 25.0}, 
    'l_arm.elbow.pitch':       {'limit': -128.0,'dir': 'less', 'msg': "left elbow is tucked all the way in", 'sys_name': "left elbow pitch", 'buffer_warn': 8.0, 'buffer_caut': 15.0}, 
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

            # UPDATED: Renamed local 'config' to 'limit_cfg' to avoid shadowing imported module
            for key, limit_cfg in LIMITS_CONFIG.items():
                if key not in joints:
                    continue
                    
                val = joints[key]
                
                # 1. POSITION CHECK
                level, color, _ = get_safety_status(val, limit_cfg['limit'], limit_cfg['dir'], limit_cfg['buffer_warn'], limit_cfg['buffer_caut'])
                if level > 0:
                    status_text = f"{limit_cfg['msg']} ({val:.1f})"
                    # Store the key so we can fetch 'sys_name' later for the Co-Pilot
                    messages.append((level, status_text, color, key))
                    if level > highest:
                        highest = level

                # 2. VELOCITY CHECK
                if key in self.last_joint_states:
                    last_val, last_time = self.last_joint_states[key]
                    dt = current_time - last_time
                    
                    if dt > 0.01: 
                        speed = abs(val - last_val) / dt
                        
                        if speed > SPEED_LIMIT_DEG_PER_SEC:
                            self.speed_violation_counts[key] += 1
                        else:
                            self.speed_violation_counts[key] = 0
                            
                        if self.speed_violation_counts[key] >= VIOLATION_THRESHOLD:
                            speed_warning_triggered = True
                            fastest_joint_name = key.split('.')[0] + " " + key.split('.')[1]
                            self.speed_violation_counts[key] = 0 
                
                self.last_joint_states[key] = (val, current_time)

            messages.sort(key=lambda x: x[0], reverse=True)
            self.highest_threat_level = highest
            self.status_messages = messages

            # 3. TRIGGER AUDIO (Positional limits take priority)
            if highest >= 2:
                self._trigger_warning(messages[0][1], highest, warning_type="position", joint_key=messages[0][3])
            elif speed_warning_triggered:
                self._trigger_warning(fastest_joint_name, level=2, warning_type="speed")

            time.sleep(0.1) 

    def _trigger_warning(self, msg, level, warning_type="position", joint_key=None):
        current_time = time.time()
        if (current_time - self.last_spoken_time) > self.cooldown:
            self.last_spoken_time = current_time
            
            # --- NEW: Check condition and route speech accordingly ---
            if config.EXPERIMENT_CONDITION == "copilot":
                if warning_type == "speed":
                    friendly_name = msg.replace("r_arm", "right").replace("l_arm", "left").replace("_", " ")
                    full_msg = f"Telemetry Alert: Velocity limit exceeded on {friendly_name}. Reduce Operator input speed immediately."
                else:
                    sys_name = LIMITS_CONFIG[joint_key]['sys_name'] if joint_key else "hardware"
                    if level == 3: 
                        full_msg = f"Critical Alert: {sys_name} limit reached "
                    elif level == 2: 
                        full_msg = f"Warning: {sys_name} is approaching maximum mechanical tolerance."
                    else:
                        full_msg = f"Notice: {sys_name} telemetry indicates caution zone."
                        
            else: # Embodied condition
                if warning_type == "speed":
                    friendly_name = msg.replace("r_arm", "right").replace("l_arm", "left").replace("_", " ")
                    full_msg = f"Whoa, slow down a bit! You're moving my {friendly_name} too fast!"
                else:
                    clean_msg = msg.split(' (')[0] if ' (' in msg else msg
                    if level == 3: 
                        full_msg = f"Stop! I can't go any further. Please, pull my {clean_msg} back!"
                    elif level == 2: 
                        full_msg = f"Oof... I'm really stretching here. My {clean_msg} is starting to feel a lot of pressure."
                    else:
                        full_msg = f"Careful, my {clean_msg} feels a bit tight."
            
            print(f"[Safety Monitor - {config.EXPERIMENT_CONDITION.capitalize()}] {full_msg}")
            threading.Thread(target=self.speak_callback, args=(full_msg,), daemon=True).start()