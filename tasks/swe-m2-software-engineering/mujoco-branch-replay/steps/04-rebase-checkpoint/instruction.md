# Resume a rollout in a revised model

Researchers sometimes edit the model between a recorded run and a
counterfactual. They may reorder XML declarations, adjust contact or
actuator calibration, or change a payload mass. The old integration
vector belongs to the original compiled model. Add a command that ports
its state by physical identity and runs a continuation in the revised
model. Keep the previous commands available.

```bash
python3 -m simbranch rebase --spec SPEC.json --output REPORT.json
```

Use `source_model` and `target_model` in the same inline format as before,
plus a `checkpoint` from the source model. The request also has `end`,
`updates`, `sample_ticks`, and `checkpoint_ticks` in the target model's
native array order. The continuation starts at the captured tick. Apply
the same time and boundary rules as `resume`.

## Compatible edits

Both models have named bodies, joints, actuators and equalities. Account
for the implicit world body. Require the same name sets in each of these
categories, the same parent body per named body, and the same named body
for each joint. Body local position and orientation, joint type, anchor,
axis, and neutral `qpos0` values must agree for each matched entity.
Compare numeric values with absolute tolerance `1e-12`. Quaternions in
body orientations can use either sign for the same orientation.

Require equal timesteps and numbers of user-data scalars. Each named
body must agree on whether it has a mocap input. Any actuator uses a
joint transmission. Match its target joint and transmission gear, and
require matching activation dynamics type and activation dimension.
Equalities have joint, connect, or weld type. Require the same type,
named endpoints in order and endpoint categories. These constraints
define coordinate compatibility. Geometry, mass, damping, solver
settings, actuator tuning and equality parameters may change. Models
with simulator plugins or unsupported transmission or equality types are
outside this command's format.

## Migrate and continue

Preserve the native integration state by named entity. Transfer the
joint position blocks, the joint velocity blocks, solver warm start and
applied generalized forces. Also transfer control, actuator activation
blocks, body wrenches, mocap positions and orientations, equality
activation, simulation time and user-data scalars. Copy body pose and
velocity quantities in their native joint frames. The compatibility
rules keep those frames well defined. Keep the full target integration
array even when a component has zero length.

Return `{"checkpoint": migrated_checkpoint, "resumed": resume_report}`.
Use the target model fingerprint on the migrated checkpoint. Report the
migration before stepping or applying any continuation inputs. Resume
the target model from exactly that checkpoint.

Reject incompatible models, malformed state or a malformed continuation
with a nonzero exit code. Keep any existing output intact.
