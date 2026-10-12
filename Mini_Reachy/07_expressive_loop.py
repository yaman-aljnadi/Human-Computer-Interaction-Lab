"""Live generated motion: the head traces a figure-8 and the body follows.

This is the pattern for behaviors you compute yourself (tracking, a
joystick, a timer). set_target does not wait, so the loop decides the
pose about 100 times a second.

Press Ctrl+C to stop. The robot then returns to center.
"""

import time

import numpy as np

from reachy_mini.utils import create_head_pose

from robot import connect, go_home


def pose_at(t: float) -> tuple[np.ndarray, list[float], float]:
    """Head pose, antenna angles, and body yaw at time t (seconds)."""
    yaw_deg = 20 * np.sin(2 * np.pi * 0.2 * t)
    pitch_deg = 10 * np.sin(2 * np.pi * 0.4 * t)
    roll_deg = 8 * np.sin(2 * np.pi * 0.2 * t)
    ear = np.deg2rad(28 * np.sin(2 * np.pi * 0.5 * t))
    head = create_head_pose(yaw=yaw_deg, pitch=pitch_deg, roll=roll_deg)
    antennas = [float(ear), float(-ear)]
    body_yaw = float(np.deg2rad(0.6 * yaw_deg))
    return head, antennas, body_yaw


def main() -> None:
    with connect() as mini:
        go_home(mini, duration=1.0)
        print("Figure-8. Press Ctrl+C to stop.")
        t0 = time.time()

        try:
            while True:
                head, antennas, body_yaw = pose_at(time.time() - t0)
                mini.set_target(head=head, antennas=antennas, body_yaw=body_yaw)
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nStopping. Returning to center.")
            go_home(mini, duration=1.2)


if __name__ == "__main__":
    main()
