# Join raw inference, teleoperation, and drive journals

Extend `/app/lerobot_repair` with an offline reconstruction of the action provenance lost during asynchronous policy rollout. Our drive bridge retained accepted transaction counters and capture times. It did not retain which policy chunk or handset command supplied each accepted transaction. Recover that relationship from the queue lifecycle, synchronized clocks, and independent joint readback. Keep the earlier dataset and `action-qualify` commands working.

```sh
python3 -m lerobot_repair reconstruct-actions --dataset SOURCE.parquet \
  --journal JOURNAL.json --output ACTION-AUDIT.parquet
```

Use focused modules for input, clock and queue reconstruction, native replay, and publication.

## Recorded inputs

The frame table has integer `index`, `episode_index`, and `frame_index`. The global `index` is unique. Frames in each episode are consecutive from zero, with up to 100 frames per episode. File row order is arbitrary. The staged `action` column does not establish what reached the drive.

In the journal, `model` is the path to the commissioned six-axis SO‑101 model relative to the journal file. Its six servo actuator names are in joint order. `steps_per_frame` is an integer from 1 to 20. Round the native model timestep to the nearest whole microsecond for clock association and multiply it by the step count for the frame period. Physics uses the original native timestep. The position and velocity readback bounds are `position_tolerance_rad` and `velocity_tolerance_rad_s`, finite and nonnegative. The `episodes` array lists up to 200 unique entries and covers the source exactly.

Each episode has the following fields.

- `episode_index` and `origin_us`. Frame zero's reference start is `origin_us`, and later starts are spaced by the frame period.
- `initial` with `joints`, `position_rad`, `velocity_rad_s`, and `held_target_rad` in the stated joint order. This is the physical state before frame zero. It carries through subsequent controller restarts.
- `clock_sync` maps clock IDs to two endpoint records each, with integer `local_us`, `ref_center_us` and `error_us`. A clock has one positive affine map through reference times in the inclusive intervals `ref_center_us ± error_us`. Both endpoint clocks increase and the reference intervals are strictly ordered. Use one choice of the two mapped endpoints for the entire episode and clock, with interpolation between them. Source timestamps are within these anchors. Endpoint uncertainty is at most 30,000 µs. A rebooted device has a distinct clock.
- `authority` records contain `boot`, `generation`, `controller` (`policy` or `operator`), and consecutive frame ranges `[start,end)`. They give the active queue epoch and cover every frame. A boot can reappear only in its adjacent ranges, and generation increases within each boot.
- `chunk_replies` and `teleop_updates` cover the whole episode. Each array has at most 24 entries in nondecreasing local time order per source clock. Every event has an `event_id`, `clock`, `local_us`, `snapshot_boot`, and `snapshot_generation`. Event IDs are unique across both arrays within an episode and may recur in another episode. Boot and clock IDs are also scoped to the episode. A policy reply also records the `snapshot_cursor`, `reported_delay` in actions, and `positions`, the canonical six-axis target sequence in radians with at most 120 actions. A handset update has the same fields, with zero cursor and delay and one six-axis target. Event IDs, boot IDs and clock IDs use letters, digits, underscores or hyphens. Timestamps and counters are nonnegative whole microseconds or counts, below 2⁵³.
- `accepted` is the drive bridge's accepted transaction journal. Entries have `boot`, `counter`, `clock` and `local_us`. Accepts are consecutive from zero within each boot and restart at zero when the device reboots. There is one distinct accepted transaction per frame in counter order for its boot. The journal can be out of order, with exact copies that count once. Conflicting duplicates are invalid. The bridge counters contain no policy ownership or target payload.
- `encoders` maps decimal frame index strings to optional end-of-frame observations. Each value has `position_rad` and `velocity_rad_s` in native joint order. Either array may be null. Individual channels may also be null.

## Queue and drive replay

A queue event becomes visible for the first frame start at or after its aligned time. A placement in a discrete frame or substep is consistent when the aligned reference time lies in the closed integer-microsecond range from the previous boundary plus 1 through that boundary. Process events that share a frame in journal order for their source. All placements must be consistent with the same affine clock for each clock ID and the event order. Queue events in the export have a placement inside the recorded frame range.

Reset the queue, cursor, and active handset value on a boot or generation change. Discard an arriving payload from a retired epoch or an inactive controller source. On a policy reply, skip `min(reported_delay, cursor - snapshot_cursor)` entries before replacing the pending queue. The live cursor counts actions popped since the epoch started. A negative cursor difference is impossible. An accepted policy write pops exactly one queue entry. In an operator epoch use the latest valid handset target, including repeated sends of that target. An empty required queue or missing handset target is incompatible with an accepted write. The position values must stay inside the model's actuator ranges.

Use the accepted timestamp to determine which substep of its frame can latch the write. Hold the previous target for earlier substeps and use the new target for every remaining substep. Advance the native MuJoCo model through all substeps. A history must match each recorded end-of-frame encoder channel within its inclusive tolerance, satisfy all queue and clock constraints, and reach the end of the episode. Consider how later evidence can rule out an earlier owner. Two producers can remain feasible even if they issued identical joint targets.

## Publish the results

Write one row per source `index` in ascending order. Use the following column order.

| Column | Type | Value |
| --- | --- | --- |
| `index` | int64 | Original source frame ID |
| `decision` | string | `confirmed` for one feasible producer, `ambiguous` for several, or `inconsistent` for no complete history |
| `action` | list<float64> | Confirmed producer's canonical target, or null |
| `receipt` | string | Confirmed producer ID, or null. Use `EVENT_ID:OFFSET` for a policy action, with zero-based offset in the original chunk, or `EVENT_ID` for a handset update. |
| `controller` | string | Confirmed `policy` or `operator`, or null |
| `feasible_receipts` | list<string> | Distinct feasible producer IDs in lexicographic order |
| `device_boot` | string | Bridge boot ID of the frame's accepted transaction |
| `device_counter` | int64 | Bridge transaction counter for that boot |
| `feasible_dispatch_substeps` | list<int64> | Sorted distinct feasible zero-based latch substeps |

An inconsistent episode has null confirmed fields and empty feasibility arrays in every row. Distinguish that evidence outcome from malformed inputs, which exit nonzero. Publish the Parquet file atomically and preserve the source files and any existing report if input validation fails.
