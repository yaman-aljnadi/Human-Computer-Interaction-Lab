"""Nod and sway the antennas in a live control loop.

goto_target is for one smooth move that you wait for.
set_target is for a loop: it sends the pose immediately and does not wait.
Use set_target when you want to follow a joystick, a face, or a generated path.

Press Ctrl+C to stop. The robot then returns to a neutral pose.
"""

import time

import numpy as np

from reachy_mini.utils import create_head_pose

from robot import connect, go_home


def main() -> None:
    with connect() as mini:
        go_home(mini, duration=1.0)
        print("Nodding. Press Ctrl+C to stop.")

        try:
            while True:
                t = time.time()
                pitch = np.deg2rad(10 * np.sin(2 * np.pi * 0.5 * t))
                antennas_offset = np.deg2rad(20 * np.sin(2 * np.pi * 0.5 * t))
                mini.set_target(
                    head=create_head_pose(pitch=pitch, degrees=False),
                    antennas=[antennas_offset, -antennas_offset],
                )
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nStopping. Returning to center.")
            go_home(mini, duration=1.0)


if __name__ == "__main__":
    main()
