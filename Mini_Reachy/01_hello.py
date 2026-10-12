"""Connect to Reachy Mini, read its joints, and wiggle the antennas.

Run this first. The daemon on the robot must already be running.
"""

import numpy as np

from robot import connect


def main() -> None:
    with connect() as mini:
        head_joints, antenna_joints = mini.get_current_joint_positions()
        print(f"Head joints (rad):    {np.round(head_joints, 3)}")
        print(f"Antenna joints (rad): {np.round(antenna_joints, 3)}")
        print(f"Antennas (deg):       {np.round(np.rad2deg(antenna_joints), 1)}")

        imu = mini.imu
        if imu is None:
            print("IMU: not available on this unit.")
        else:
            print(f"IMU accel (m/s^2): {np.round(imu['accelerometer'], 2)}")

        # goto_target moves smoothly and waits until the motion finishes.
        # Antennas are [right, left] in radians.
        print("Wiggling antennas...")
        mini.goto_target(antennas=[0.5, -0.5], duration=0.5)
        mini.goto_target(antennas=[-0.5, 0.5], duration=0.5)
        mini.goto_target(antennas=[0.0, 0.0], duration=0.5)

        print("Done. Antennas are back at zero.")


if __name__ == "__main__":
    main()
