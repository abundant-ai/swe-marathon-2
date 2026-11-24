# Synthesize a loaded transfer from physical grasp frames

Plan a transfer in the commissioned two-arm cell from measured joints and task-space grasp targets. Select a feasible handoff pose, reach the two compatible gripper poses, transfer the part at rest, and deliver it to the surveyed target. The request provides the task geometry. Joint waypoints and allowed edges must come from your planner. Keep the earlier commands available.

```bash
python3 -m dual_arm plan-native --spec SPEC.json --output REPORT.json
```

## Cell and objective

- `robot_xml` is the supplied single-arm UR5e model. `calibration` is a successful `commission-native` report. The two calibrated marker frames serve as the gripper grasp sites. Each arm has six joints in model order. Retain the native collision shapes and hinge limits.
- `payload` has positive `half_size_m` for a rigid box, positive `mass_kg`, and `object_from_grasp` poses for `left` and `right`. These transform a gripper's grasp site from the part frame. The maximum box half dimension is 0.42 m, each grasp offset's norm is at most 0.48 m, and each marker's flange offset is at most 0.30 m. Keep the part rigidly attached to its current holder.
- `fixtures` contains up to 16 fixed boxes, with `half_size_m` and `world_from_box` for each. Verify separation by at least `clearance_m` after subtracting the shapes. Include arm–arm, nonadjacent self, arm–part, fixture–arm and part–fixture pairs. Same-body and direct parent-child arm shapes may meet. The task uses authored collision envelopes and strictly positive margins.
- `measured` contains nonnegative `tick`, `owner`, and `q` and `dq` maps with six joint positions and velocities for `left` and `right`. Concatenated `speed_rad_s` and `acceleration_rad_s2` hold positive limits, left then right. Each tick is 5 ms. `deadline_tick` is at most 7,000 ticks after measurement.
- `handoff_object_poses` lists up to eight permissible world poses of the payload at a transfer. The list may be empty when the destination owner already holds the part. `transfer_ticks` is a positive stationary dwell. `destination` contains the required `owner` and `world_from_object` pose.

## Plan

Return `{"status":"ready","commands":[...]}` or `{"status":"blocked","commands":[]}` if unable to complete safely. Plan continuously collision-free motion with a positive clearance after accounting for execution error. Joint-space motion can be synthesized by any method. At a handoff combine object and tool transforms in full SE(3) and make both grasps physically compatible. Payload orientation matters through the approach, custody receipt and delivery.

Every command has integer `start` and `end`. The first starts at the measured tick, and successive intervals are contiguous. A `move` has `q` containing the terminal positions for both arms. Its commanded joint path from the previous position is the rest-to-rest cubic with normalized phase `3u²−2u³`. A `brake` has the same `q` shape and decelerates linearly from measured velocity to zero. It displaces each joint by half the starting rate times the interval in seconds. Brake first when any measured rate exceeds 0.025 rad/s. A `transfer` has `to` naming the other arm, holds both arms throughout `transfer_ticks`, and changes custody at the end only if the receiver is aligned. Its initial object pose must be within 0.036 m and 0.11 rad of an allowed handoff pose.

A native controller tracks the commanded trajectory while exposing actual encoder and payload state. The receiver must be within 0.018 m and 0.055 rad of its grasp site, with maximum joint speed 0.17 rad/s before exchange. Qualifying motion keeps position tracking error below 0.04 rad, avoids native contact and reaches the destination with position error at most 0.027 m and orientation error at most 0.075 rad. The required owner must hold the actual payload at completion. An empty ready plan is acceptable if the measured state already meets the goal with speed at most 0.025 rad/s. Reject malformed requests without replacing an existing report. Separate task-space synthesis, geometry and timing.
