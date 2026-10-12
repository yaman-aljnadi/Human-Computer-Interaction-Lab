# Progress report: arm self-collision safety for Reachy 2 teleoperation

Date: October 12, 2026  
Robot: Reachy 2, host `r2-0004`  
Software: ROS 2 Humble inside `pollenrobotics/reachy2_core:1.7.5.9_release`  
Unity project: Reachy2Teleoperation

## Objective

The operator drives both arms from a Unity teleoperation client. The robot needs a joint safety behavior so the arms cannot hit each other. When the arms approach, the system should warn, then slow the motion, then hold the last safe command if the next command would bring the arms closer. Motion that increases the separation should still be allowed.

The check has to consider the full arm, including elbows and forearms, using both the commanded hand targets and the joint angles reported by the robot. Using the chest depth camera to avoid tables and other obstacles is planned as a later extension of the same check.

## Direction taken

After review, the safety behavior is being implemented on the robot in ROS 2 Humble, rather than in the Unity client. The items under that direction were: ROS 2 Humble, MoveIt keep-out zones, moving the safety logic off Unity, the delay between the controllers and the robot hands, and an automatic intervention instead of a warning that the operator can ignore.

A first Unity prototype was built and then set aside. It crashed the editor because a robot-state callback updated on-screen text from a background thread. Those Unity components are to stay disabled.

## What was found on the robot

The Reachy software is not in the home workspace. `~/Reachy` and `~/ros2_ws` are leftover folders from an older project. The live stack runs in Docker. `reachy2-core.service` runs the container `core` from `pollenrobotics/reachy2_core:1.7.5.9_release`. Unity reaches the robot through the WebRTC containers (`pollenrobotics/webrtc:2.0.1.2_deploy`).

Arm teleoperation follows one path:

```text
Unity hand pose
  -> reachy_abstract_bridge_node
  -> /l_arm/ik_target_pose and /r_arm/ik_target_pose
     (pollen_msgs/IKRequest)
  -> /kinematics, function on_ik_target_pose
  -> /l_arm_forward_position_controller/commands
     and the right-arm equivalent
     (std_msgs/Float64MultiArray)
  -> forward position controller for that arm
```

The running kinematics process loads:

`/home/reachy/reachy_ws/build/pollen_kdl_kinematics/pollen_kdl_kinematics/pollen_kdl_kinematics_node.py`

The command that moves the arm is the publication of `sol`, the seven joint angles returned by inverse kinematics, inside `on_ik_target_pose`. At that moment the same node also has the latest `/joint_states` for both arms. That is the point where a new command can be compared with the current arm geometry and replaced with the last safe command.

`/l_arm/cart_target_pose` looks related, but the kinematics node does not subscribe to it. Only rosbag recording was subscribed. It is not the teleoperation command.

## MoveIt keep-out zones

MoveIt is not part of the stack that is running on this robot. A MoveIt keep-out zone constrains MoveIt plans. This teleoperation path does not ask MoveIt to plan. It streams inverse-kinematics results to the forward position controllers.

Pollen's MoveIt setup also expects the arms to be switched to trajectory controllers. That would replace the streaming controller Unity is using. The controller type should stay as it is. The keep-out behavior can still be obtained by enforcing the distance limit on the command this node already publishes.

## De-synchronization

The delay between the headset controllers and the robot hands comes from doing the prediction in Unity while the robot executes an older command. In `on_ik_target_pose` both pieces are already in one place: the hand target that is about to be executed, and the joint angles the robot is currently reporting. The safety decision uses those values on the robot clock.

One open check remains. `/joint_states` has two publishers, `joint_state_broadcaster` and `fake_gz_interface`. The kinematics node keeps the message that arrived last. Before the distance check is trusted, a teleoperation session should confirm that the message it reads is the live hardware state.

## Proposed safety behavior

Add the check in `on_ik_target_pose` after inverse kinematics and before the joint command is published.

1. From the proposed joint angles, and from the other arm's current joint angles, compute shoulder, elbow, wrist, and hand positions. The existing forward-kinematics helper returns only the hand tip, so the elbow and wrist come from intermediate frames of the same arm chain (`torso` to `l_arm_tip` or `r_arm_tip`).
2. Treat each upper arm, forearm, and hand as a capsule and measure the smallest surface gap.
3. Warn when the gap enters the warning band.
4. Slow the joint step when the gap enters the danger band.
5. If the gap is critical and the new command would make it smaller, publish the last safe joint command instead. Publish the new command when it moves the arms apart.

The reachability message this node already publishes can carry the warning back to Unity without the interface code that crashed the editor. Controller vibration can be added later from that same result.

Starting gap thresholds, still to be tuned on this robot, are 0.15 m warning, 0.08 m danger, and 0.04 m critical. A few colliding and near-base joint poses have already been written down for that test.

Depth-camera obstacles use the same capsule test later. The depth topics are already published by `core`. The image stays on the robot.

## Next steps

1. Confirm that an edit to the loaded kinematics file survives a container restart, and keep a copy of the change outside the container.
2. Read the arm-chain segment names and print elbow and wrist positions for a known pose, with no change to the commands the robot executes.
3. Add logging only, restart the kinematics node under supervision, and compare the reported gap with the recorded close-arm poses.
4. Enable slow, then hold-last-safe, with the torque-off procedure ready.
5. Tune the three distance thresholds on the robot.
6. After arm-to-arm behavior is reliable, add chest-camera obstacles to the same test.

## Current status

The command path and the insertion point are identified. No safety code has been installed on the robot yet. The Unity prototype is disabled from further use because the safety decision is moving to ROS.
