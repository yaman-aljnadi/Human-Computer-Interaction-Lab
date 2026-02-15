import time
import cv2
import threading
import io
import pygame
from openai import OpenAI
from reachy2_sdk import ReachySDK
from reachy2_sdk.media.camera import CameraView

# --- CONFIGURATION ---
ROBOT_IP = '192.168.50.241'
OPENAI_API_KEY = "#"  


LIMITS_CONFIG = {
    # RIGHT ARM
    'r_arm.shoulder.pitch': {'limit': -80.0, 'dir': 'less', 'msg': "Right Arm Too High"}, # Measured -87
    'r_arm.shoulder.roll_out': {'limit': -70.0, 'dir': 'less', 'msg': "Right Arm Too Far Out"}, # Measured -75
    'r_arm.shoulder.roll_in':  {'limit': 20.0,  'dir': 'greater', 'msg': "Right Arm Hitting Stomach"}, # Measured 29
    'r_arm.elbow.pitch':       {'limit': -125.0,'dir': 'less', 'msg': "Right Elbow Max Flex"}, # Measured -132

    # LEFT ARM
    'l_arm.shoulder.pitch': {'limit': -85.0, 'dir': 'less', 'msg': "Left Arm Too High"}, # Measured -90
    'l_arm.shoulder.roll_out': {'limit': 70.0,  'dir': 'greater', 'msg': "Left Arm Too Far Out"}, # Measured 78
    'l_arm.shoulder.roll_in':  {'limit': -20.0, 'dir': 'less', 'msg': "Left Arm Hitting Stomach"}, # Measured -28
    'l_arm.elbow.pitch':       {'limit': -128.0,'dir': 'less', 'msg': "Left Elbow Max Flex"}, # Measured -133
}

BUFFER_WARN = 10.0   
BUFFER_CAUT = 20.0  

class VoiceAnnouncer:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key) if api_key != "YOUR_OPENAI_API_KEY_HERE" else None
        self.last_spoken_time = 0
        self.cooldown = 5.0  
        self.is_speaking = False
        
        pygame.mixer.init()

    def speak(self, text):
        if not self.client or self.is_speaking:
            return
        if (time.time() - self.last_spoken_time) < self.cooldown:
            return

        self.is_speaking = True
        self.last_spoken_time = time.time()
        
        threading.Thread(target=self._generate_and_play, args=(text,)).start()

    def _generate_and_play(self, text):
        try:
            print(f"Speaking: {text}")
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            byte_stream = io.BytesIO(response.content)
            pygame.mixer.music.load(byte_stream)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            print(f"TTS Error: {e}")
        finally:
            self.is_speaking = False

def get_safety_status(current_val, limit_val, direction):
    """
    Returns: (Level, Color_BGR, Message_Suffix)
    Level 0: Safe, 1: Caution, 2: Warning, 3: Danger
    """
    # Calculate distance to limit
    if direction == 'less':
        # Example: Limit -90, Current -95. Dist = (-95) - (-90) = -5 (Danger)
        dist = current_val - limit_val
    else: # direction == 'greater'
        # Example: Limit 20, Current 25. Dist = 25 - 20 = 5 (Danger)
        dist = current_val - limit_val 
    

    
    is_danger = False
    if direction == 'less' and current_val < limit_val:
        is_danger = True
        dist = abs(limit_val - current_val) # How far past limit
    elif direction == 'greater' and current_val > limit_val:
        is_danger = True
        dist = abs(current_val - limit_val)
    else:
        dist = abs(current_val - limit_val)

    if is_danger:
        return 3, (0, 0, 255), "DANGER" # Red
    elif dist <= BUFFER_WARN: # Within 10 degrees
        return 2, (0, 165, 255), "WARNING" # Orange
    elif dist <= BUFFER_CAUT: # Within 20 degrees
        return 1, (0, 255, 255), "CAUTION" # Yellow
    else:
        return 0, (0, 255, 0), "SAFE" # Green

def main():
    print(f"Connecting to Reachy at {ROBOT_IP}...")
    reachy = ReachySDK(host=ROBOT_IP)
    
    reachy.turn_off()
    
    announcer = VoiceAnnouncer(OPENAI_API_KEY)

    if reachy.cameras.teleop is None:
        print("Error: No camera detected.")
        return
    
    print("Starting Video Feed... Press 'q' to quit.")

    while True:
        joints = {
            'r_arm.shoulder.pitch': reachy.r_arm.shoulder.pitch.present_position,
            'r_arm.shoulder.roll_out': reachy.r_arm.shoulder.roll.present_position, # Same joint, checked twice
            'r_arm.shoulder.roll_in': reachy.r_arm.shoulder.roll.present_position,
            'r_arm.elbow.pitch': reachy.r_arm.elbow.pitch.present_position,
            
            'l_arm.shoulder.pitch': reachy.l_arm.shoulder.pitch.present_position,
            'l_arm.shoulder.roll_out': reachy.l_arm.shoulder.roll.present_position,
            'l_arm.shoulder.roll_in': reachy.l_arm.shoulder.roll.present_position,
            'l_arm.elbow.pitch': reachy.l_arm.elbow.pitch.present_position,
        }

        highest_threat_level = 0
        status_messages = []

        for key, config in LIMITS_CONFIG.items():
            val = joints[key]
            level, color, _ = get_safety_status(val, config['limit'], config['dir'])
            
            if level > 0:
                # Add to display list
                status_text = f"{config['msg']} ({val:.1f})"
                status_messages.append((level, status_text, color))
                
                if level > highest_threat_level:
                    highest_threat_level = level

        # Sort messages so DANGER is at top
        status_messages.sort(key=lambda x: x[0], reverse=True)

        if highest_threat_level == 3:
            # Pick the top danger message to speak
            top_msg = status_messages[0][1] # Get text
            announcer.speak(f"Danger. {top_msg}")
        elif highest_threat_level == 2:
            top_msg = status_messages[0][1]
            announcer.speak(f"Warning. {top_msg}")

        result = reachy.cameras.teleop.get_frame(CameraView.RIGHT)
        if result is not None:
            frame, _ = result
            
            y_offset = 30
            
            if highest_threat_level == 0:
                cv2.putText(frame, "STATUS: SAFE", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:
                header_color = (0, 0, 255) if highest_threat_level == 3 else (0, 165, 255)
                header_text = "DANGER DETECTED" if highest_threat_level == 3 else "WARNING"
                cv2.putText(frame, f"STATUS: {header_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, header_color, 2)

            y_offset = 70
            for level, text, color in status_messages:
                cv2.putText(frame, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                y_offset += 30

            # Add live joint values (Optional, for debugging)
            # cv2.putText(frame, f"R-Roll: {joints['r_arm.shoulder.roll_in']:.1f}", (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

            cv2.imshow("Reachy Safety HUD", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    # reachy.turn_on() # Optional: Stiffen arms on exit

if __name__ == "__main__":
    main()