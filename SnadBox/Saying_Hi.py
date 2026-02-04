from reachy2_sdk import ReachySDK
import time

# 1. Connect to Reachy
reachy = ReachySDK(host='192.168.50.241')

reachy.r_arm.turn_on()


# Neutral posiiton
neutral_pos = {
    'r_arm.shoulder.pitch': 0,
    'r_arm.shoulder.roll': 0,
    'r_arm.elbow.yaw': 0,
    'r_arm.elbow.pitch': 0,
    'r_arm.wrist.roll': 0,
    'r_arm.wrist.pitch': 0,
    'r_arm.wrist.yaw': 0
}

# Upper arm raised, elbow bent 90 degrees, palm facing forward (This is Hell to figure out and I hate it)
wave_ready_pos = {
    'r_arm.shoulder.pitch': -30,  # Lift arm forward/up
    'r_arm.shoulder.roll': 10,   # Slight angle out to the side
    'r_arm.elbow.yaw': -10,
    'r_arm.elbow.pitch': -95,     # Bend elbow so hand is up
    'r_arm.wrist.roll': 0,
    'r_arm.wrist.pitch': -40,     # Slight wrist adjustment
    'r_arm.wrist.yaw': 0
}


print("Step 1: Moving to Neutral Start...")
reachy.r_arm.goto(list(neutral_pos.values()), duration=3.0, wait=True)

print("Moving to Ready Position...")
reachy.r_arm.goto(list(wave_ready_pos.values()), duration=3, wait=True)

print("Waving...")

wave_left = wave_ready_pos.copy()
wave_left['r_arm.wrist.roll'] = -20  # Tilt left

wave_right = wave_ready_pos.copy()
wave_right['r_arm.wrist.roll'] = 20  # Tilt right

for i in range(2):
    # Move to Left
    reachy.r_arm.goto(list(wave_left.values()), duration=0.5, wait=True)
    
    # Move to Right
    reachy.r_arm.goto(list(wave_right.values()), duration=0.5, wait=True)

print("Returning to Neutral...")
reachy.r_arm.goto(list(neutral_pos.values()), duration=2.0, wait=True)

reachy.r_arm.turn_off_smoothly()
print("Done.")