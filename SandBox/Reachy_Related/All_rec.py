import time
import numpy as np
from reachy2_sdk import ReachySDK

reachy = ReachySDK(host='192.168.50.242')

# Make joints compliant for kinesthetic teaching
reachy.l_arm.turn_off()
reachy.r_arm.turn_off()

sampling_frequency = 100  # Hz
record_duration = 240      # seconds

# Left arm joints
left_arm_joints = [
    reachy.l_arm._shoulder.pitch,
    reachy.l_arm._shoulder.roll,
    reachy.l_arm._elbow.yaw,
    reachy.l_arm._elbow.pitch,
    reachy.l_arm._wrist.roll,
    reachy.l_arm._wrist.pitch,
    reachy.l_arm._wrist.yaw,
]


right_hand_joints = [
    reachy.r_arm._shoulder.pitch,
    reachy.r_arm._shoulder.roll,
    reachy.r_arm._elbow.yaw,
    reachy.r_arm._elbow.pitch,
    reachy.r_arm._wrist.roll,
    reachy.r_arm._wrist.pitch,
    reachy.r_arm._wrist.yaw,

]

# Combine all joints to record
recorded_joints = left_arm_joints + right_hand_joints

trajectories = []

print("Recording ARM + HEAD movement...")
start = time.time()
while (time.time() - start) < record_duration:
    point = [joint.present_position for joint in recorded_joints]
    trajectories.append(point)
    time.sleep(1 / sampling_frequency )

traj_array = np.array(trajectories)

# Save everything together
np.save("leftright_arm_traj1.npy", traj_array)

print("Recording finished and saved as left_arm_head_traj.npy")

# Sound alert
for _ in range(3):
    print("\a")
    time.sleep(0.2)
