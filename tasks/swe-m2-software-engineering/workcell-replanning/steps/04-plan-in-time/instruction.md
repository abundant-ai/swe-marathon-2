# Plan a loaded move around tracked fixtures

The fixture controller can now send forecasts for moving clamps and transfer
fixtures. We need a timed recovery plan from the encoder position and velocity
at the interruption. Extend the offline workcell package in `/app/workcell` and
keep the three existing commands working. Keep the planning and geometry code
modular so we can call both from the execution supervisor.

```bash
python3 -m workcell plan-window --spec SPEC.json --output REPORT.json
```

## Forecast and motion window

The spec uses the existing `robot` model. Its `scene` has two arrays, `fixtures`
and `payload`. Each entry is a capsule in the earlier format. Fixture
coordinates are in the world frame. Payload coordinates are in the tool frame.
There may be several capsules on the same load or none. Each entry of
`moving_fixtures` has a positive `radius_m` and a nonempty `keyframes` array
of `{"tick":integer,"a":[x,y],"b":[x,y]}` records with strictly increasing
nonnegative ticks. Interpolate each world-frame endpoint linearly between
keyframes and hold the endpoint constant outside the keyframe range.

- `tick_seconds` is the positive number of seconds per tick. The nonnegative
  integer `measured.tick` is the start of the planning window. `deadline`
  is the inclusive final tick, at most 128 ticks after that reading.
- `measured.q` and `measured.dq` are three numbers each in joint order.
  `dq` is in metres or radians per second.
- `limits.velocity` and `limits.acceleration` are arrays of three positive
  per-axis limits in joint units per second and per second squared.
  Use the lower of `limits.velocity` and `robot.max_speeds` on each axis.
- `nodes` maps taught pose IDs to joint positions. Each member of `edges`
  has a unique `id`, a `source` and `target` node ID, and a positive integer
  duration in `ticks`. Edges are directed. The graph can offer several
  transfers between the same nodes.
- `start_node` is the required rest position after braking. `goal_node` is
  the delivery position. `brake_ticks` is a nonnegative integer.
- `margin` is the minimum capsule separation in metres, given as a
  nonnegative number. Check both links and all carried capsules against all
  static and tracked fixtures. Check each carried capsule against the upper
  arm. Forearm contact with the load and contact within the load are allowed.

## Controller motions

Commands start and end at integer ticks. Joint and clearance limits apply at
every instant of a command, including its endpoints and times between ticks.

1. Brake first if the measured velocity is nonzero. Over
   `T = brake_ticks * tick_seconds` seconds use
   `q(t) = measured.q + measured.dq * t * (1 - t/(2*T))`, with elapsed seconds
   `0 <= t <= T`. This ends at zero velocity and must reach the taught
   `start_node` within `1e-8` on each axis. For a stationary measurement,
   `brake_ticks` is zero and the reading already matches `start_node`.
2. Wait at a taught node when it is safe to hold there for the whole wait.
3. Execute a directed transfer in its specified duration. Use
   `q = q_start + (q_end - q_start) * (3*u*u - 2*u*u*u)`, where `u` is
   the elapsed fraction of the transfer. Each transfer begins and ends at rest.

Return `{"status":"ready","commands":[...]}` for a feasible route to the goal
by the deadline. Consecutive commands share an endpoint in both time and
position. A route is complete at its first arrival at the goal. The command
formats are as follows.

```json
{"kind":"brake","start":0,"end":2,"node":"start"}
{"kind":"wait","start":2,"end":4,"node":"start"}
{"kind":"move","start":4,"end":12,"edge":"crossing"}
```

Return `{"status":"blocked","commands":[...]}` if there is no feasible trip.
For a blocked trip, brake if needed and hold the start node through the
deadline. If the initial state or that fallback cannot be certified safe,
return an empty blocked command list so the machine controller can invoke
its external stop procedure. An empty ready list is valid when a stationary,
safe measurement is already at the goal.

Use the same malformed-input and atomic-output rules as the earlier commands.
Treat a well-formed pose or primitive that violates a physical bound as
unavailable for planning. The same applies if the braking measurement fails
to reach `start_node`.
