# Plan a coating pass on a curved part

Extend `/app/coating` so the operator can preview an executable coating pass on the registered part. Treat the mounted positioner angle as fixed at the job's start setting for this command. Keep `register` working. Separate surface planning, robot motion, and report generation so each can be used independently.

```bash
/app/coating plan-pass --job JOB.json --registration REGISTRATION.json --output PLAN.json
```

## Job and applied material

Use the part mesh, calibrated axis, and registration report from the previous step. The job also includes the fields below. An engineering sample includes the MoveIt robot model and workcell geometry.

| Field | Meaning |
| --- | --- |
| `robot_model` | Object with absolute `urdf_path` and `srdf_path`, six ordered `arm_joints`, and the `tool_frame` name. The nozzle points along its frame's positive Z. The model supplies collision geometry, joint position limits, and self-collision exclusions. |
| `fixture_collision`, `world_collision` | Arrays of rigid collision bodies. Each has a unique string `id` across both arrays, an indexed `mesh` in its body frame, and `pose` in the zero-angle axis frame for fixture bodies or the base frame for world bodies. Fixture bodies turn with the positioner even if the part is remounted. |
| `target_faces`, `masked_faces` | Disjoint arrays of referenced part triangle indices. Remaining part faces receive the same off-target treatment as masked faces. |
| `start_q_rad`, `final_positioner_rad`, `scene_revision` | Seven measured positions at rest, the required final positioner angle, and a nonnegative integer scene revision. The seventh position is the positioner angle. For this command its start and final angles are equal. |
| `motion` | Object with seven `lower_rad`, `upper_rad`, `max_velocity_rad_s`, and `max_acceleration_rad_s2` values in wire order. It also supplies `min_clearance_m`, `control_period_ns`, and `max_duration_ns`. |
| `recipe` | Object with inclusive `standoff_m` and `surface_speed_mps` pairs, `max_normal_error_rad`, `cone_half_angle_rad`, `max_flow_ml_s`, inclusive `target_dose_ml_m2` pair, `min_covered_fraction`, and `max_off_target_ml`. |

The spray is a simulated cone with uniform flow per unit solid angle. The first surface reached by a ray blocks surfaces behind it. For an unobstructed surface element in the cone, its dose rate per unit area is flow divided by the cone solid angle, multiplied by the cosine of incidence and divided by the square of the nozzle-to-element distance. Occluded or back-facing facets receive zero dose. Include all visible off-target surfaces when accounting for excess material, including nearby fixture and world bodies.

While flow is enabled, the nozzle axis must first intersect a target face. Use the axis hit distance for standoff, the angle between the reverse nozzle axis and outward face normal for normal error, and the speed of the moving hit point in the part frame for surface speed. Keep these within the recipe limits. A qualified plan puts at least `min_covered_fraction` of the target area inside the inclusive dose range and uses at most `max_off_target_ml` of off-target material. Area fractions are measured on the part surface. The clearance and motion limits apply throughout approach, coating, transitions, and departure. Respect the tighter joint limit where the job and robot model both specify one. Apply clearance to the arm and tool against the part, fixtures, and world as well as to the self-collision pairs enabled by the model.

## Plan file

Write `{job_id,scene_revision,status,trajectory}`. A ready plan uses `status:"ready"` and contains a trajectory with rows `{t_ns,q_rad,qd_rad_s,flow_ml_s}`. The position and velocity arrays list the six arm joints in the declared order followed by the positioner. The controller interpolates position using cubic Hermite segments with the stated endpoint velocities. Flow is held at the row's value until the next row. It becomes zero at the final row.

Start at time zero with `start_q_rad` and zero velocity. Subsequent times are strictly increasing multiples of `control_period_ns`. All flow values are between zero and `max_flow_ml_s`. End at rest within `max_duration_ns` with the tool disabled. Keep the positioner constant for this command.

Use `status:"blocked"` and an empty trajectory if registration requires review or a qualified pass cannot be produced within the supplied limits. A job ID mismatch, malformed record, or unknown referenced geometry is an input error. Exit nonzero and preserve an existing output for those errors. Publish an entire complete report in one replacement.

Include one reproducible curved-part preview with the predicted coated area, dose range, and off-target volume in your development record.
