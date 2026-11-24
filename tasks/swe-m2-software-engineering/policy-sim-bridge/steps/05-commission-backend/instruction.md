# Commission an export with an undocumented axis map

The new simulator exposes encoder and actuator labels without a reliable mapping to the actor's joint names. Its clock also differs slightly from the commissioning rig. Recover the joint map and clock from a paired motion capture. Keep the existing commands working. Use the fitted calibration on a separate validation capture before handing it to the deployment controller.

```bash
python3 -m policy_bridge calibrate --spec SPEC.json --output CALIBRATION.json
```

## Captures

The spec includes `joint_names` and `action_order`, distinct canonical names in their respective array orders. `action_order` is a nonempty subset of the joint names. `sensor_order` and `actuator_order` list the target simulator's independent channel names. Extra target channels can be present. Each rig and target sample carries integer `time_ns` on its device's clock. Each sequence is strictly increasing. There are at most eight canonical joints and at most 12 labels on either target bus.

- `fit` and `validation` each contain `reference` and `target` arrays. The reference rows have `position`, `velocity`, and `control` in `joint_names`, `joint_names`, and `action_order` respectively. The target rows have these arrays in `sensor_order`, `sensor_order`, and `actuator_order`. Positions and control targets are radians. Velocities use radians per second.
- `clock` contains integer `anchor_ns`, nonempty distinct integer arrays `offsets_ns` and `rates_ppm`, and positive integer `max_gap_ns`. The grid has at most 81 pairs. Rates are greater than -1000000. For a clock candidate, map each target stamp `t` to `t + offset_ns + floor((t - anchor_ns) * rate_ppm / 1000000)`. A reference row at that exact time is usable directly. Otherwise interpolate all reference channels linearly if bounded by two reference samples and each bracket is within `max_gap_ns`. Use no extrapolation.
- `limits` contains integer `min_pairs` of at least 3, `min_coverage` in (0,1], positive `velocity_weight_s`, nonnegative `ambiguity`, and nonnegative `max_position_rmse`, `max_velocity_rmse`, and `max_control_rmse`. Coverage is the fraction of all target rows matched by the candidate clock.

## Fit and qualify

Fit using only `fit`. For every clock candidate meeting both overlap limits, fit an injective mapping from canonical joints to sensor slots and a sign in {-1,1} per joint. For a paired fit sample and a proposed binding, let the difference be `target_position - sign * reference_position`. Its mean over the matched fit rows is the fitted `zero`. Minimize squared position residual after subtracting zero plus squared velocity residual weighted by `velocity_weight_s ** 2`. The assignment cost is the mean of those sums over matched rows and canonical joints.

Among all clock, sensor assignment and sign hypotheses with coverage, choose the lowest cost. Treat the fit as ambiguous if the second distinct hypothesis is within `limits.ambiguity` of the best cost, inclusive. Once the clock and sensor map are resolved, independently fit an injective binding from action names to actuator labels. For an action's fitted sign and zero, compare `zero + sign * reference_control` to the observed actuator slot. Minimize mean squared residual over rows and actions. Apply the same ambiguity test to the best two actuator assignments.

Use the fitted result unchanged on `validation`. Report RMSEs over all matched rows and mapped channels for position, velocity, and control, separately, without velocity weighting. Count and enforce holdout overlap. An insufficient validation overlap or any RMSE above its limit makes the report `validation_failed`; keep the fit in that report for diagnosis. No fit candidate with overlap is `insufficient_overlap`. An unresolved sensor, clock or actuator solution is `ambiguous`.

Write the fields shown below. In `insufficient_overlap` and `ambiguous`, both fit fields and `metrics` are null. Report `validation_pairs` as zero in those cases. For a fitted result, report the actual validation pair count and metrics, or null metrics if there are no pairs.

```json
{"status":"ok","clock":{"offset_ns":0,"rate_ppm":0},"mapping":{"hip":{"sensor":"enc9","sign":-1,"zero":0.12,"actuator":"position3"}},"validation_pairs":100,"metrics":{"position_rmse":0.0,"velocity_rmse":0.0,"control_rmse":0.0}}
```

Mapping entries for canonical joints outside `action_order` have null `actuator`. Reject malformed dimensions, references, timestamps, numbers, or grid limits with nonzero exit and keep any existing report intact.

## Run with the qualified map

Extend `stream` with an optional `--calibration CALIBRATION.json` argument. Read a successful report before opening the session. Replace the base spec's sensor names and signed zero conversions with the calibration mapping. Retain canonical references from `joints`. Replace each action's actuator name, preserving its scale and target bounds. Reject a non-`ok` calibration or a map that does not validate against the deployment manifest before issuing commands or modifying the state. With this option, the incoming step clock is already expressed in deployment tick units. Calibration clock fields describe commissioning alignment and do not retime the live stream.
