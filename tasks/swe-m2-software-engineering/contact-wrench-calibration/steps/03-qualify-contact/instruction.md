# Qualify a compliant pushing model on held-out drives

Fit a planar model of a compliant pusher and a round sliding object. Then freeze the fitted parameters and predict the force and motion on separate commanded pushes. Keep the earlier commands.

```bash
python3 -m wrenchlab qualify --spec SPEC.json --output REPORT.json
```

The spec supplies `arm` and a successful `calibration` in the earlier shape. `object` has positive `mass_kg`, `radius_m`, and `pusher_radius_m`. `dt_s` is a positive common step duration. Fit rows in `fit` have `q`, `dq` in rad/s, the object's world `position_m` and `velocity_m_s` at the current boundary, its independently measured `next_velocity_m_s`, and sensor `raw_wrench`. The sensor reports the wrench the pusher exerts on the object. Some force readings are outliers. Validation entries have distinct `id`, `initial_position_m`, `initial_velocity_m_s`, and `controls` of `{"q":[...],"dq":[...]}` in commanded order. They provide no observed force or object pose after the initial state.

At each boundary calculate pusher position and velocity from arm kinematics. Let `n` be the unit direction from pusher to object center, `d` the sum of radii minus their center distance, and `s = dot(pusher_velocity-object_velocity,n)`. If the centers coincide or `d <= 0`, predict zero contact force. Otherwise predict `F = max(0, stiffness*d + damping*s) * n`. With nonnegative drag parameters `drag_xy`, use `acceleration = (F - drag_xy * object_velocity) / mass`, element by element. Update velocity by a forward Euler step, then advance position using the new velocity.

Fit positive stiffness, nonnegative damping, and nonnegative drag coefficients from the known pushes. The calibration is fixed. Require enough independent contact variation to distinguish stiffness and damping, and velocity support in each drag direction. For inadequate excitation report `{"status":"insufficient_excitation","parameters":null,"runs":[]}`.

On success write `{"status":"ok","parameters":{"stiffness_n_m":number,"damping_n_s_m":number,"drag_n_s_m":[x,y]},"runs":[...]}`. Each run has `id` and `steps` in control order. Each step contains `force_n` at the current boundary and `position_m` and `velocity_m_s` after integration. Preserve malformed-input behavior and never adjust the fit using validation drives.
