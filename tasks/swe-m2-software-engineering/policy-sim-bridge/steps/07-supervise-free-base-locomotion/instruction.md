# Supervise a walking policy on a free-base target

Deploy a published 12-joint locomotion actor on a free-base quadruped. The controller must keep its actor and joint mappings exact while current support, slip and command ownership change during real simulated motion. Keep earlier commands and behaviors.

Implement `python -m policy_bridge locomote --spec MANIFEST.json --state DIRECTORY`. Consume one NDJSON observation and flush one NDJSON reply per line. Use the public [starter fixture](../../environment/example/locomotion/README.md) under `/app/example/locomotion` to exercise the protocol locally. NumPy and CPU ONNX Runtime are installed. Use the published frozen ONNX weights given by the manifest.

## Manifest

| Field | Meaning |
| --- | --- |
| `actor`, `actor_sha256` | ONNX file path, relative to the manifest when needed, and its SHA-256 |
| `policy_joints`, `default_positions_rad` | Twelve canonical joint names and their nominal positions in actor order |
| `joint_sensors` | Independent wire order of twelve `{joint,sign,zero_rad}` objects with sign −1 or +1 |
| `actuator_order` | Target bus order of those twelve joint names |
| `command_scale`, `max_command_abs` | Three component scales for the actor and magnitude limits for requested forward, lateral and yaw commands |
| `max_lease_ticks`, `max_contact_age_ticks` | Inclusive upper limits for new lease expiry and per-foot measurement age |
| `normal_min_n`, `slip_limit_mps`, `min_support_feet` | Thresholds for loaded support, slip and a qualifying support frame |
| `limit_factor`, `recovery_ticks`, `rearm_ticks`, `max_tilt_rad` | Speed scale and consecutive evidence counts for recovery and rearming, and torso tilt limit |

## Observation and authority

An observation contains integer `tick`, wire vectors `joint_position_rad` and `joint_velocity_rad_s`, scalar-last nonzero `q_xyzw` from body to world, three-vector `gyro_world_rad_s`, `contacts` and `request`. The policy period is 20 ms. Normalize quaternion signs and rotate world gravity `[0,0,-1]` and angular velocity to body coordinates. For a wire sample compute canonical position as `sign*wire_position + zero_rad` and canonical velocity as `sign*wire_velocity`.

Each contact is `{foot,capture_tick,normal_force_n,tangent_speed_mps}`. Feet are `FL`, `FR`, `RL`, `RR`. Force and speed are nonnegative. Ignore invalid contacts and captures outside `[tick-max_contact_age_ticks,tick]`. Retain the greatest accepted timestamp per foot, with the first sample winning at equal timestamps. Only fresh retained samples count. The body has live contact telemetry with at least three fresh feet. The support list contains fresh feet with load at least `normal_min_n`. Slip occurs when any supporting foot has tangent speed above `slip_limit_mps`. A qualifying frame has live telemetry, acceptable tilt, enough supporting feet and no slip. Count consecutive qualifying frames, resetting on a failed frame.

A request is null or an object `{sequence,valid_until_tick,velocity}`. Accept a nonnegative sequence strictly newer than the most recently accepted request with expiry in `[tick,tick+max_lease_ticks]` and a finite body twist within the manifest limits. Ignore invalid and older requests, including attempts to extend the same sequence. Sequence, validity and motion authority persist across process death.

1. Start unarmed. If an accepted lease expires, retire its sequence and stop. When armed, loss of live telemetry or excessive tilt retires the current lease and disarms the controller. A newer request received while already stopped can wait for evidence until its own expiry.
2. When stopped, arm on an unexpired lease newer than all retired leases after `rearm_ticks` consecutive qualifying frames.
3. While armed, use `track` and the requested twist. Loaded slip latches `limited`, multiplying all three requested twist components by `limit_factor`. Restore `track` after `recovery_ticks` consecutive qualifying frames. Stop clears the slip latch and uses zero requested twist. A stopped robot still runs the balance actor.
4. A retired lease cannot regain authority. The simulator can restore good foot packets before the client submits a fresh lease.

## Frozen actor and durable output

At every accepted tick, including stopped ticks, construct six float32 terms in this order.

| Term | Coordinates |
| --- | --- |
| Body angular velocity | 3, multiplied by 0.25 |
| Projected gravity | 3, body-frame down vector |
| Effective body twist | 3, multiplied by `command_scale` |
| Centered joint position | 12, actor order with nominal positions subtracted |
| Joint velocity | 12, actor order multiplied by 0.05 |
| Previous clipped action | 12, actor order |

Maintain ten frames per term, oldest first, with missing startup history and the previous action filled with zeros. Flatten each term's history separately, then concatenate the six histories into float32 `[1,450]`. Evaluate the network and clip each action to `[-100,100]`. Emit angles in target-bus order after adding `0.25 * action` to canonical nominal angles.

Return `{tick,mode,lease,support,effective_twist,action,target_rad}` where the support names are sorted and the lease is the active sequence in `track` and `limited`, or null in `stop`. Store the manifest and actor identity, contact and lease state, previous action, actor history and last complete response durably before sending a new reply. Initial tick is zero, and new ticks must be contiguous. A retry of the latest identical parsed observation returns its identical reply after any restart without advancing state. Older, altered same-tick and skipped future events emit `mode:"rejected"`, `support:[]`, and null lease and numeric arrays, with no state change. Incompatible manifest or actor identity fails before modifying an existing session.

## Physical qualification

The verifier applies only the submitted target bus to the free-base native Go2. The underlying motor loop runs at 5 ms with published position feedback gains and directional torque-speed limits. Visible foot samples come from measured loaded contacts. Successful missions require exact actor decisions and actuator ownership, actual travel followed by a physical stop, native friction contact and safe torso clearance. One mission induces loaded slip and checks return to tracking. Others interrupt motion through a telemetry blackout and unclean restart or expire a motion lease during a route. A stationary robot cannot pass the travel requirement. Safety gate examples include body height above 0.16 m, tilt below 0.68 rad, zero loaded nonfoot contacts, and ending forward progress above 2.35 m with terminal horizontal speed below 0.12 m/s.
