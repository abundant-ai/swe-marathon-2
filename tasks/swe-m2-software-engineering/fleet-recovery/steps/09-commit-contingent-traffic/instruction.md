# Commit a safe delivery approach before traffic and lift outcomes are known

Extend `/app/fleet_recovery` so two couriers can keep a delivery slot when both an independently operated carrier and a lift service may be delayed. Before either outcome is known, commit only the movement that can run in every advertised history. When the carrier's live itinerary arrives, choose the crossing movements without assuming a lift outcome. Once the lift supervisor announces the actual sessions, send each courier to a reachable cabin. A cabin timetable allows approach to its door. Boarding also needs current door and floor readback and the courier's measured pose.

Keep the earlier commands working. Use the installed Open-RMF library for native interpolation, continuous traffic conflicts and joint proposal reconciliation. Separate the policy search, movement authority and durable receipt handling in focused modules.

## Command and site

Run `python3 -m fleet_recovery rmf-contingent --site SITE.json --state JOURNAL.json --event EVENT.json --output REPLY.json`. Each invocation handles one event. The caller sends events serially with a unique string `request_id`, a nonnegative integer `now_ns` in mission time, and a `kind`. First-seen event times are nondecreasing. Persist accepted observations, issued commands and the exact reply before publishing the response. Retrying the same request and body returns the original response without issuing a second logical command. Reusing the ID with different content or supplying a malformed event is a nonzero exit with no state change. A fresh journal starts with a `start` event at time zero.

The site includes `map`, integer nanosecond `slot_ns`, `max_time_ns`, `carrier_observe_ns` and `lift_observe_ns`. The observations occur in that order, and the lift observation may arrive while a courier is already in the crossing. Plan over at most 128 departure slots. The site supplies at most eight carrier alternatives, cabins and lift outcomes each. Times are in the same mission clock. Each pose is `[x_m,y_m,yaw_rad]`. Each `profile` has the positive fields `radius_m`, `linear_velocity_mps`, `linear_acceleration_mps2`, `angular_velocity_radps` and `angular_acceleration_radps2`, as in the previous checkpoint.

- `couriers` maps two courier IDs to `{profile,home,stage,goal,deadline_ns}`. `goal` is the far side of the crossing. Every courier moves home-to-stage and stage-to-goal and then from that exit to its assigned cabin door.
- `carrier` contains `{id,profile,home,stage,goal,options}` with a separate participant ID. Its common committed movement leaves `home` at time zero and stops at `stage`. It waits there until the departure named by its actual option, then moves to `goal`. The `options` map associates each option with `{plan,departure_ns}`. The alternatives are full possibilities and the initial packet gives no selected option.
- `cabins` maps a cabin ID to `{doors,ride_ns}`. Each `doors` map gives the door pose for each courier. `lift_options` maps each possible lift schedule to `{version,slots}`. Its `slots` maps cabin ID then courier ID to `{session_id,board_ns,floor}`. A slot is usable only if the selected courier is at its door by `board_ns`, finishes the ride by its deadline, and sees a current matching door observation. At most one courier occupies a cabin during a half-open interval `[board_ns, board_ns + ride_ns)`. The carrier and lift alternatives are independent. Every combination must work for an approved policy.

Use native Open-RMF rest-to-rest interpolation between the named poses, including waits. Approach, crossing and cabin-door travel starts are on the site grid. Calculate finish times to within 10 ns of native interpolation. After arriving at any pose, retain its occupied footprint until the next movement. On this floor retain the cabin-door footprint through the horizon for conservative clearance. Avoid contact between any two circular footprints throughout the complete physical trajectories, including waits and motion already issued before a new observation. Cabin service slots are external appointments and can be off the movement grid.

## Policy and events

The initial reply contains a policy that delivers both couriers by their own inclusive deadlines in every history. If none exists, reply with `status:"blocked"`, `policy:null` and empty `commands`. A feasible policy has `status:"ready"` and uses this structure:

```text
policy
  approaches[courier] = {start_ns, end_ns}
  after_carrier[option]
    crossings[courier] = {start_ns, end_ns}
    after_lift[option]
      dock[courier] = {cabin, start_ns, end_ns, board_ns, arrival_ns}
```

Every approach finishes by `carrier_observe_ns`. A crossing starts at or after that observation and after its approach. The chosen pair is shared across both lift outcomes for the same carrier. Dock travel starts at or after `lift_observe_ns` and after that courier's crossing. A `start` event issues the two common approach commands. Later replies retain the same policy. Release only these commitments as the relevant event arrives:

- `carrier` adds `{option,plan,pose}`. Accept a known option only at or after `carrier_observe_ns`, with its plan ID and a carrier within `1e-6` m of its stage in the plane. Issue the two crossing commands for the selected branch once, provided their starts are still current or future.
- `lift` adds `{option,version}`. Accept a known option only after carrier selection, at or after `lift_observe_ns`, with that option's version. Issue the two dock commands for its continuation once, provided their starts are still current or future.
- `door` adds `{courier,cabin,session_id,floor,open,pose}`. Board only at that courier's `board_ns`, after the lift has been selected and the courier has reached the assigned door. Require the matching cabin, booked session, floor, `open:true`, and a measured courier within `1e-6` m of that door in the plane. Do not issue a second boarding command for the same courier.

A well-formed early, stale, out-of-order, wrong-session or wrong-position observation emits no commands and leaves the current selected branch unchanged. No later observation retracts a movement already issued. The simulator provides current authoritative observations at the advertised times for executable policies.

Each reply is `{status,policy,commands}`. A movement command is `{kind,courier,start_ns,end_ns}`, where `kind` is `approach`, `cross`, `dock` or `board`. Dock and board commands also contain `cabin`. A board command contains `session_id` and runs from the exact booked boarding instant through the quoted ride end. The caller deduplicates retried replies by their request ID. The program chooses any physically safe policy meeting every stated deadline.

[Open-RMF traffic negotiation](https://github.com/open-rmf/rmf_traffic/blob/main/rmf_traffic/include/rmf_traffic/schedule/Negotiation.hpp) · [Open-RMF lift-session workflow](https://github.com/open-rmf/rmf_ros2/issues/382)
