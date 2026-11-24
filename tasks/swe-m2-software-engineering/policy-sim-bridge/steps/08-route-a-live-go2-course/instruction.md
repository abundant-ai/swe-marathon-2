# Route a walking robot through live aisle changes

Bring the Go2 bridge onto a shared laboratory course. Our scanner
publishes delayed poses and revised aisle bounds while the base is
already walking. The bridge chooses its own body-frame velocity through
the existing frozen actor. It must find a detour when a passage closes
and physically hold when the live map expires. Keep the earlier commands.

```bash
python3 -m policy_bridge navigate --spec MANIFEST.json --state STATE
```

This stream uses the checkpoint seven manifest, proprioception, contact
and durability conventions. The added `course` manifest fields are
`extent` as `[xmin,xmax,ymin,ymax]`, `goal` as `[x,y,heading_rad]`,
`footprint_radius_m`, `max_speed_mps`, `max_pose_age_ticks`,
`max_map_age_ticks`, `max_map_lease_ticks`, and the inclusive
`completion_tick`. The extent and positions
are in the surveyed world frame. The robot's body x axis points forward.

## Live input

For each contiguous tick, the earlier fields carry joint, contact and IMU
observations. There is no caller-provided motion request. Two new fields can
be null or populated.

- `localization` gives `capture_tick`, `position` as `[x,y]`, `heading_rad`,
  and `velocity` as surveyed `[vx,vy]`. Its age cannot exceed
  `max_pose_age_ticks`. Only a newer capture can replace the retained one.
- `map` gives integer `revision`, `capture_tick`, `valid_until_tick`, and
  `obstacles`. Each obstacle is an axis-aligned closed rectangle
  `[xmin,xmax,ymin,ymax]`. Treat the map as the full occupancy snapshot.
  Accept a nonnegative revision and a fresh capture. An equal revision
  can renew the map only with identical rectangles and a newer capture.
  Its expiry must be between the current tick and
  `capture_tick + max_map_lease_ticks`, inclusive. An older revision
  cannot replace a newer one, including after restart.

An accepted localization or map can remain usable on ticks with null
updates until its respective age or expiry bound. Stop issuing motion
when either loses authority or no route is currently clear. Keep the robot
outside obstacles and the site boundary with its declared footprint.
Plan from the measured pose with room for actuation and observation delay.
The scanner reports changes early enough to allow a feasible response.

## Output and verification

Return the checkpoint seven actor output fields and add
`navigation`, `map_revision` and `intent`. Use navigation mode
`navigate`, `hold`, or `arrived`. Report the most recently accepted
map revision, or null before the first accepted map. The `intent` is the
motion lease submitted to the frozen actor. Its sequence equals the tick,
its expiry is tick plus one, and its `velocity` is a body-frame twist
within the manifest limits. Planar speed must also fit the course limit.
Use a zero intent for `hold` and `arrived`. A stopped robot still runs
the balance actor.

Reach the surveyed goal within 0.17 m and 0.16 rad and report `arrived`
while measured planar speed stays below 0.085 m/s for 22 consecutive
20 ms policy ticks by `completion_tick`. Persist the navigation state, frozen actor state,
and latest accepted response before replying. Replaying the latest
identical input after process death returns the exact same response.
Earlier, changed and future-tick packets return the checkpoint seven
rejection object and preserve the session state.

The verifier integrates the submitted actuator targets on native Go2,
checks the policy output against the issued intent, and measures physical
motion and obstacle clearance. Missions contain traversable detours, a
reflected course, and a loss of map authority followed by a fresh map after
an unclean restart. The task reward retains 20% of checkpoint seven and
gives 80% to the three equally weighted complete course missions.
