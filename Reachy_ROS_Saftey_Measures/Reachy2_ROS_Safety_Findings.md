# Reachy 2 arm-safety findings

Robot: `bedrock@r2-0004`  
Core image: `pollenrobotics/reachy2_core:1.7.5.9_release`  

Purpose: record where Unity teleoperation actually commands the arms, so the self-collision check can be added on the robot.

This file is the working log. The shorter write-up for review is `Reachy2_ROS_Safety_Progress_Report.md` in this same folder.

## Goal

While a person drives Reachy 2 from Unity, the two arms must not hit each other. The intended behavior is tiered:

1. Warn when the arms get close.
2. Slow the motion.
3. Hold the last safe joint command when a new command would bring the arms closer. A command that increases the separation still goes through.

Detection has to use the commanded hand targets and the robot's reported joint angles, so elbows and forearms are included, not only the hands. Obstacle avoidance from the chest depth camera is a later addition to the same check.

## Where the software actually is

`~/Reachy` and `~/ros2_ws` on the robot are leftover folders from an older project. `~/Reachy` has no robot source. `~/ros2_ws/src` has no packages. Searching those folders cannot find the kinematics code.

The running stack is Docker, started by systemd:

| Service | Container | Image |
| --- | --- | --- |
| `reachy2-core.service` | `core` | `pollenrobotics/reachy2_core:1.7.5.9_release` |
| `reachy2-dashboard.service` | `reachy2-dashboard` | `pollenrobotics/reachy2-dashboard:1.2.1_deploy` |
| `webrtc.service` | `webrtc_streaming_playback_ros`, `grpc-webrtc-bridge-con`, `webrtc_signalling` | `pollenrobotics/webrtc:2.0.1.2_deploy` |
| (running with the stack) | `display` | `pollenrobotics/display:1.1.8_release` |
| (running with the stack) | `plum` | `pollenrobotics/plum:1.0.3_release` (host port 5000) |

`core` is where joints, inverse kinematics, and arm controllers run. The WebRTC containers are what Unity talks to. ROS 2 Humble is installed inside `core`. A host shell that only sources `/opt/ros/humble/setup.bash` does not show the Reachy packages, and after `ros2 daemon stop` most arm topics disappear from the host. Inspect the graph with `docker exec` into `core`.

## Teleoperation command path

This path was confirmed from topic types, publishers, subscribers, and the kinematics source.

```text
Unity hand pose
  -> gRPC / WebRTC
  -> node /reachy_abstract_bridge_node
  -> /l_arm/ik_target_pose and /r_arm/ik_target_pose
     type: pollen_msgs/msg/IKRequest
     QoS: best effort, volatile
  -> node /kinematics, callback on_ik_target_pose
  -> /l_arm_forward_position_controller/commands
     and /r_arm_forward_position_controller/commands
     type: std_msgs/msg/Float64MultiArray
     QoS: reliable, volatile
  -> l_arm_forward_position_controller / r_arm_forward_position_controller
```

`/l_arm_goto_action_server` and `/r_arm_goto_action_server` publish the same `IKRequest` topics. A check inside `on_ik_target_pose` covers Unity teleoperation and scripted gotos.

`IKRequest` fields:

- `pose`: `geometry_msgs/PoseStamped` (the 6D hand goal)
- `constrained_mode`: `"unconstrained"` or `"low_elbow"`
- `preferred_theta`: elbow angle the solver tries to reach, in radians
- `d_theta_max`: maximum elbow change along the reachability circle in continuous mode
- `continuous_mode`: `"continuous"` or `"discrete"`
- `order_id`: id used to match a reachability result to a request
- `traceparent`: tracing metadata

Inside `on_ik_target_pose` the callback solves inverse kinematics into `sol` (seven joint angles) and then executes:

```python
msg = Float64MultiArray()
msg.data = sol
forward_publisher.publish(msg)
```

In the source file that publish is line 660. A `ReachabilityState` is published immediately afterward on `/l_arm_reachability_states` or `/r_arm_reachability_states`. Unity already displays that reachability result.

`/l_arm/cart_target_pose` is a different message, `pollen_msgs/msg/CartTarget`. The bridge publishes it, and the only subscriber seen was `rosbag2_recorder`. The kinematics node does not read it. The same is true of the right arm. Do not put the safety check on `cart_target_pose`.

## File the running node loads

Process 792 on October 12, 2026:

```text
/usr/bin/python3 /home/reachy/reachy_ws/install/pollen_kdl_kinematics/lib/pollen_kdl_kinematics/pollen_kdl_kinematics --ros-args -r __node:=kinematics -r __ns:=/
```

That install path is an entry-point script. Importing the module from a shell that sources the workspace resolves to:

```text
/home/reachy/reachy_ws/build/pollen_kdl_kinematics/pollen_kdl_kinematics/pollen_kdl_kinematics_node.py
```

A second copy is the source tree:

```text
/home/reachy/reachy_ws/src/ros2_pollen_toolbox/pollen_kdl_kinematics/pollen_kdl_kinematics/pollen_kdl_kinematics_node.py
```

The publish block quoted above was read from the source copy. The build copy is the file Python imports. It is not yet confirmed whether the build file is a link to the source file. An edit has to land in the file the process imports, and process 792 keeps running the old code until that node is restarted.

Related source read during the investigation:

