# Mini Reachy starter scripts

Python examples for moving [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) with the `reachy_mini` SDK. These scripts are for Reachy Mini, not the Reachy 2 code (`reachy2_sdk`) elsewhere in this lab repo.

## Connect to the robot

Every script uses [robot.py](robot.py), which opens a **network** connection to `192.168.50.186`. A plain `ReachyMini()` tries localhost first. If something is listening on this computer, the script prints and finishes without moving the robot.

Change `ROBOT_IP` in `robot.py` if the robot's address changes. The daemon on the robot must already be running.

```bash
conda activate HRI
python 01_hello.py
```

On success the script prints the robot name, whether it is the wireless unit, and the daemon's `wlan_ip`. `sim=True` means you reached a simulator, not the robot.

## Scripts

| Script | What it shows |
| --- | --- |
| `01_hello.py` | Connect, read joints and the IMU, wiggle the antennas. |
| `02_look_around.py` | Head, antennas, and body yaw, one move at a time. |
| `03_nod_loop.py` | A live `set_target` loop. Ctrl+C returns to center. |
| `04_play_emotion.py` | One clip from the emotions library. |
| `05_greeting.py` | One short performance: min-jerk, ease-in-out, and cartoon moves. |
| `06_look_at_points.py` | Aim the head at 3D points with `look_at_world`. |
| `07_expressive_loop.py` | A generated figure-8. The body yaw follows the head. |
| `08_emotion_and_dance.py` | A few recorded emotions, then one dance. |

`04` and `08` download Hugging Face datasets the first time they run. Sound is off so they do not need the speaker.

## How motion works

`goto_target` makes one smooth move and waits until it finishes.

`set_target` sends a pose immediately and does not wait. Use it inside a loop (about every 10 ms) when the target keeps changing.

`look_at_world(x, y, z)` aims the head at a point in meters. +X is forward, +Y is left, +Z is up.

`play_move` replays a recorded clip (emotions and dances).

You can command three things:

- **head** — a 4x4 pose from `create_head_pose`. Roll, pitch, and yaw are degrees unless you pass `degrees=False`.
- **antennas** — `[right, left]` in radians.
- **body_yaw** — base turn, in radians. Pass `None` to leave the current yaw alone. The default is `0`, which turns the body back to center.

Interpolation styles for `goto_target`: `minjerk` (default), `ease_in_out`, `cartoon`, and `linear`.
