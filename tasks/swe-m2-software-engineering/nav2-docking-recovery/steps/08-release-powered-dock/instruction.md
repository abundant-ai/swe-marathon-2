# Isolate charging power and complete a measured departure

Extend `/app/dock_recovery` so the robot can safely leave a powered charging dock. When the charger accepts a disconnect request, current may continue to flow through the connector. Wait for actual electrical isolation before undocking. If the application dies after the robot leaves native docking tolerance but before it reaches staging, finish the departure from measured pose. An interrupted trip must not send the robot back into the dock.

Keep the seven earlier checkpoints and their commands working. Use focused modules for charger evidence, ROS motion authority, remaining-path control, and durable departure receipts. The installation uses the existing stock Jazzy docking server and front-facing charging rail. The caller operates one motion mission at a time.

## Request and receipts

Run `python3 -m dock_recovery guarded-undock --spec SPEC.json --state STATE_DIR --output REPORT.json`. The specification includes:

- `request_id` is a 1–64 character string of letters, digits, underscores or hyphens. Use this value as the isolation transaction ID.
- `dock_type` is `calibrated_rail`.
- `seat_pose` and `staging_pose` are finite `[x_m,y_m,yaw_rad]` in `odom`. The staging pose is behind the seat by 0.15–0.60 m along the surveyed heading. The departure corridor permits a centerline deviation of 0.035 m. The fresh physical entry is within 0.012 m of the seat; the connector is closed and charging.
- `isolation_timeout_s` is the positive time allowed for trusted isolation after issuing a matching request, from 2 through 6 seconds inclusive. Bound the full request to 24 seconds from acceptance, including any restart on the same host.

`python3 -m dock_recovery undock-receipt --state STATE_DIR --request-id ID` prints `{"request_id":ID,"status":"accepted"}` while pending, the durable terminal receipt after completion, and exits nonzero for an unknown ID. Write the acceptance before sending a disconnect request or enabling motion. The terminal receipt is `{request_id,status,boot}`, with status `departed` and the verified charger boot on success or `blocked` and a null boot otherwise. Commit it independently of the report file. An exact terminal retry republishes that receipt without requesting power changes, accepting another goal or moving. Reusing the ID with different input exits nonzero without side effects.

## Charger boundary

Publish `std_msgs/msg/String` on `/departure/isolate` with JSON `{transaction_id,boot}` for the current charger boot. The charger treats identical requests as one operation. Obtain the current boot from the valid hardware stream. Retry the same operation if transport feedback is delayed. Keep the robot stopped while acquiring isolation.

Subscribe to `std_msgs/msg/String` on `/departure/power`. A transport reply has `{kind:"ack",transaction_id,boot,stamp_ns,accepted}`. A physical sample has `{kind:"state",transaction_id,boot,stamp_ns,seq,contactor_open,current_amps,contact}`. The clock is ROS wall-clock time. A hardware sample must be no more than 150 ms old and cannot be from the future. The boot is positive and monotonically increasing. Match the active transaction and current boot. Ignore stale, retired or duplicate observations. Reset the isolation streak when the boot changes, the contactor closes, current exceeds the limit, or the stream loses freshness.

Require at least four distinct physical samples spanning 150 ms or more, with strictly increasing sequence and acquisition time, gaps of at most 70 ms, contactor open, and finite absolute current at most 0.10 A. For initial authorization the connector must still be seated, as reported by `contact` and current TF. During an interrupted departure outside the seat, require equally fresh isolation evidence without requiring re-seating. A transport acknowledgment, missing current, lack of charge confirmation or mechanical separation cannot establish isolation. If the contactor fails to open or current fails to settle within the stated timeout, return blocked with the robot still stationary.

## Movement and restart

For an uninterrupted departure, send native `nav2_msgs/action/UndockRobot` on `/undock_robot` once the power boundary is satisfied. Keep the relay disarmed until a goal is accepted. Relay `geometry_msgs/msg/Twist` from `/nav2_cmd_vel` to `/cmd_vel` using the authorized native goal and continued fresh isolation and localization. Use fresh `odom` to `base_link` transforms from `/tf`. The actuator watchdog is 95 ms. Limit linear and angular speeds to 0.18 m/s and 0.50 rad/s in magnitude. Stop or cancel on loss of isolation, clock or localization freshness, timeout or unsafe travel. The connector must never separate while true current exceeds 0.10 A.

On restart keep motion disarmed and cancel an orphaned native retreat before taking control. Recover from the measured pose using the existing accepted request and new physical isolation evidence. If the robot is outside docking tolerance and short of staging, follow the remaining surveyed corridor without returning into the seat or assuming a native action result means the corridor is free. You may use a separately gated local controller for this remaining segment. Do not send forward re-approach commands. Declare the corridor clear only when measured pose is within 0.027 m of the surveyed staging pose and yaw is within 0.12 rad, the robot has stopped there, and its isolation evidence is still fresh. For an uninterrupted request also require native undock success.

The charger state and contact model are authored for the commissioned simulator. The interface reflects the power-release responsibilities supported by Jazzy docking plugins. [Jazzy charging plugin API](https://api.nav2.org/nav2-jazzy/html/classopennav__docking__core_1_1ChargingDock.html) · [Nav2 navigation and undocking ownership](https://github.com/ros-navigation/navigation2/issues/4503)
