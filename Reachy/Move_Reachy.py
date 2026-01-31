from reachy2_sdk import ReachySDK
from reachy2_sdk.utils.utils import get_pose_matrix
import numpy as np

import time

reachy = ReachySDK(host='192.168.50.241')

reachy.head.turn_on()
# reachy.r_arm.turn_on()
# reachy.l_arm.turn_on()

# reachy.head.look_at(x=0.5, y=0, z=0, duration=1.0)

# look_right = reachy.head.look_at(x=0.5, y=-0.5, z=0.1, duration=1.0)
# look_down = reachy.head.look_at(x=0.5, y=0, z=-0.4, duration=1.0)
# look_left = reachy.head.look_at(x=0.5, y=0.3, z=-0.3, duration=1.0)
# look_front = reachy.head.look_at(x=0.5, y=0, z=0, duration=1.0)

# reachy.head.l_antenna.goto(60, duration=0.5)
# reachy.head.r_antenna.goto(60, duration=0.5)

# A = np.array([[0, 0, -1, 0.4], [0, 1, 0, -0.5], [1, 0, 0, -0.2], [0, 0, 0, 1]])
# B = np.array([[0, 0, -1, 0.4], [0, 1, 0, -0.5], [1, 0, 0, 0.0], [0, 0, 0, 1]])
# C = np.array([[0, 0, -1, 0.4], [0, 1, 0, -0.3], [1, 0, 0, 0.0], [0, 0, 0, 1]])
# D = np.array([[0, 0, -1, 0.4], [0, 1, 0, -0.3], [1, 0, 0, -0.2], [0, 0, 0, 1]])

# reachy.l_arm.goto(A)
# reachy.l_arm.goto(B)
# reachy.l_arm.goto(C)
# reachy.l_arm.goto(D)

# reachy.r_arm.inverse_kinematics(reachy.r_arm.forward_kinematics())

while True:
    reachy.head.l_antenna.goto(80, duration=0.7, interpolation_mode='minimum_jerk', wait=True)
    reachy.head.r_antenna.goto(80, duration=0.7, interpolation_mode='minimum_jerk', wait=True)

    reachy.head.l_antenna.goto(0, duration=0.7, interpolation_mode='minimum_jerk', wait=True)
    reachy.head.r_antenna.goto(0, duration=0.7, interpolation_mode='minimum_jerk', wait=True)

time.sleep(12)
reachy.l_arm.turn_off_smoothly()

reachy.head.l_antenna.goto(0, duration=5)
reachy.head.r_antenna.goto(0, duration=5)

reachy.goto_posture('default')

reachy.head.turn_off()