# Harness workcell interface

The application reads the job as UTF-8 JSON and exchanges one JSON object per
line with the controller. Use metres, radians, seconds, newtons, and
newton-metres throughout. A pose contains `translation_m` and a unit
`quaternion_xyzw`. A pose named `base_from_board` maps coordinates in the
board frame into the robot base.

## Job

The job identifies the board and its initial nonnegative `generation`. It
gives `base_from_board`, `base_from_camera`, and `tool_from_gripper`
calibrations. `robot` names the supplied arm model and the six ordered
`joint_names`. Joint feedback and motion targets always use that order.

`cable` gives its rest `length_m`, `radius_m`, visible material marks,
rest curvature, and characterized parameters or parameter ranges. Arc
coordinate `s_m` is measured in rest metres from the anchored end. The
guide does not report an arc coordinate for an unmarked cable observation.

The `route` array lists the fixtures in order along the material. Each
entry names a fixture and its allowed `material_interval_m`. The endpoints
of the interval are inclusive. `fixtures` gives their board-relative
geometry, aperture pose, and `entry_axis_board`, pointing inward through
the mechanical opening. This direction describes physical entry over time.
The orientation of the seated cable is measured separately along increasing
material coordinate. `connector` specifies the keyed pose, approach axis,
and retention load and duration. Use the fixture models supplied with the
job to plan the clearance and approach.

`motion` gives the observation period `tick_s`, positive integer
`max_command_ticks`, six `lower_rad` and `upper_rad` values, and the
joint speed and load limits. A move can be interrupted by a plant event
before all its ticks elapse. The reported joints and command receipt are
the measured result of the applied motion.

## Observation

| Field | Meaning |
| --- | --- |
| `observation_id` | Nonempty identifier for the current captured observation. |
| `tick`, `generation` | Capture tick and board generation. Both are nonnegative integers. A generation can change when the fixture or job is revised. |
| `q_rad`, `qd_rad_s` | Six measured joint positions and velocities. |
| `wrench_tool` | Current force vector in newtons followed by the moment vector in newton-metres, both in the calibrated tool frame. |
| `cable_points` | Visible cable samples as `{point_id,position_camera_m,s_m}`. A point ID identifies a detection only for the current observation. The material coordinate is null if its mark cannot be read. Missing points are unobserved. |
| `gripper` | Grip mode `open`, `pinch`, or `slide`. Reports a readable material mark when available. |
| `clips` | Fixture IDs with their measured open or latched switches. The switch can be closed without identifying which material segment is inside. |
| `connector` | Measured keyed-seat interlock. It is separate from the clip switches. |
| `receipt` | Null before a command has an outcome. Otherwise contains `{command_id,generation,status}` using the generation that authorized the command. Status is `applied`, `interrupted`, or `rejected`. |

A revised job includes the new geometry and states which unlatched guides may
change. The new generation applies to future motion only. Keep the earlier
material constraints for each clip that remains latched.

## Response

Reply with `{observation_id,generation,command_id,status,action}`. Copy the
current observation identity and generation. Give each new logical command a
nonempty ID unique to the board job. The plant
accepts one new decision per observation. A retry uses the same command ID,
action and status. Within its original generation, the retry can refer to
the original or current observation and receives the existing receipt. It
does not move the arm again. After a board revision, issue newly planned
motion under the current generation with a new command ID.

`status` is `running`, `complete`, or `blocked`. A terminal response issues
a hold. Include a short `reason` when requested by a later checkpoint.

| Action object | Effect |
| --- | --- |
| `{kind:"move",target_q_rad,ticks}` | Request a joint target within the published position bounds for one to `max_command_ticks` observations. The actuator drives toward the target under its limits. It reports where the arm actually ended. |
| `{kind:"acquire",point_id,mode}` | Request a grasp on a visible point using `pinch` or `slide`. The gripper must already enclose the selected segment. A request cannot move the gripper or assign material at a distance. |
| `{kind:"set_mode",mode}` | Change an existing grip between pinch and slide. The cable remains constrained by the actual gripper and fixtures. |
| `{kind:"release"}` | Open the gripper. |
| `{kind:"hold"}` | Stop requested progress and retain the current grip state. |
| `{kind:"probe",target_q_rad,ticks}` | A bounded sensing move after the replacement-batch checkpoint introduces probes. Use its disclosed probe limits as well as the general motion limits. |

The plant independently determines fixture contact, clip closure, cable
movement, and keyed connector seating. Commands have no direct actuator for
clip state or interlock. The operator performs the declared retention pull
after a completed route, with the gripper released.
