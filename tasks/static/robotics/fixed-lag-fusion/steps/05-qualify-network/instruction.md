# Recommission a nonlinear ranging installation

A receiver reboot changed which radio channels refer to our surveyed anchors. We have several calibration drives with sparse survey fixes and several separate check drives. Recover the wheel calibration, channel bindings, range biases, and trajectories together. Process a range as its distance to one anchor at acquisition time. The receivers in these drives did not sample simultaneously.

Add the following command and keep the earlier commands working.

```bash
python3 -m lagfusion qualify-network --spec SPEC.json --output REPORT.json
```

## Drives and observations

The spec has `anchors` (three distinct, noncollinear positions in metres by ID), `receivers` (three distinct channel IDs), `fit_captures`, and `validation_captures`. Each capture contains a unique nonempty `id`, an `epoch` identifier, and integer `start_tick` and `end_tick`. Use one pose at every integer tick in the closed interval. Captures are independent drives in the same surveyed coordinate frame. An epoch identifies a wiring configuration that persists across captures with that epoch. Fit contains one or two epochs. Validation uses only those epochs.

Each capture contains four arrays. Read their observations independently of array order.

- `wheel` uses `{"device_tick":integer,"delta":[x,y],"sigma_m":positive_number}`. Each `offset_candidates` value is an integer to add to `device_tick` to obtain the acquisition tick. A wheel delta ending at that tick observes the displacement since the preceding tick. Rotate and scale the supplied vector before comparison. Its `sigma_m` is already in lab-frame metres and applies to each component of the residual.
- `imu` uses `{"tick":integer,"delta":[x,y],"sigma_m":positive_number}`. These projected displacements already use the survey frame. They cover adjacent ticks as above.
- `fixes` uses `{"tick":integer,"position":[x,y],"sigma_m":positive_number}` for independent position measurements in the lab frame. Each capture supplies at least one fix.
- `ranges` uses `{"tick":integer,"receiver":id,"distance_m":nonnegative_number,"sigma_m":positive_number}`. Predict range by taking the Euclidean distance from the pose to the surveyed anchor bound to that receiver, then adding the anchor's bias in metres. Each receiver binds to a different anchor within its epoch. Biases are per physical anchor and are shared across epochs.

Inputs use finite numeric values and exclude booleans. Every range and fix tick is inside its capture. Every displacement endpoint has a preceding tick inside its capture. This holds for every candidate wheel offset, so offsets are compared on identical observations. Each interval contains 2 through 32 poses. The fit and validation arrays each contain 1 through 3 captures. Use up to five distinct offsets and 512 total observations per capture. Multiple measurements of the same tick are independent observations.

## Commissioning and qualification

Estimate one offset, positive wheel scale, yaw in `[-pi,pi]`, and three range biases. Fit one receiver-to-anchor bijection per epoch. Estimates and associations use the fit captures only. Minimize the total of the following costs over the poses and calibration parameters.

- For each fix or displacement, use half the sum of squared component residuals divided by its squared `sigma_m`.
- For each raw range, normalize the scalar residual by its `sigma_m` and apply the Huber loss with threshold `huber_k`, a positive number. For normalized residual `r`, the loss is `0.5*r^2` when `abs(r) <= huber_k` and `huber_k*(abs(r)-0.5*huber_k)` otherwise.

The task uses a small hypothesis set and an observable fit in ordinary captures. Report `ambiguous` when two distinct discrete hypotheses (offset or one epoch's bijection) have fitted costs within the supplied nonnegative `ambiguity_cost` of the best. Treat a fit with fewer than three nonzero wheel displacements, or no sample from any receiver in a fit epoch, as `insufficient_support`. Do not issue a calibration in either case.

After a successful fit, freeze the complete calibration and both receiver maps. Estimate a fresh pose sequence in each validation capture using its supplied fixes and sensor observations with the same residuals. Leave the fit model and fit poses unchanged if validation observations change.

## Report

Write `status`, `calibration`, `fit_cost`, `fit`, and `validation`. For `status: "ok"`, use:

- `calibration: {"offset_ticks":integer,"wheel_scale":number,"wheel_yaw_rad":number,"range_bias_m":{anchor_id:number},"receiver_maps":{epoch:{receiver_id:anchor_id}}}`.
- `fit_cost` equal to the total objective evaluated on the reported fit and calibration.
- `fit` and `validation` arrays in input capture order. Each entry has `id` and `poses`, an ascending array of `{"tick":integer,"position":[x,y]}` for every tick.

For `ambiguous` or `insufficient_support`, set `calibration` and `fit_cost` to null and both track arrays to empty. Follow the existing malformed-input and atomic-output rules.
