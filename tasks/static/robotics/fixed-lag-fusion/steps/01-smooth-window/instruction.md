# Fuse delayed measurements in a bounded pose window

We are recording a cart with wheel odometry, an inertial navigation unit, and fixed radio anchors. The research team needs to compare the live, recent trajectory with a surveyed reference. Measurements often arrive after later acquisitions. Build an offline workbench that can revise a recent pose while preserving information from poses that have already left memory.

Implement a modular Python package under `/app/lagfusion` and run it with Python 3.12.

```bash
python3 -m lagfusion smooth --spec SPEC.json --output REPORT.json
```

## Input model

The spec contains `config` and `events`. A pose is a 2D translation in metres in a fixed laboratory frame. A tick is a nonnegative integer acquisition-time index. Process events in array order.

- `config` has `start_tick`, `lag_ticks` from 1 through 24, `prior_mean`, `prior_covariance`, and `process_covariance`. Means and other 2D vectors are JSON arrays of two numbers. Covariances are symmetric positive-definite 2-by-2 arrays in square metres. The prior is on the pose at `start_tick`.
- An event with `op: "advance"` has an integer `tick` greater than the current watermark. The initial watermark is `start_tick`. Create each intervening state with an independent zero-mean Gaussian displacement prior from its predecessor using `process_covariance`. The active window includes every tick from `max(start_tick, watermark-lag_ticks)` through the watermark. Marginalize expired states while preserving their information and correlations in the retained states. A run advances at most 4096 ticks.
- `op: "delta"` observes `pose[tick]-pose[tick-1]` with `value` and `covariance`.
- `op: "position"` observes `pose[tick]` with `value` and `covariance`.
- `op: "projection"` observes the dot product of `pose[tick]` with a nonzero 2D `axis`, with scalar `value` and positive `variance`. Use the axis and variance as supplied.
- `op: "snapshot"` has a nonempty string `label` and requests the current posterior.

Treat supported observations as independent. A factor whose earliest needed tick precedes the active window expires. Otherwise if its latest tick is beyond the watermark it is future. Do not add expired or future factors or move the watermark for them. Repeated ordinary observations are separate evidence. All numerical inputs are finite and booleans are excluded.

## Output

Write `{"outcomes":[...],"snapshots":[...],"final":{...}}`. Each outcome is an object containing `status` with value `advanced`, `accepted`, `expired`, `future`, or `snapshot`, in input order. Each snapshot has its requested `label`, the current `watermark`, and `states` in increasing tick order. Each state has `tick`, `mean`, and its full 2-by-2 marginal `covariance`. The `final` object has the same watermark and states, without a label.

The posterior must use exact linear-Gaussian marginalization to ordinary floating-point accuracy. Keep the working numerical state within the window and its summarized prior as the watermark advances. Reject malformed inputs with a nonzero exit and leave any existing output unchanged.
