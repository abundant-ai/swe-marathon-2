# Qualify a frozen policy across paired starts and deployment delays

Before running a policy on the arm, use the held-out demo pairs to check
whether it survives deployment timing changes. Keep both earlier commands.
Use the supplied frozen weights and reset simulation and controller state
for each rollout.

```bash
python3 -m rollout_qualification qualify --spec SPEC.json --output REPORT.json
```

The spec has dataset, a path relative to the spec, split "train" or "valid",
positive integer horizon, nonempty observations, actions, and nonempty
scenarios. Each observation describes a scalar as
{kind,name,mean,scale}. scale is positive. Read kind qpos or qvel using
the named joint. Read kind goal_error as that named goal joint's target
minus its measured qpos. Read kind applied using the previous filtered
command for the named actuator. Normalize each scalar as (value-mean)/scale
and keep the given observation order. actions maps every actuator name to
{bias,weights}. Compute its action as bias plus the dot product of weights
with observed scalars. weights must have one entry per observation.
Apply actions in the model's actuator order through the earlier controller.

Each scenario has a unique nonempty id and nonnegative integers
command_delay and observation_delay. Change the FIFO to command_delay,
keeping its newest entries when shortening it and prepending zero commands
when lengthening it. For observation_delay, use observations from that
many control ticks earlier, holding the reset observation until enough have
arrived. Compute fresh observations from the running simulator rather than
the logged demonstration after reset.

For every pair in the requested split, run both roles for exactly horizon
ticks in each scenario. Write {schema_version:1,rollouts,summary}.
Each rollout has pair_id,scenario,demo,recorded_role,goal_success,
first_goal_tick,final_state,actions,applied. first_goal_tick is its first
1-based post-action tick within the goal or null. actions contains every
raw policy output in model order and applied contains the filtered commands.
Sort rollouts by pair_id, scenario ID and then demo name. summary maps each
scenario ID to {trials,successes}. Reject malformed input atomically.
