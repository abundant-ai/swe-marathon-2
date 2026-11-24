# Replay a contact fork in different joint coordinates

Add a `rechart` command to `/app/simbranch`. We need to reuse a recorded contact checkpoint after replacing a free joint with three slides and three hinges, or making the reverse change. The engineering purpose is to expose scalar degrees of freedom in a revised model while preserving the physical state at the fork.

Keep `trace`, `resume`, `study`, and `rebase` available. Use focused modules for model compatibility, coordinate conversion, state transfer, and native replay.

```sh
python3 -m simbranch rechart --spec SPEC.json --output REPORT.json
```

Use the same request fields and output structure as `rebase`, plus a nonempty `charts` array. Each entry contains `body`, the named root body, and `source` and `target` chart descriptors. A free descriptor is `{"free_joint":"part-free"}`. A scalar descriptor is `{"slides":["sx","sy","sz"],"hinges":["a","b","c"]}` in the order of the compiled joints. The two descriptors in each entry must specify different chart types. Each root appears at most once.

## Supported changes

A converted root is a physical child of the world. Its chart consists of one free joint or exactly six unlimited scalar joints, with the three slides first. The signed slide axes and signed hinge axes each form an orthonormal basis in the neutral frame. The hinges share a local pivot, which can differ from the body origin. Joint references may be nonzero. The models retain the same named body frames. Converted joints have no actuator transmissions or joint equality endpoints. All other entities follow the earlier `rebase` compatibility and transfer rules.

Choose the principal scalar representation. Relative to the compiled joint references, use a middle angle in `(-π/2, π/2)` and outer angles in `[-π, π)`. For a free quaternion, select the sign with a positive first nonzero coefficient in MuJoCo's scalar-first order. Reject a source or target chart whose six-dimensional world Jacobian at the named body origin has a smallest singular value below `1e-4`.

## Physical checkpoint and continuation

- Preserve the position and orientation of the named body origin and its linear and angular velocities in world axes. Preserve the solver warm-start acceleration as the derivative of that world twist at the current generalized velocity. Account for the changing velocity basis.
- Preserve the virtual work of each converted applied generalized force. The same virtual motion of the rigid body should receive the same work before and after conversion. Preserve body wrenches, controller state, user data, and all other named integration fields as in `rebase`.
- Match world pose, velocity and generalized applied force within `1e-8` and warm-start acceleration within `1e-6`. Use the target chart and the target model fingerprint when encoding the checkpoint.
- Report the migrated checkpoint at the original tick before stepping or applying scheduled input updates. Run the target native model from exactly that checkpoint, using the specified continuation boundary and sampling rules. Target model changes can affect the subsequent dynamics.
- Exit nonzero on an incompatible model, singular chart, malformed checkpoint or invalid continuation. Keep any existing output intact.
