# Run the frozen policy on the target actuator clock

Keep `observe` and add a controller process that can serve physics samples. Use the exported actor exactly as supplied. Its inputs and outputs remain in the training convention even though both deployment interfaces are in simulator order.

```bash
python3 -m policy_bridge stream --spec SPEC.json --state STATE_DIR
```

Read one observation per stdin line and flush one JSON response per line. Observations have `kind:"step"`, integer `tick` starting at or after zero, and the sample fields from the observation command except `last_action`. Steps arrive in increasing tick order. Diagnostic output goes to stderr.

The additional spec fields are as follows.

| Field | Definition |
| --- | --- |
| `physics_dt_ns`, `policy_period_ticks` | Positive integer physics step and policy period, in nanoseconds and steps respectively. Update the policy only on ticks that are multiples of the policy period. Missed ticks have no inferred samples. |
| `observation.history` | Positive number of normalized frames to concatenate oldest first. At start, prefill with normalized zero frames. At a policy update, append the new frame and drop the oldest. |
| `policy.layers` | Dense layers with row-major `weights`, one `bias` per row and `activation` equal to `linear`, `tanh` or `relu`. Each input width matches the preceding vector. The final width is the length of `action_order`. |
| `policy.action_clip` | Positive symmetric clamp for each final actor component. The clipped action is the next policy frame's `last_action`. At start the previous action is zero. |
| `model.actuator_order`, `model.neutral` | Distinct simulator actuator names and their neutral controls in that order. |
| `actions` | Object keyed by the names in `action_order`. Each value has unique destination `actuator`, `scale`, `minimum`, and `maximum`. Form a canonical target as `reference + scale * action`, clamp to the provided target bounds, and convert to actuator coordinates using `zero + sign * target`. Keep all unassigned actuators at neutral. |

At a policy update, output `{"status":"updated","control":[...],"observation":[...],"action":[...],"target":[...]}`. Control uses actuator order. Observation is the actual stacked actor input. Action and target use action order. At other ticks return status `held` and the last committed control, or neutral before the first update. Set observation, action, and target to null in those replies. Holding does not advance the policy history. Reject malformed config or samples with a nonzero exit. Reserve `--state` for the next checkpoint.
