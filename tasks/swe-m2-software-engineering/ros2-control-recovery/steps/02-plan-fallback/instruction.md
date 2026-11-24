# Restore the best available controller configuration

We need to bring back as much service as possible after a fault. Keep
`inspect` working and add a planner that proposes one operation at a time.

```bash
python3 -m control_recovery plan --spec SPEC.json --output REPORT.json
```

Use the same graph, readback, and `groups` as before. Each option includes
its named controllers and every dependency. A device in fault is
unavailable. A ready device can be switched to a commissioned mode.
A final configuration may select one option per group, or none if no
compatible assignment exists. The selected controller union cannot
claim different modes or duplicate an exclusive command interface.
Repeated references to the same controller represent one owner.

Choose the assignment serving the largest number of groups. Among
assignments that serve the same number, prefer the lexicographically
lowest option indices in the given group order. Treat no assignment
as worse than any listed option. Requests have up to eight groups and
four options per group.

Write `{"selected": {group_id: option_index_or_null}, "command": ...}`.
The command is null when the readback already matches the selected
configuration. Otherwise propose one of these primitives.

- `{"kind":"stop", "controller":id}` stops an active controller. Stop its
  active dependants first. Remove unsafe controllers and controllers
  outside the target configuration. Preserve an active, usable target
  controller.
- `{"kind":"mode", "device":id, "mode":mode, "generation":integer}` requests
  a needed mode change on a ready device using its observed generation.
  There must be no active command owner on that device at the time of
  the switch.
- `{"kind":"start", "controller":id}` starts an inactive target controller
  after its required controllers are active and usable and its devices
  are ready in the requested mode. Starting it must not conflict with
  another active command claim.

Finish required stops before requesting a switch or a start. Use the
physical readback after each primitive to plan the next one.
