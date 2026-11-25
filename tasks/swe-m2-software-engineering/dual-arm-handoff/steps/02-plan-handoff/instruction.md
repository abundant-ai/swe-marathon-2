# Route both arms through a timed handoff

The cell has commissioned paired poses, directed motion segments, and
transfer stations. It can wait for a fixture window, choose a detour in
three dimensions, or brake from an interrupted move. Add a planner.
Keep the spatial certifier available.

```bash
python3 -m dual_arm plan --spec SPEC.json --output REPORT.json
```

The planning spec carries over `arms`, `payload`, `fixtures`, `margin`
and `tick_seconds` from the motion checker. The measured record supplies
the current owner and joint state.

- `nodes` maps nonempty IDs to paired poses in the motion checker format.
  `edges` is an array of `{"id": ..., "from": node, "to": node, "ticks": positive_integer}`.
  A move uses the same rest-to-rest interpolation as the certifier.
- `handoffs` is an array of `{"id": ..., "node": node, "from": arm, "to": arm, "ticks": positive_integer}`.
  Distinct arms must be named. Hold the pose during the operation. The
  two tool-frame payload shapes must agree in world endpoints and
  radius within `1e-7`. Maintain clearance. Ownership changes at the
  operation's end. IDs are unique within each array.
- `measured` gives `tick`, paired joint `pose`, paired joint
  `velocity`, and `owner`. `start_node` is a string ID in `nodes`.
  Its paired pose matches the measured pose at rest or the required
  stop pose after braking.
- `brake_ticks` is zero when starting at rest. Otherwise brake for
  that positive duration with constant deceleration from the measured
  velocities to zero. The displacement is half the initial velocity
  times the duration in seconds. The stop must match the pose at
  `nodes[start_node]` within `1e-7` per coordinate and satisfy the same
  motion limits and continuous clearance. The owner stays the same
  during braking.
- `goal_node` is the destination string ID in `nodes`. `goal_owner`
  is the required holder at completion. `deadline` is the latest
  completion tick, at most 80 ticks after the measurement.

Return `{"status":"ready","commands":[...]}` for any safe completion
by the deadline. Otherwise return `{"status":"blocked","commands":[]}`.
The controller uses that outcome to stop automatic dispatch. Every
command contains its integer `start` and `end`. Commands are contiguous,
with these additional fields.

- Brake when required using kind `"brake"` and `node` set to the stop node.
- Wait using kind `"wait"` and `node` set to the current node. Hold with
  clearance throughout. A wait takes one or more ticks.
- Move using kind `"move"` and the chosen `id` from `edges`.
- Transfer using kind `"handoff"` and the chosen `id` from `handoffs`.

The first command starts at measurement time. An empty ready plan is
valid at a safe goal pose with the correct owner and both arms at rest.
Keep search, kinematics and wire-format handling modular.
