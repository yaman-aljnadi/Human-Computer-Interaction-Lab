import time
import threading
from evdev import InputDevice, categorize, ecodes, list_devices
from reachy2_sdk import ReachySDK

# --- Configuration ---
REACHY_IP = '127.0.0.1' # Running locally on Reachy
MAX_LINEAR_SPEED = 0.5  # m/s
MAX_ANGULAR_SPEED = 30.0 # deg/s
DEADZONE = 5000 # Ignore tiny stick movements (stick drift)

# --- Global Speed Variables ---
current_vx = 0.0
current_vy = 0.0
current_vtheta = 0.0

# --- 1. Connect to Reachy ---
print("Connecting to Reachy...")
reachy = ReachySDK(host=REACHY_IP)
reachy.mobile_base.turn_on()
print("Connected! Mobile base ready.")

# --- 2. Find the Xbox Controller ---
def get_controller():
    devices = [InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        # Look for typical Xbox controller names
        if "Xbox" in device.name or "Wireless Controller" in device.name:
            print(f"Found controller: {device.name}")
            return device
    return None

gamepad = get_controller()
if not gamepad:
    print("No controller found. Make sure it is paired and turned on!")
    exit()

# --- 3. Continuous Speed Command Thread ---
# This fulfills the requirement to send commands every 100-150ms 
def send_speed_loop():
    while True:
        reachy.mobile_base.set_goal_speed(vx=current_vx, vy=current_vy, vtheta=current_vtheta)
        reachy.mobile_base.send_speed_command()
        time.sleep(0.1) # Send every 100ms

# Start the background thread
threading.Thread(target=send_speed_loop, daemon=True).start()

# --- 4. Main Event Loop (Reading Sticks) ---
print("Listening for input... Press Ctrl+C to stop.")

def map_axis(value, max_speed):
    # Xbox axes go from -32768 to 32767
    if abs(value) < DEADZONE:
        return 0.0
    # Normalize to -1.0 to 1.0, then multiply by max speed
    normalized = value / 32768.0
    return normalized * max_speed

try:
    for event in gamepad.read_loop():
        if event.type == ecodes.EV_ABS:
            # Left Stick Y-Axis (Forward/Backward)
            if event.code == ecodes.ABS_Y:
                # Invert so pushing up (negative Y) moves forward (positive X)
                current_vx = map_axis(-event.value, MAX_LINEAR_SPEED)
            
            # Left Stick X-Axis (Left/Right Strafe)
            elif event.code == ecodes.ABS_X:
                # Left is positive Y in Reachy's frame, so invert joystick X
                current_vy = map_axis(-event.value, MAX_LINEAR_SPEED)
            
            # Right Stick X-Axis (Rotation)
            elif event.code == ecodes.ABS_RX:
                # Left is positive Theta, so invert joystick X
                current_vtheta = map_axis(-event.value, MAX_ANGULAR_SPEED)

except KeyboardInterrupt:
    print("Stopping...")
    reachy.mobile_base.set_goal_speed(vx=0.0, vy=0.0, vtheta=0.0)
    reachy.mobile_base.send_speed_command()