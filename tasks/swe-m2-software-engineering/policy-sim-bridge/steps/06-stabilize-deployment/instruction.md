# Stabilize the qualified policy on a different drive bus

The axis and clock calibration is correct, but the second simulator has a coupled motor interface and varying start delays across its drives. Position commands then produce cross-axis torques, and an added payload changes tracking under load. Identify the target drives from commissioning logs and run the frozen actor through a causal compensator. Keep earlier commands and stream behavior available.

```bash
python3 -m policy_bridge calibrate-drive --spec IDENTIFICATION.json --output DRIVE.json
python3 -m policy_bridge stream --spec MANIFEST.json --state SESSION --drive DRIVE.json --safety SAFETY.json
```

`stream` may also take the existing `--calibration` option. The frozen actor, observation convention, action scaling and decision cadence still apply. Compensation changes only the bus sent to the target and must run on each accepted healthy physics tick, including held actor ticks.

## Identify the target drives

The spec has `joint_order`, a list of one to eight distinct canonical action names, and `delay_candidates`, a nonempty array of distinct integers from zero to eight physics ticks. `fit` and `validation` are separate arrays of up to 1,200 rows, each in consecutive order from its own first nonnegative integer `tick`. Both must have more rows than the maximum delay. Each row holds four vectors in `joint_order`: `requested_rad` is the outgoing canonical position-command bus before transport delay, `position_rad` and `velocity_rad_s` are the actual canonical joint states, and `effort_nm` is the target simulator's measured actuator torque at that physics tick. Each channel receives a fixed delay during these captures and during deployment. All numbers are finite.

For actuator row `i`, use this measured effort model, where `G` is a square command gain matrix and `k`, `c` and `b` are vectors:

```text
torque_i[t] = sum_j G[i,j] * requested_j[t - delay_i] - k_i * position_i[t] - c_i * velocity_i[t] + b_i
```

For every candidate delay, fit this row by ordinary least squares on the fit capture. Use only rows where all candidate delays have history. Choose the delay with the smallest fit torque RMSE, separately for each row. Fit params and delays may use only the fit capture. If any row's design is rank deficient at a required delay, or the second delay's RMSE is within `limits.ambiguity_rmse_nm` of the best inclusive, report `unidentifiable`. Assess rank using relative singular value threshold `1e-8` after scaling each design column to unit Euclidean norm. Zero-norm columns indicate deficient rank. Also report `unidentifiable` if an identified self stiffness/damping is nonpositive or the fitted command matrix has 2-norm condition number greater than `1e5`.

Apply the frozen fit to the separate validation rows, with the same history rule. If any row exceeds `limits.max_validation_rmse_nm`, report `validation_failed` and keep the model for diagnosis. Both limits are finite, nonnegative numbers. Otherwise report `ok`.

Write these fields. All arrays follow the declared joint order. In `unidentifiable`, `model` and `metrics` are null.

```json
{"status":"ok","joint_order":["hip"],"model":{"delays_ticks":[2],"command_gain_nm_rad":[[29.0]],"position_gain_nm_rad":[31.0],"velocity_gain_nm_s_rad":[1.2],"bias_nm":[-0.3]},"metrics":{"fit_rmse_nm":[0.02],"validation_rmse_nm":[0.027]}}
```

Malformed input fails with nonzero exit and preserves an existing report.

## Deploy under physical load

`SAFETY.json` has `joint_order` matching the drive report and `command_min_rad`, `command_max_rad`, and `max_step_rad` vectors in that order. They bound the canonical commands sent to the target, distinct from the frozen actor's target bounds. Each min is below its max, max step is positive, and the manifest's canonical neutral command lies in the envelope. Validate the qualified drive model, immutable session configuration and all joint references before opening a new session or making a state change. The drive can list the same action names in a different order from the manifest. A non-`ok` drive cannot be used in `stream`.

Consume only observations at or before the current tick. Preserve the actor's exact `observation`, `action`, and `target` outputs. `control` contains the compensated values projected through the same signed actuator mapping. Non-action bus slots still use their neutral values. Apply the range and per-update slew limits on every accepted healthy tick, with slew measured from the last emitted command or neutral at session start. On latch, reject, and arm, keep the previous neutral-response behavior. These neutral responses may jump directly to neutral. Reset compensation history on arm and initialize from neutral. A repeat of the latest event returns the exact original reply. Compensated sessions with the same configuration and observations must produce the same replies. Restart must preserve the actuator history, policy history and compensation needed for the same behavior. Loading a different manifest, drive, or safety configuration into an active compensated session fails before a new reply or a state change.

The deployment must track the frozen actor's changing joint targets on native fixed-deck MuJoCo plants with asymmetric inertia and unannounced torque disturbances. After the initial 0.45 seconds of healthy tracking, position RMS across times and joints must be within 0.11 rad. Exclude time spent latched and the first 0.425 seconds after re-arm from this metric. Under the last sustained load, the RMS over the final 0.25 seconds must also be within 0.10 rad. Use peak absolute joint angle within 1.10 rad and peak speed within 10 rad/s throughout the run. A recovered controller should bring all joint errors within 0.17 rad for 12 consecutive ticks within 0.55 seconds of a transient ending or an explicit re-arm. The deployment receives no future commands, disturbance schedule, hidden plant parameters, or ground-truth target trajectory. Separate model identification, compensation and actor execution.
