# Confirm electrical seating on the live Jazzy dock

Add a supervisor to `/app/dock_recovery` for a commissioned low-speed charging station. The station uses the stock Jazzy Nav2 docking server. A nominal docking pose can be within the server's tolerance while the connector remains open. A delayed or previous-boot current packet can also lead the native server to return success prematurely.

Keep the earlier controller, restart protocol, and `compile` command available. Organize the new code into focused modules for ROS interfaces, the charge and motion gates, and durable receipts. The public example at `/app/example/native_dock.py` brings up the commissioned interfaces on a local ROS domain.

## Command and request

Run `python3 -m dock_recovery guarded-dock --spec SPEC.json --state STATE_DIR --output REPORT.json`. The JSON specification contains these fields.

| Field | Meaning |
| --- | --- |
| `request_id` | 1–64 letters, digits, underscores, or hyphens. |
| `dock_type` | The commissioned native plugin name `calibrated_rail`. |
| `targets` | One to eight objects with distinct nonempty string `id`, finite `x`, `y` in meters within ±1, and `yaw` in radians within ±π. The first entry is the nominal pose. |
| `obstacles` | Up to twelve rectangular no-go regions in odom, given by finite `min_x`, `max_x`, `min_y`, `max_y` in meters. Each axis has positive extent. The chassis has a 0.019 m clearance radius. |

The server is already active and the robot starts inside the commissioned staging area. Use actual `nav2_msgs/action/DockRobot` goals on `/dock_robot` with an explicit pose in `odom`, the commissioned plugin type, and navigation to staging disabled. On a nominal electrical seating failure, use `nav2_msgs/action/UndockRobot` on `/undock_robot` to retreat to staging before approaching an unobstructed alternate pose. Use the supplied order for alternatives after excluding obstructed targets. Run at most one native motion goal at a time. Bound receipt completion to 35 seconds on an active graph, including safe failure when there is no available route or sustained current.

## Physical command and charger interfaces

- Subscribe to `geometry_msgs/Twist` on `/nav2_cmd_vel` and publish gated native commands to the actuator `/cmd_vel`. The native relay is the only source of moving commands. Use fresh `odom` to `base_link` transforms from `/tf` to protect obstacles during approach and retreat. The cell uses planar forward and angular velocities with absolute limits 0.18 m/s and 0.50 rad/s. Stop relaying motion on action completion, stale localization, cancel, unsafe motion, or timeout. The actuator stops after 95 ms without a newly received command.
- Subscribe to `std_msgs/UInt64` on `/charger/boot`, `std_msgs/Bool` on `/charger/contact`, and `sensor_msgs/BatteryState` on `/charger/battery_state`. The battery message uses `header.frame_id = "charger_boot_<decimal boot>"` and a ROS acquisition timestamp. ROS uses wall-clock time. Contact must be true and have been received in the last 200 ms during the current observed boot.
- Publish qualified `sensor_msgs/BatteryState` on `/qualified_battery` for the native dock plugin. Accept only samples from the current boot with a timestamp at most 200 ms old and no later than the current ROS time, present battery, charging status, and finite current above 0.5 A. Confirm with at least four strictly increasing samples spanning at least 60 ms while contact remains true, with gaps of at most 100 ms. Clear confirmation on a new boot, loss of contact, freshness loss, or a gap in the charge samples. While confirmation is absent, publish no positive current to the plugin.
- Declare `docked` only with native success and current independent charge confirmation. A close transform or native action result alone is insufficient. An open circuit, unsafe path, or exhausted retry returns `blocked` with movement disarmed.

## Receipts and restart

- Persist acceptance before sending native goals or moving. `python3 -m dock_recovery dock-receipt --state STATE_DIR --request-id ID` prints `{"request_id":ID,"status":"accepted"}` while the request is pending, prints its durable terminal receipt when it exists, or exits nonzero for an unknown ID. A reader must be able to inspect it while the worker is running.
- A terminal receipt has `request_id`, `status` (`docked` or `blocked`), `boot` and `target_id` (the confirmed boot and delivered pose ID when docked, otherwise `null`), and `attempts` (an array of completed action results with `action`, `target_id`, `status`, and native integer `error_code` or `null`). Use `dock` and `undock` for action names and `succeeded`, `failed`, `rejected`, `timed_out`, or `unsafe` for action results. An interrupted action may be absent from the receipt.
- Repeating a terminal request with the same specification republishes the receipt atomically without sending a new native goal or moving. Invalid input and a reused ID with different content exit nonzero. Hold at most one motion worker for a request. Commit terminal state independently of writing `REPORT.json` so an unavailable output path can be retried safely.
- When restarting a pending request, keep the relay disarmed while canceling orphaned native dock and undock goals. This installation has one mission owner. Replan from the live physical and electrical observations, discard process-local confirmation, and complete the accepted request without assuming old goals finished.
