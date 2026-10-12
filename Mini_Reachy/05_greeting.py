"""A short greeting that combines the head, antennas, body, and motion styles.

goto_target can interpolate in four ways:
  minjerk     smooth start and stop (the default)
  ease_in_out slow at the ends, faster in the middle
  cartoon     overshoots a little, then settles
  linear      constant speed
"""

import numpy as np

from reachy_mini.utils import create_head_pose
from reachy_mini.utils.interpolation import InterpolationTechnique

from robot import connect, go_home


def main() -> None:
    with connect() as mini:
        print("Perking up.")
        mini.goto_target(
            head=create_head_pose(roll=8, pitch=-8),
            antennas=np.deg2rad([35, -35]).tolist(),
            body_yaw=0.0,
            duration=1.0,
            method=InterpolationTechnique.MIN_JERK,
        )

        print("Looking to the left with the body.")
        mini.goto_target(
            head=create_head_pose(yaw=20, roll=-6),
            antennas=np.deg2rad([15, 40]).tolist(),
            body_yaw=np.deg2rad(25),
            duration=1.4,
            method=InterpolationTechnique.EASE_IN_OUT,
        )

        print("Looking to the right.")
        mini.goto_target(
            head=create_head_pose(yaw=-20, roll=6),
            antennas=np.deg2rad([40, 15]).tolist(),
            body_yaw=np.deg2rad(-25),
            duration=1.4,
            method=InterpolationTechnique.EASE_IN_OUT,
        )

        print("Cartoon nod.")
        mini.goto_target(
            head=create_head_pose(pitch=12),
            antennas=np.deg2rad([20, 20]).tolist(),
            body_yaw=0.0,
            duration=0.45,
            method=InterpolationTechnique.CARTOON,
        )
        mini.goto_target(
            head=create_head_pose(pitch=-10, z=10, mm=True),
            antennas=np.deg2rad([45, 45]).tolist(),
            duration=0.7,
            method=InterpolationTechnique.CARTOON,
        )

        print("Back to center.")
        go_home(mini, duration=1.5)


if __name__ == "__main__":
    main()
