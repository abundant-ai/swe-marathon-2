# Replay a rigid payload pickup and release

Add a `handoff` command to `/app/simbranch`. Start at a saved grasp checkpoint, attach the payload to the moving carrier, run the carry, then release it into the original model and continue. The pickup is an instantaneous plastic latch. It can coincide with an existing support contact, so the post-latch velocity must satisfy both the grasp and the contact constraints.

Keep the five earlier commands available. Separate model editing, impact computation, state transfer, and native replay into focused modules.

```sh
python3 -m simbranch handoff --spec SPEC.json --output REPORT.json
```

## Request and supported models

| Field | Value |
| --- | --- |
| `model` | The original inline `{xml, assets}` model |
| `checkpoint` | Its packed integration state at the latch tick |
| `latch` | String names `carrier`, `payload`, `carrier_site`, `payload_site`, plus finite nonnegative `max_distance_m` and `max_angle_rad` |
| `carry`, `release` | Native rollout requests with `end`, `updates`, `sample_ticks`, and `checkpoint_ticks` |

The payload is an explicitly declared leaf body directly under `worldbody`, with one free joint. The carrier is a different dynamic body. It may be on an articulated fixed-base chain. Each site belongs to its indicated body. At the latch tick the world-frame site positions must differ by at most `max_distance_m` and their relative orientation angle by at most `max_angle_rad` in `[0,π]`. The sites authorize the latch. Use the actual payload body pose for the attachment transform.

Use self-contained MJCF with a direct, explicit body tree and named bodies, joints and actuators. Leave free-body inertial alignment and static fusion disabled. Geometry assets can use the existing in-memory format. The body tree uses ordinary `body` and joint elements without `include`, `attach`, `frame`, `replicate`, `composite` or `flexcomp`. Actuators transmit to retained joints. The source has no equality constraints, tendons, flex bodies or simulator plugins.

At latch there can be up to eight touching native geometry contact rows that allow relative normal motion in the attached coordinates. The rows may be redundant. Compute relative velocity in the world frame using the two bodies' native velocity fields at the contact position. World geometry and mocap bodies contribute zero velocity at the instantaneous event.

The carry begins at the checkpoint tick in the compiled attachment model. Its `end` is later than the checkpoint and appears in `carry.checkpoint_ticks`. That boundary is the release tick. The released continuation runs in the original model and ends later. Both segments use the ordinary pre-update sampling rules and native array layouts for their respective models.

## Latch semantics

Compile a model in which the payload is a jointless child of the carrier. Preserve its actual world pose, geometry, and inertia with the relative pose captured at the event. Retain the unrelated body, joint, and actuator definitions. Named actuator controls and activation, body wrenches, mocap state and user data carry across the event. The compiler output may have different formatting from the source. Stored keyframes may be omitted from the attachment model because they use the old coordinates. An explicit MuJoCo `size` arena may use up to 256 MiB. The replay worker uses several native models in its 2 GiB environment.

Take the inelastic impulse at the recorded time before integrating a native step. Let `v⁻` be the recorded source velocity and `M` the source native mass matrix at the recorded pose. The physical post-latch velocity minimizes `(v - v⁻)ᵀ M (v - v⁻) / 2` subject to these constraints.

- The carrier and payload have equal world linear and angular velocities at the payload body origin.
- Source native geometry contacts with signed distance at most zero impose nonnegative separation speed at their contact point. Include points that are separating before the latch, since the grasp impulse can change their velocity. A contact row that vanishes in the attached coordinates adds no restriction. Normal impulses are compressive only, and this instantaneous reset adds no tangential contact impulse. Native contact dynamics apply in subsequent steps.

If `E` maps target generalized velocity into source generalized velocity for the attached motion, carry the applied generalized force as `Eᵀ qfrc_applied`. Encode the target velocity on the reduced native coordinates. Clear the solver warm-start acceleration for the topology change. A carry sample at the latch tick observes this reset state at the original clock time.

## Release semantics and result

At the end of the carry, reproduce the payload world pose and twist in the original model without a release impulse. Keep the carrier and other retained joints at their live positions and velocities. Preserve named body wrenches, actuator state, mocap, user data and the retained joints' applied generalized forces. Set the newly freed joint's applied generalized force to zero and clear the solver warm-start acceleration. Advance the actual original model from this release state through the requested segment.

Return one JSON object with `attached_model`, `latch_checkpoint`, `carry`, `release_checkpoint`, and `released`. The two segment reports have the usual `resume` format. The latch checkpoint uses the model ID of the returned `attached_model`; the release checkpoint uses the source model ID. The transition checkpoints use the original latch and carry-end ticks, respectively.

Exit nonzero on an incompatible model, failed latch guard, malformed checkpoint, or invalid rollout schedule. Preserve the input and any existing output on failure.
