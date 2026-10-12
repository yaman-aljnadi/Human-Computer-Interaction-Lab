"""Shared connection to the lab Reachy Mini.

ReachyMini() tries localhost first. If anything is listening there, the
script prints and "succeeds" without ever talking to the robot. These
examples always use the robot's IP instead.
"""

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

ROBOT_IP = "192.168.50.186"
ROBOT_PORT = 8000


def connect() -> ReachyMini:
    """Open a network connection to the Reachy Mini daemon."""
    print(f"Connecting to Reachy Mini at {ROBOT_IP}:{ROBOT_PORT}...")
    mini = ReachyMini(
        host=ROBOT_IP,
        port=ROBOT_PORT,
        connection_mode="network",
        media_backend="no_media",
        timeout=8.0,
    )
    status = mini.client.get_status()
    print(
        f"Connected to {status.robot_name} "
        f"(state={status.state}, wireless={status.wireless_version}, "
        f"sim={status.simulation_enabled}, wlan_ip={status.wlan_ip})"
    )
    if status.wlan_ip and status.wlan_ip != ROBOT_IP:
        print(f"Warning: daemon reported wlan_ip {status.wlan_ip}, expected {ROBOT_IP}.")
    return mini


def go_home(mini: ReachyMini, duration: float = 1.2) -> None:
    """Return the head, antennas, and body to a neutral pose."""
    mini.goto_target(
        head=create_head_pose(),
        antennas=[0.0, 0.0],
        body_yaw=0.0,
        duration=duration,
    )
