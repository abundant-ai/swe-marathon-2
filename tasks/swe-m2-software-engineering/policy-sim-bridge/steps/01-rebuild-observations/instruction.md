# Rebuild the policy observation at the simulator boundary

Our exported robot policy works with the training simulator's observation layout. A second simulator exposes the same joints through a different order, position reference, handedness, and quaternion convention. Build a modular Python package in `/app/policy_bridge` that reconstructs the actor's input without changing the policy.

```bash
python3 -m policy_bridge observe --spec SPEC.json --input SAMPLE.json --output REPORT.json
```

The sample has `position` and `velocity` arrays in `model.joint_order`, `orientation` with four components, `angular_velocity` with three components, and a three-component already body-frame `command`. Joint angles and angular velocities use radians and radians per second. `last_action` has one number per name in `action_order`.

- `model.joint_order` lists distinct simulator joint names. `model.quaternion` is `wxyz` or `xyzw`. The quaternion maps body coordinates to world coordinates and may require normalization. `model.angular_frame` is `world` or `body`.
- `joints` maps canonical training joint names to `{"sensor":name,"sign":1|-1,"zero":number,"reference":number}`. Convert a measured position to training coordinates using `q = sign * (position - zero)`. The relative observation is `q - reference`. The velocity is `sign * velocity`. `observation_order` and `action_order` are independent arrays of canonical joint names. Simulator joints outside the policy can appear in the arrays.
- `observation.terms` is an ordered array of distinct names drawn from `gravity`, `angular_velocity`, `command`, `joint_position`, `joint_velocity` and `last_action`. Gravity is the world unit vector `[0,0,-1]` expressed in the body frame. Express angular velocity in the body frame. The joint blocks use `observation_order`. The last action block uses `action_order`. Concatenate blocks in term order.
- `observation.mean`, `observation.std` and `observation.clip` each contain one number per concatenated component. Standard deviations and clip magnitudes are positive. Standardize each component as `(value - mean) / std`, then clamp it symmetrically to the specified magnitude.

Write `{"observation":[...]}` as complete JSON. Reject malformed inputs, such as unknown references, wrong widths, duplicate names, a zero quaternion or non-finite numbers, with a nonzero exit. Preserve any existing output on an invalid input. Python 3.12 is installed. Small example files are under `/app/example`.
