# Schedule a protected controller handover

A maintenance team needs to switch controller modes while keeping a
protected service live. A standby chain can provide that service, but
starting it takes time and some buses only permit switching during
maintenance slots. Plan the handover from the measured snapshot before
sending requests. Keep `inspect`, `plan`, and `recover` available.

```bash
python3 -m control_recovery schedule --spec SPEC.json --output REPORT.json
```

Use the commissioned graph, `snapshot` and requested `groups` from
`plan`. Add a `schedule` object with these fields.

- `deadline` is an integer tick from 0 through 36. The readback is at
  tick zero.
- `protected` is a list of service requirements. Each requirement is a
  nonempty list of alternative controller-root lists. Every requirement
  must be supplied by at least one complete, usable option throughout
  the handover, including tick zero and the deadline. Include the
  option's dependency closure.
- `durations` has `start`, `stop`, and `mode` maps. The first two map
  controller IDs to durations. The third maps device IDs to objects
  mapping mode IDs to durations. Each duration is a positive integer
  number of ticks. Omitted entries use one tick.
- `maintenance` maps hardware IDs to lists of half-open `[begin,end]`
  windows when the device is unavailable. A device already faulted in
  the snapshot stays unavailable throughout the request.
- `switch_windows` maps hardware IDs to lists of half-open `[begin,end]`
  intervals authorizing a mode operation. The entire operation
  `[start,end)` must fit inside one such interval. Omitted devices have
  unrestricted switching. An empty list permits no switches.

Window bounds are integers with `0 <= begin < end <= deadline+1`. An
input has up to ten controllers and four devices. Every ID in a schedule
field refers to the commissioned graph.

## Operations and coverage

Return `{"status": "scheduled", "selected": {...}, "operations": [...]}`.
Use the primitive shapes from `plan`, and add integer `start` and `end`
to each. Operations run serially, in chronological order. Gaps hold the
observed configuration. Each operation lasts its declared duration.
Complete every operation by the deadline.

- A stop removes its controller at the beginning of the operation.
  All its active dependants must already be stopped.
- A mode switch changes the readback at the end of the operation. It
  needs the observed generation and a device that stays ready through
  completion. No controller may own the device during the switch.
- A start activates its controller at the end of the operation. Its
  dependencies must be active, and its requested devices must stay
  available in the requested mode throughout the operation, including
  its end. Select starts that preserve exclusive ownership.

At every boundary and through any hold, the active controllers and
their dependencies must be usable. They cannot own a device during
maintenance, disagree with its mode, or conflict with each other.
Evaluate active state immediately before and after each change. Both
checks use device readiness at that boundary tick. The schedule may run a temporary standby controller that
is outside the requested end configuration.

At the deadline choose the best requested `groups` assignment that is
active. Use the priority from `plan`, maximizing served groups first
and then preferring lexicographically lowest option indices. A plan
may leave extra healthy controllers active. It must attain the best
assignment achievable by a legal schedule, even if the best static
assignment would require an interruption or miss a window. If the
initial state is unsafe or no schedule can preserve the protected
services through the deadline, return
`{"status": "blocked", "selected": {}, "operations": []}`.

Malformed input must fail with a nonzero exit and leave any previous
output unchanged. Keep declarations, planning, and output handling
modular.
