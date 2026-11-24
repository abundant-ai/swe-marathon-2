# Reverse onto a charging dock

Our navigation stack brings the robot to a staging pose near its assigned charger. Build the controller that takes over there. It should acquire the dock from the rear camera and reverse into contact. Use modular code so we can reuse the pose tracking and motion control separately.

Put the Python package in `/app/dock_recovery` and run it from `/app`.

```bash
python3 -m dock_recovery --config CONFIG.json --state STATE_DIR
```

The process reads one observation per stdin line and flushes one JSON response per line. Output `{"v_mps":number,"w_radps":number,"status":"running"|"docked"|"failed"}`. Positive linear speed drives forward. Positive angular speed turns counterclockwise. Send diagnostics to stderr. The state directory is writable and may be empty. An example configuration is at `/app/example/config.json`.

## Pose and observation convention

An SE(2) pose is `[x_m,y_m,yaw_rad]`, with x forward, y left, and yaw counterclockwise. A pose named `a_from_b` maps from frame b to frame a.

| Configuration | Definition |
| --- | --- |
| `tag_id` | Identifier of the assigned charger tag |
| `base_from_camera` and `tag_from_dock` | Extrinsics from camera to robot base, and the desired seated robot pose in the tag frame. The orientation of the desired seated pose points away from the charger. |
| `tick_seconds`, `deadline_tick` | Fixed command interval in seconds, and the last allowed tick for this mission |
| `tag_max_age_ticks`, `tag_jump_m`, `tag_jump_rad` | Maximum age inclusive, and maximum accepted translation and wrapped yaw change in a dock track within the same odometry epoch |
| `max_reverse_mps`, `max_angular_radps` | Reverse and angular speed limits |
| `near_distance_m`, `near_reverse_mps` | Use the lower reverse speed limit when within this distance of the tracked seated pose |

Observations have increasing integer `tick`, starting at 0, a boolean contact switch `contact`, `odom` and an array of `detections`. The odometry is `{"epoch":integer,"pose":[x,y,yaw]}`, expressing the robot base in the current odometry frame. Each detection is `{"tag_id":string,"tick":integer,"epoch":integer,"camera_from_tag":[x,y,yaw]}`. It may arrive several ticks after capture. The camera frame in that observation is the one at the capture tick. The odometry frame can be offset or rotated from the room coordinates.

For this approach, use an accepted target only while its capture is recent and its epoch matches. Ignore future samples, unknown tags, timestamps you cannot transform, older samples, and discontinuous jumps beyond either configured bound after acquisition. Track the pose against the capture-time odometry and then drive from the current odometry. While a usable track is missing, request zero linear and angular velocity. Between detections, retain the latest still-valid track.

Reverse or turn to align with the target. During the approach, move forward only in a later recovery phase. Respect speed limits on every response. At switch contact, stop both axes and return `docked`. Return `failed` with zero motion at the deadline if contact has not occurred. Both terminal decisions stay at zero motion on later observations. Keep the robot within the docking approach and stop when contact is made. The configuration and observation inputs used by this interface are well formed.
