# Reconcile the active controller chain after a hardware fault

I need a recovery tool for a robot with several independent controller
chains. A device can report a fault during an update, leaving a mix of
active controllers and stale mode assumptions. Start by determining
which controllers can continue. Write a modular Python package in
`/app/control_recovery` that runs offline.

```bash
python3 -m control_recovery inspect --spec SPEC.json --output REPORT.json
```

The spec contains the commissioned controller graph and a hardware readback.

- `hardware` maps device IDs to `{"modes": {mode_name: [interface_id, ...]}}`.
  These lists are exclusive command interfaces available in each mode.
- `controllers` maps controller IDs to `{"requires": [controller_id, ...],
  "claims": {device_id: {"mode": mode_name, "interfaces": [interface_id, ...]}}}`.
  Requirements are dependencies, with no cycles. A claimed interface must
  belong to the declared device mode.
- `snapshot.devices` maps each commissioned device ID to
  `{"generation": nonnegative_integer, "mode": mode_name, "state": "ready"|"fault"}`.
  The observed mode may be `"unknown"` during recovery.
- `snapshot.active` lists the controllers currently reported active.
- `groups` is the requested service configuration for a later command.
  For now it may be empty. Each record has a unique string `id` and
  `options`, a list of nonempty controller-root lists in preference order.

Report `{"usable": [...], "deactivate": [...]}` with both lists sorted by
controller ID. Examine the observed active set. A controller is unsafe
if a claimed device is faulted, its mode disagrees with the readback, its
required controller is absent or unsafe, or its active claims conflict.
Claims conflict if two controllers ask for the same exclusive interface
or different modes on a device. Mark every involved controller unsafe and
propagate the fault to their dependants. Any reported active controller
that is unsafe belongs in `deactivate`. A healthy independent chain
belongs in `usable`.

IDs and interface names are nonempty strings. Reject malformed inputs,
unknown references, duplicate names in lists, or a cyclic graph with a
nonzero exit. Publish a complete JSON report atomically and preserve any
existing report on malformed input.
