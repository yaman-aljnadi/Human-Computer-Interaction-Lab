import time
import threading
from evdev import InputDevice, categorize, ecodes, list_devices
from reachy2_sdk import ReachySDK

# --- Configuration ---
REACHY_IP = 'localhost' # Running locally on Reachy
MAX_LINEAR_SPEED = 0.5  # m/s
MAX_ANGULAR_SPEED = 30.0 # deg/s

# Controller Calibration
CENTER = 32768
DEADZONE = 5000 # Ignores the sensitive flutter you saw around 31k-33k

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
    devices = [InputDevice(path) for path in list_devices()]
    for device in devices:
        if "Xbox" in device.name or "Wireless Controller" in device.name:
            print(f"Found controller: {device.name}")
            return device
    return None

gamepad = get_controller()
if not gamepad:
    print("No controller found. Make sure it is paired and turned on!")
    exit()

# --- 3. Continuous Speed Command Thread ---
def send_speed_loop():
    while True:
        # Command holonomic velocity directly in the robot frame
        reachy.mobile_base.set_goal_speed(vx=current_vx, vy=current_vy, vtheta=current_vtheta)
        reachy.mobile_base.send_speed_command()
        time.sleep(0.1) # Send every 100ms to keep the 200ms safety window active

# Start the background thread
threading.Thread(target=send_speed_loop, daemon=True).start()

# --- 4. Main Event Loop (Reading Sticks) ---
print("Listening for input... Press Ctrl+C to stop.")

def map_axis(raw_value, max_speed):
    # Shift the value so the resting point is mathematically 0
    centered = raw_value - CENTER
    
    # Apply the deadzone to ignore stick drift
    if abs(centered) < DEADZONE:
        return 0.0
        
    # Convert to a percentage (-1.0 to 1.0)
    normalized = centered / 32768.0
    
    return normalized * max_speed

try:
    for event in gamepad.read_loop():
        if event.type == ecodes.EV_ABS:
            
            # --- LEFT STICK (Movement) ---
            
            # Y-Axis (Forward/Backward)
            if event.code == ecodes.ABS_Y:
                # '0' is UP. map_axis gives negative for UP. 
                # We want positive vx for forward, so we invert it.
                current_vx = -map_axis(event.value, MAX_LINEAR_SPEED)
            
            # X-Axis (Left/Right Strafe)
            elif event.code == ecodes.ABS_X:
                # '0' is LEFT. map_axis gives negative for LEFT.
                # Positive vy is left, so we invert it.
                current_vy = -map_axis(event.value, MAX_LINEAR_SPEED)
            
            # --- RIGHT STICK (Rotation) ---
            
            # X-Axis (Turning)
            # Depending on the Bluetooth driver, Right Stick X can show up as ABS_RX or ABS_Z.
            # We map both just to be absolutely certain it catches your input.
            elif event.code in (ecodes.ABS_RX, ecodes.ABS_Z):
                # '0' is LEFT. map_axis gives negative for LEFT.
                # Positive vtheta is counterclockwise (left turn), so we invert it.
                current_vtheta = -map_axis(event.value, MAX_ANGULAR_SPEED)

except KeyboardInterrupt:
    print("\nStopping...")
    reachy.mobile_base.set_goal_speed(vx=0.0, vy=0.0, vtheta=0.0)
    reachy.mobile_base.send_speed_command()