- `kdl_kinematics.py`: `forward_kinematics` at line 26 calls `fk_solver.JntToCart` and returns one tip pose.
- Arm chains are built from link `torso` to `l_arm_tip` and `r_arm_tip`.
- `get_current_position` reads `/joint_states` into the joints of one chain.
- Startup logs say a chain was found for `l_arm`, `r_arm`, and `head`. The joint-name lines under those messages were not captured.

`/joint_states` (`sensor_msgs/msg/JointState`) has two publishers inside `core`:

- `joint_state_broadcaster`, reliable, volatile
- `fake_gz_interface`, reliable, transient local

Subscribers include `kinematics`, `robot_state_publisher`, `central_joint_state_handler`, and `rosbag2_recorder`. The kinematics node stores whichever `JointState` arrived last. Which publisher is the live hardware stream during teleoperation is still unchecked.

## Why this is the safety insertion point

At the `msg.data = sol` line, one node already has:

- the arm being commanded (`l_arm` or `r_arm`)
- the joint angles about to be sent (`sol`)
- the other arm's current joint angles from `/joint_states`
- a forward-kinematics solver for both chains

The check can build both arms, measure the gap, and replace `sol` with the last safe command when the new command would close that gap. Commands that move the arms apart still publish.

MoveIt keep-out zones do not sit on this path. MoveIt is not installed in the host ROS environment. Pollen's separate MoveIt image expects `controllers:=trajectory`, which replaces the streaming forward-position controllers this teleoperation uses. Leave the controller type as it is.

The current `forward_kinematics` helper returns the hand tip only. Elbow and wrist positions require a pose at intermediate chain segments (`JntToCart` with a segment number). Those segment indexes still have to be read from the loaded chain before the capsules are hardcoded.

Other `forward_publisher.publish` calls in the same file serve the head, an older pose topic, and an averaged pose topic. Unity arm teleoperation uses the publish inside `on_ik_target_pose`.

## Unity work already done, then set aside

A first safety prototype was added in this Unity project: forward kinematics, capsule distance, tiered warning / slow / freeze, a warning panel, and controller vibration. It was wired into `RobotDataScene` and `TeleoperationScene`.

Playing teleoperation crashed the Unity editor. The crash is in `ArmCollisionWarningUIManager`: a joint-state callback arrives on the GStreamer thread and sets UI text from that thread. The professor's direction is to do this safety on the robot, so those Unity components should stay disabled:

- `RobotDataScene`: `Arm Self Collision Manager`, `Arm Collision Haptics Feedback`
- `TeleoperationScene`: `Arm Collision Warning UI Manager`

Starting distances used in that prototype, measured as surface gap, were warning 0.15 m, danger 0.08 m, and critical 0.04 m. Capsule radii were about 0.055 m (upper arm), 0.05 m (forearm), and 0.06 m (hand). Those numbers came from the simplified kinematics documentation, not from a tuned test on `r2-0004`. Retune them on the robot.

## Depth camera, later

These topics already exist inside `core`:

- `/camera/depth/image_raw`
- `/camera/depth/camera_info`
- `/camera/depth_registered/points`
- `/camera/color/image_raw`

Obstacle capsules from that depth image can be added to the same distance test. They should be computed on the robot. Raw depth does not need to be sent to the headset.

## Recorded poses to test against

From `Danger_Zones.txt` at the Unity project root. Values are degrees.

Arms close to each other:

```text
r_arm.shoulder.pitch -17.2, shoulder.roll 16.2, elbow.yaw -3.7, elbow.pitch -69.3
l_arm.shoulder.pitch -20.9, shoulder.roll -17.5, elbow.yaw -3.5, elbow.pitch -71.0

r_arm.shoulder.pitch -33.5, shoulder.roll 5.9, elbow.yaw -17.8, elbow.pitch -49.6
l_arm.shoulder.pitch -45.7, shoulder.roll -29.7, elbow.yaw 9.1, elbow.pitch -40.5
```

Arms near the base:

```text
r_arm.shoulder.pitch 1.8, shoulder.roll 21.4, elbow.yaw -33.6, elbow.pitch -1.2
l_arm.shoulder.pitch -6.1, shoulder.roll -20.3, elbow.yaw 6.3, elbow.pitch -3.2
```

Wrist joints were not recorded in that note.

## Commands that produced these facts

Run on the robot host. They only read.

```bash
docker exec core bash -lc 'source /opt/ros/humble/setup.bash; source /home/reachy/reachy_ws/install/setup.bash; ros2 topic info /l_arm/ik_target_pose -v; ros2 interface show pollen_msgs/msg/IKRequest'
```

```bash
docker exec core bash -lc 'ps -eo pid,args | grep -E "[p]ollen_kdl|[k]inematics_node"'
```

```bash
docker exec core bash -lc 'source /opt/ros/humble/setup.bash; source /home/reachy/reachy_ws/install/setup.bash; python3 -c "import pollen_kdl_kinematics.pollen_kdl_kinematics_node as m; print(m.__file__)"'
```

`pgrep -f pollen_kdl_kinematics_node` is a bad search here: it matches the `docker exec` shell that contains that text. Use the `ps | grep` form above.

## Still open

- Whether the build `.py` and the source `.py` are the same file.
- Whether a container restart would discard an edit. Check `docker inspect core` mounts before relying on an in-container edit.
- Segment indexes for shoulder, elbow, wrist, and tip on the loaded KDL chain.
- Which `/joint_states` publisher is the live hardware stream while Unity is connected.
- Tuned gap thresholds on this robot.
- A safe way to restart only `/kinematics` after an edit.
