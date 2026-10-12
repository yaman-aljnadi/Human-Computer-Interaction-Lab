"""Aim the head at points in space with look_at_world.

The head's forward direction is +X, in meters. Distance does not matter:
look_at_world uses the direction of the point. Antennas lift when the
point is above the robot and drop when it is below.
"""

import numpy as np

from robot import connect, go_home

# name, x forward, y left, z up. All in meters.
POINTS = [
    ("straight ahead", 0.6, 0.0, 0.0),
    ("upper left", 0.6, 0.22, 0.18),
    ("upper right", 0.6, -0.22, 0.18),
    ("lower left", 0.6, 0.18, -0.12),
    ("lower right", 0.6, -0.18, -0.12),
    ("straight ahead", 0.6, 0.0, 0.05),
]


def main() -> None:
    with connect() as mini:
        for name, x, y, z in POINTS:
            antennas = np.deg2rad([25, 25] if z >= 0 else [-15, -15]).tolist()
            print(f"Looking at {name} ({x:.2f}, {y:.2f}, {z:.2f})")
            mini.goto_target(antennas=antennas, body_yaw=None, duration=0.4)
            mini.look_at_world(x, y, z, duration=1.0)

        print("Back to center.")
        go_home(mini)


if __name__ == "__main__":
    main()
