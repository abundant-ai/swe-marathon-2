# Track pose integrity through a live radio outage

The vehicle now makes turns while ranging from an off-center tag. A burst of biased ranges can look like real motion until independent evidence arrives. Track both pose and integrity, isolate a suspect radio when the data identify one, and keep a conservative estimate when they do not. Late corrections can change the active window. They cannot change a previously released estimate or reopen a retired factor. Keep the earlier commands working.

```bash
python3 -m lagfusion track-integrity --spec PACKET.json --state STATE.json --output REPORT.json
```

## Commissioned model and packet

Each packet contains `stream_id`, `sequence`, `config`, and a nonempty `events` array (up to 128 events). Use the packet idempotence, consecutive numbering, atomic writes, locking, and lost-reply behavior from `ingest`. The new command has its own state file, initially absent. It can serve multiple independent stream IDs. Each stream keeps its original config. Keep only the active graph, its observation revisions and summarized prior, and the latest request and response. Finite numbers and integer ticks exclude booleans.

- `start_tick` is a nonnegative integer. `lag_ticks` is an integer from 2 through 24, counting active poses. One pose exists at the start before any event.
- `prior_pose` is `[x_m,y_m,yaw_rad]` and `prior_covariance` is a symmetric positive definite 3×3 matrix in those coordinates. Keep yaw unwrapped in the optimize-and-report coordinates.
- `tag_in_body_m` is the 2D location of the ranging antenna in the body frame. `anchors` maps 3 through 6 distinct surveyed IDs to distinct `[x_m,y_m]` points. `radio_to_anchor` is a bijection from radio IDs to anchors. `anchor_bias_m` has one number per surveyed anchor. The maps and biases are already commissioned and stay fixed.
- `range_drop_cost` is positive and `ambiguity_cost` is nonnegative. These are costs in the objective below.

Apply events in packet order. An `advance` event has integer `tick`, `body_delta: [dx_m,dy_m,dyaw_rad]` and `sigma: [sx_m,sy_m,syaw_rad]`, all three sigmas positive. Advance by exactly one tick. If the active window is full, finalize and retire its oldest pose immediately before adding the new pose. Odometry observes the change from the preceding pose to the new one, with translation expressed in the preceding pose's body frame.

`upsert` and `retract` have `tick`, nonempty `id`, and positive integer `revision`. A measurement identity is `(tick,id)` within its stream. Upserts also have `measurement`:

- `{"kind":"range","radio":id,"value_m":number,"sigma_m":number}` uses nonnegative range and positive sigma. Predict Euclidean distance from the surveyed anchor to `position + R(yaw) @ tag_in_body_m`, plus the known bias. Evaluate each range at its own tick.
- `{"kind":"survey","pose":[x,y,yaw],"sigma":[sx,sy,syaw]}` supplies an independent lab-frame pose with positive sigmas and unwrapped yaw.

The `ingest` revision rules apply, with `expired` and `future` classified first. There are at most 24 observation identities per tick, including retracted records. A measurement may change radio or kind at the next accepted revision. The expected event reports are `advanced`, `accepted`, `retracted`, `duplicate`, `stale`, `conflict`, `expired`, and `future` in the original event order. Malformed requests, including nonadjacent advances, return nonzero and preserve any previous report and committed state.

## Integrity at a decision boundary

Compute a decision immediately before a full window retires a pose and at the end of every accepted packet. Use only accepted factors then active. Profile the nominal graph and one hypothesis dropping all active ranges from each radio currently observed. In each hypothesis, minimize half the sum of squared whitened residuals for the frozen prior, odometry and included observations. Add `range_drop_cost` once per omitted range to its minimized objective. For odometry the XY prediction is `R(previous_yaw).T @ (next_position - previous_position)` and the yaw prediction is their unwrapped difference. Surveys predict the pose directly. The inputs use an observable odometry and survey initialization and do not require a global search over arbitrary orientations.

If the second-lowest hypothesis score is within `ambiguity_cost` of the lowest, report `ambiguous` and estimate using the prior, odometry and surveys with all active ranges excluded. Otherwise use the best hypothesis. Report `nominal` for no exclusion or `isolated` with the excluded radio ID. If there is only one hypothesis, use it. Use the inverse of the undamped Gauss–Newton information for the selected estimate's covariance, including posterior coupling between poses. At exact tag–anchor coincidence use a zero range Jacobian.

At retirement linearize only the incoming prior, the motion from the oldest pose to the next pose, and that decision's included observations on the oldest pose. Linearize at the selected fitted poses and eliminate the oldest 3 coordinates by a Gaussian Schur complement. Preserve both information matrix and first-order term in a new frozen quadratic prior on the next pose. Set the additive constant so that this prior has cost zero at its own mean. Discard the retired observations permanently. Leave the other factors nonlinear and available for later revisions, even when a radio was temporarily excluded. Later evidence can change the selected model only for evidence still active.

## Report

Use the same `stream_id`, `sequence`, `status`, and `result` envelope as `ingest`. For an accepted packet, `result` contains:

- `integrity`, `fault_radio` (null except when isolated), and `profiles`, an array of `{ "excluded_radio": id_or_null, "score": number }` for every final hypothesis. Profile order is unrestricted. Null denotes the nominal graph. Exclude additive Gaussian normalization constants from all reported costs.
- `poses` lists active `{ "tick": integer, "pose": [x,y,yaw], "covariance": [[...],[...],[...]] }` rows in ascending tick order.
- `finalized` lists retired pose rows in ascending tick order, with an additional `status` and `fault_radio` for the decision at retirement. Return only the poses first finalized by this packet.
- `events` lists the disposition strings in input order.
