# Recover which commands reached the actuators

We have a frame table with action values written before commands reached the
robot. Some windows include several possible writes from the policy and the
operator. The drive receipt log is incomplete, but the recorder retained
independent encoder samples. Add an offline command that recovers each action
and its controller where the evidence identifies the write. Keep the earlier
dataset commands available.

```bash
python3 -m lerobot_repair action-qualify --dataset SOURCE.parquet \
  --ledger WRITE-LEDGER.json --output ACTION-AUDIT.parquet
```

## Frame table and write ledger

`SOURCE.parquet` is a LeRobot frame table with `index`, `episode_index`, and
`frame_index` integer columns. `index` is globally unique. Join ledger windows
by `index` and verify their episode and frame IDs. The existing `action` column
records staged proposals and cannot establish which write reached the drive.

The ledger is a JSON object with these fields.

- `model` is the path to the supplied headless SO101 MJCF relative to the
  ledger. The model's six actuator names and their order define the canonical
  axis order for this command.
- `steps_per_frame` is a positive integer number of native physics steps per
  frame. The model supplies the duration of each step. The finite, nonnegative
  `position_tolerance_rad` and `velocity_tolerance_rad_s` give the maximum
  absolute discrepancy for every observed position and velocity channel.
- `calibrations` maps IDs to records with `joints`, `scale_to_rad`, and
  `offset_rad`. The `joints` array names each model axis once. Scale and offset
  arrays use that same order. Convert each raw target by multiplying it by its
  scale and adding its offset, then arrange the values in canonical order.
- `episodes` lists records with `episode_index`, `initial`, and `windows`.
  `initial` has `joints`, `position_rad`, `velocity_rad_s`, and
  `held_target_rad`. These vectors describe the state and active drive target
  immediately before frame zero. They follow the order in `initial.joints`,
  which names every model axis once. Each episode starts from its own snapshot.
- Each episode's `windows` are in frame order, starting at frame zero. A
  window has the frame table's `index`, a nonempty `writes` array, and
  `encoder_after`. The ledger must cover every source row exactly once.
- Each candidate in `writes` has a `receipt` string unique within the window,
  a `controller` string, a `calibration` ID, and a finite six-element `target`
  vector in that calibration's order. The converted target must be within the
  model's actuator control ranges. Optional `dispatch_substep` is a zero-based
  integer less than `steps_per_frame` and defaults to `0`. Optional
  `interpolation` is `step` or `linear` and defaults to `step`.
- `encoder_after` is `null` when no sample was recorded. A recorded sample has
  `position_rad` and `velocity_rad_s`, each a six-element array in canonical
  order. Use finite numbers for observed channels and `null` for missing ones.

## Determine which histories satisfy the readback

Consider histories in which exactly one candidate write from each window
reached the actuators. Replay each possible continuation through the native
MuJoCo model. Carry the resulting integration state and target into the next
window. Measure discrepancies against `encoder_after` after the last physics
step in its window. Each available channel must be within its tolerance,
inclusively. A missing sample or value leaves that observation unconstrained.

Hold the previous drive target for the substeps before `dispatch_substep`.
With `step`, apply the full new target from `dispatch_substep` onward. With
`linear`, use the previous target plus the change toward the new target
multiplied by `(j - dispatch_substep + 1) / (steps_per_frame - dispatch_substep)`
at substep `j`, beginning at `dispatch_substep`. Both modes reach the new target
by the final substep. The initial held target applies before the first write.

Use all observations from an episode to decide its rows. Later samples can
resolve earlier choices. If two receipts remain feasible at a window, their
provenance is ambiguous even when the commanded targets agree. An episode
with no history that satisfies all available samples is inconsistent.

## Publish the audit

Write one row per source `index` in ascending order, using these columns in
this order.

| Column | Parquet type | Value |
| --- | --- | --- |
| `index` | `int64` | Source frame ID |
| `decision` | `string` | `confirmed` for exactly one feasible receipt, `ambiguous` for multiple, or `inconsistent` for no feasible history for the episode |
| `action` | `list<float64>` | For a confirmed write, its six canonical target angles in radians. Otherwise `null` |
| `receipt` | `string` | The confirmed receipt ID or `null` |
| `controller` | `string` | The confirmed controller from the ledger or `null` |
| `feasible_receipts` | `list<string>` | Distinct receipt IDs possible at this frame, sorted lexicographically. Use an empty list when the episode is inconsistent |

Publish the result atomically and preserve the inputs. Reject malformed inputs
with a nonzero exit code and preserve any existing output. Keep code for
reading records, replaying physical state, and producing audit rows in focused
modules.

Generate a small local input pair with
`python3 /app/examples/action_example.py OUTPUT_DIR`.
