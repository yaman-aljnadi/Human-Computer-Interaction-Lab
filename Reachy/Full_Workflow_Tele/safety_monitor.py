import time
import threading

# --- CONFIGURATION ---
LIMITS_CONFIG = {
    # RIGHT ARM
    'r_arm.shoulder.pitch': {'limit': -80.0, 'dir': 'less', 'msg': "Right Arm Too High"}, 
    'r_arm.shoulder.roll_out': {'limit': -70.0, 'dir': 'less', 'msg': "Right Arm Too Far Out"}, 
    # 'r_arm.shoulder.roll_in':  {'limit': 20.0,  'dir': 'greater', 'msg': "Right Arm Hitting Stomach"}, 
    'r_arm.elbow.pitch':       {'limit': -125.0,'dir': 'less', 'msg': "Right Elbow Max Flex"}, 

    # LEFT ARM
    'l_arm.shoulder.pitch': {'limit': -85.0, 'dir': 'less', 'msg': "Left Arm Too High"}, 
    'l_arm.shoulder.roll_out': {'limit': 70.0,  'dir': 'greater', 'msg': "Left Arm Too Far Out"}, 
    # 'l_arm.shoulder.roll_in':  {'limit': -20.0, 'dir': 'less', 'msg': "Left Arm Hitting Stomach"}, 
    'l_arm.elbow.pitch':       {'limit': -128.0,'dir': 'less', 'msg': "Left Elbow Max Flex"}, 
}

BUFFER_WARN = 10.0   
BUFFER_CAUT = 20.0  

def get_safety_status(current_val, limit_val, direction):
    """
    Returns: (Level, Color_BGR, Message_Suffix)
    Level 0: Safe, 1: Caution, 2: Warning, 3: Danger
    """
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
    elif dist <= BUFFER_WARN: 
        return 2, (0, 165, 255), "WARNING" 
    elif dist <= BUFFER_CAUT: 
        return 1, (0, 255, 255), "CAUTION" 
    else:
        return 0, (0, 255, 0), "SAFE" 

class SafetyMonitor:
    def __init__(self, robot_interface, speak_callback):
        self.robot = robot_interface
        self.speak_callback = speak_callback
        self.running = False
        
        # State for the VR HUD to read
        self.highest_threat_level = 0
        self.status_messages = []
        
        # Audio cooldown
        self.last_spoken_time = 0
        self.cooldown = 5.0  

    def start(self):
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        print("[Safety Monitor] Active and monitoring joints.")

    def stop(self):
        self.running = False

    def _monitor_loop(self):
        while self.running:
            # Safely grab the joint positions from the SDK
            try:
                joints = {
                    'r_arm.shoulder.pitch': self.robot.sdk.r_arm.shoulder.pitch.present_position,
                    'r_arm.shoulder.roll_out': self.robot.sdk.r_arm.shoulder.roll.present_position, 
                    'r_arm.shoulder.roll_in': self.robot.sdk.r_arm.shoulder.roll.present_position,
                    'r_arm.elbow.pitch': self.robot.sdk.r_arm.elbow.pitch.present_position,
                    
                    'l_arm.shoulder.pitch': self.robot.sdk.l_arm.shoulder.pitch.present_position,
                    'l_arm.shoulder.roll_out': self.robot.sdk.l_arm.shoulder.roll.present_position,
                    'l_arm.shoulder.roll_in': self.robot.sdk.l_arm.shoulder.roll.present_position,
                    'l_arm.elbow.pitch': self.robot.sdk.l_arm.elbow.pitch.present_position,
                }
            except Exception as e:
                # SDK might not be fully initialized yet
                time.sleep(0.5)
                continue

            highest = 0
            messages = []

            for key, config in LIMITS_CONFIG.items():
                val = joints[key]
                level, color, _ = get_safety_status(val, config['limit'], config['dir'])
                
                if level > 0:
                    status_text = f"{config['msg']} ({val:.1f})"
                    messages.append((level, status_text, color))
                    if level > highest:
                        highest = level

            messages.sort(key=lambda x: x[0], reverse=True)
            
            # Update public state for main_vr.py to draw on the HUD
            self.highest_threat_level = highest
            self.status_messages = messages

            # Trigger Audio Warning
            if highest >= 2:
                self._trigger_warning(messages[0][1], highest)

            time.sleep(0.1) # Check 10 times a second

    def _trigger_warning(self, msg, level):
        current_time = time.time()
        if (current_time - self.last_spoken_time) > self.cooldown:
            self.last_spoken_time = current_time
            prefix = "Danger." if level == 3 else "Warning."
            full_msg = f"{prefix} {msg}"
            
            print(f"[Safety Monitor] {full_msg}")
            # Wrap the speak callback in a thread so it doesn't pause the monitoring loop
            threading.Thread(target=self.speak_callback, args=(full_msg,), daemon=True).start()