# Plan a transfer before the fixture state is known

The fixture controller now sends several possible motion forecasts after a
sensor reset. A scanner at a taught pose can distinguish some of them. The
motor controller can also take a variable number of ticks to start a command.
We need a transfer plan that completes for every forecast and start delay still
possible from the available readings. Keep the earlier commands working.

```bash
python3 -m dual_arm contingency --spec SPEC.json --output REPORT.json
```

## Inputs

`window` has the same fields as the earlier planning request. Its `fixtures`
array is empty. Carry over the motion, grasp, clearance, ownership, braking
and deadline rules. `scenes` maps one to eight distinct nonempty scene IDs to
alternative fixture arrays in the same format. A scene applies for the whole
transfer. `scanners` maps a subset of the taught pose IDs to readers. A reader
has `ticks`, a positive dwell, and `labels`, a mapping from every scene ID to
the nonempty string its reader returns. Different scenes can share a label.

`delays` has `move` and `handoff`, each a nonempty array of distinct integer
start delays between zero and four ticks. These lists apply to every command
of the respective kind. Any delay can occur independently on each dispatch.
While waiting to start, both arms hold at the current node with the current
owner. The controller reports the actual delay at completion. Brake and wait
start immediately. Scanner dwell starts immediately and holds the arms and
owner fixed.

## Plan and controller outcomes

Each decision applies to all scenes still consistent with observed readings.
The commanded motion and any initial hold must be safe through arrival for
every such scene and every allowed delay. Follow the existing interpolation
and transfer rules over the actual start and finish times. Set `start` to the
decision tick and `end` to `start` plus the primitive duration. For a delayed
move or handoff, add the entire reported delay to both times, even if the
smallest allowed delay is positive. Branch at the actual arrival tick.
Only scanner readings reduce the set of possible scenes. A single policy must
handle every reachable outcome.

Return `{"status":"ready","root":id,"decisions":{...}}` when a safe policy
exists. Each nonempty string ID maps to an object with `command` and `next`.
At a safe resting goal with the right owner, use `command: null` and an empty
`next`. Every nonterminal command is one of the following.

- A planning command from the earlier step, with `next` mapping decimal delay
  strings to decision IDs. Wait and brake have only `"0"`. The initial brake
  is required if the measurement is moving. Brakes are only available there.
- `{"kind":"scan","start":tick,"end":tick,"node":id}` with `end - start`
  equal to the commissioned dwell. `next` maps all possible returned labels
  to decision IDs. A scan is available only at its commissioned resting pose.

A decision may be shared by multiple branches if it is valid on each branch.
Include only reachable decisions. A ready decision graph must reach the goal
by `deadline` on every branch. When no such policy exists, return
`{"status":"blocked","root":null,"decisions":{}}`. Malformed inputs fail
without replacing the previous output. Separate policy search, geometry and
input handling in focused modules.
