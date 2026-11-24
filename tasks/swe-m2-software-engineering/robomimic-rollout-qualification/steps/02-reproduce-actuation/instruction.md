# Reproduce recorded actions with the original controller

Keep inspect and add a command that restores the recorded simulator and
controller state, then executes a demonstration. This should locate the first
step at which a repeat differs from the recording.

```bash
python3 -m rollout_qualification replay --dataset DATASET.hdf5 --demo DEMO --output REPORT.json
```

Restore states[0] via mjSTATE_FULLPHYSICS and recompute derived MuJoCo data
before stepping. At each control tick, clip the recorded action to the
symmetric action_limits, append it to the FIFO initialized from
controller_state.queue and dequeue the oldest command. With zero delay the
new command is used immediately. Filter the dequeued command with
new_filtered = filter_alpha * command + (1-filter_alpha) * previous_filtered.
Write the result to model-order ctrl and run substeps native MuJoCo steps.

Write {schema_version:1,demo,first_divergence,goal_success,steps,final_state}.
steps contains one row per action with state_before, applied and state_after
as native ordered numeric vectors. first_divergence is the earliest zero-based
tick at which a state_before coordinate differs from the recorded row by more
than 0.00000001, or null. The final goal succeeds when the two named joint
positions are within goal.radius Euclidean distance of goal.target at the end.
final_state repeats the last native state. Exit nonzero for malformed data
or an unknown demo and preserve any existing report.
