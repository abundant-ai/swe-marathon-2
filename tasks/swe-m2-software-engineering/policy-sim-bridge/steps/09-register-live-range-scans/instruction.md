# Repair the walking robot’s map from delayed range scans

The inspection robot now has its calibrated planar scanner, relative odometry, and the frozen Go2 walking actor. It no longer receives surveyed live poses or obstacle rectangles. Build navigation geometry from a prior teaching traversal and live raw scans, track the map-to-odometry transform, and recover from stale scans and an odometry reset. Reuse the earlier actor and preserve the previous commands.

```bash
python3 -m policy_bridge navigate-scans --spec MANIFEST.json --state STATE
```

## Manifest and sensing

The base manifest and proprioception, contact and actor conventions are those of `locomote`. The `scan_navigation` object contains:

- `extent` as `[xmin,xmax,ymin,ymax]` in the survey map, `goal` as `[x,y,heading_rad]` in that frame, `footprint_radius_m`, `max_speed_mps`, and the inclusive `completion_tick`. The extent defines the site's operating boundary.
- `body_from_lidar` as `[x_m,y_m,yaw_rad]`, the calibrated planar transform that maps lidar points into the robot body. `angle_min_rad`, `angle_step_rad`, `beam_count` and `range_max_m` define the beam fan. Body x points forward, body y points left, and yaw increases counterclockwise. Beam index `k` has scanner-frame bearing `angle_min_rad+k*angle_step_rad`. The scanner reports a gravity-leveled planar slice. A finite beam length denotes a surface hit. Null denotes no hit out to `range_max_m`. All beams in one scan share a capture time.
- `teach_anchor` as the surveyed pose `[x,y,yaw]` of the teaching traverse's first base frame. Top-level `teaching` is an ordered list of `{delta,ranges_m}` records. Each `delta` is an SE(2) increment `[dx_m,dy_m,dyaw_rad]` expressed in the previous body frame. Apply it to reach that record's acquisition pose. Its first delta is zero. `ranges_m` is the raw beam array at that pose. The dock start of the live run uses the same anchor. Obstacles may move after teaching.
- `max_scan_age_ticks` is the inclusive maximum age of a registered scan at a 20 ms policy tick. `resolution_m` is a site mapping scale. Your registration, map representation and planning algorithm can differ from a regular occupancy grid.

Each contiguous tick carries the existing joint, IMU and contact observations, plus `odometry` as `{"epoch":int,"delta":[dx_m,dy_m,dyaw_rad]}` and `scans` as a possibly empty list of `{"epoch":int,"capture_tick":int,"ranges_m":[...]}`. There is no caller motion request. The IMU yaw frame is arbitrary and can change when odometry resets. Roll, pitch and body angular velocity remain available to the frozen actor by using the supplied quaternion and angular velocity together.

Odometry provides a relative body-frame step from the preceding policy tick. A new odometry epoch starts at its own origin with a zero delta. No surveyed pose is supplied when the robot is reset or moved during service. Scan association uses the odometry at the scan's acquisition tick in that scan's epoch. A scan can arrive late, out of order, or after its epoch has been retired. Missing, expired, future and retired-epoch evidence cannot grant motion. A later arrival with an older capture must not rewind the last accepted time in the current epoch. Hold after an epoch change until a current-epoch scan establishes the new relationship to the map. Use valid observed geometry to update navigability after a change. The robot must stay outside measured obstacles and the site boundary with the declared footprint, including when a previously blocked lane opens.

## Replies and recovery

Return the existing actor fields and add these entries:

| Field | Value |
| --- | --- |
| `navigation` | `navigate`, `hold` or `arrived` |
| `intent` | Body-frame motion lease sent to the frozen actor, with `sequence` equal to the current tick, `valid_until_tick` equal to tick plus one, and finite `velocity` within the actor and course limits |
| `localization_epoch` | The current odometry epoch |
| `accepted_scan_tick` | Last accepted capture in the current epoch, or null before registering a current-epoch scan |
| `pose_map` | Current estimated base pose `[x,y,yaw]` in the map frame, or null while an epoch has no alignment |

Use a zero twist for `hold` and `arrived`, with the balance actor still running. A stale scan cannot authorize movement. Persist sufficient map, registration, sensor history, actor state and receipt before replying. The exact latest request after worker death returns the same response. An altered retry, earlier tick or skipped future tick returns the checkpoint-seven rejection object and leaves state unchanged.

Reach the map goal within 0.17 m and 0.16 rad while reporting `arrived` and keeping native speed below 0.085 m/s for 22 consecutive ticks. The evaluator compares reported map poses to independent native measurements. The 95th-percentile position and heading error limits during qualified motion are 0.14 m and 0.18 rad. The first recovered pose after a reset must be within 0.16 m and 0.18 rad. Both mirrored missions have the same goal. Physical collisions, clearance, scan freshness, and replay are observed independently. The final reward retains 20% of checkpoint eight and gives 80% to the two equally weighted raw-scan missions.
