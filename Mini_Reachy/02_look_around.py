"""Move the head, antennas, and body with one goto_target call at a time.

Reachy Mini has three things you can command:
  - head: a 4x4 pose from create_head_pose (degrees=True keeps angles in degrees)
  - antennas: [right, left] in radians
  - body_yaw: turn of the base, in radians
"""

import numpy as np

from reachy_mini.utils import create_head_pose

from robot import connect, go_home


def main() -> None:
    with connect() as mini:
        print("Looking left...")
        mini.goto_target(head=create_head_pose(yaw=25), duration=1.2)

        print("Looking right...")
        mini.goto_target(head=create_head_pose(yaw=-25), duration=1.2)

        print("Looking up...")
        mini.goto_target(head=create_head_pose(pitch=-15), duration=1.0)

        print("Turning the body and spreading the antennas...")
        mini.goto_target(
            head=create_head_pose(),
            antennas=np.deg2rad([30, 30]).tolist(),
            body_yaw=np.deg2rad(20),
            duration=1.5,
        )

        print("Back to center.")
        go_home(mini)


if __name__ == "__main__":
    main()
