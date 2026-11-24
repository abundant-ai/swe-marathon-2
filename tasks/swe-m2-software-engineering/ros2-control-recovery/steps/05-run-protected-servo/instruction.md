# Keep the protected joint tracking during a drive handover

A loaded rotary joint has two independent drives. The maintenance plan says
when to prefer a different drive, but mode switches, starts, and transfers
take time. Readback can lag, a device can restart partway through a switch,
and torque calibration differs between drives. Build the supervisor that
keeps the joint following its reference while the drives change over. Keep
`inspect`, `plan`, `recover`, and `schedule` available.

```bash
python3 -m control_recovery servo --spec SPEC.json
```

The process reads one JSON object per line from stdin and writes exactly one
flushed JSON reply of up to 2048 UTF-8 bytes per read. Keep stdout for replies. The first packet may be
from any cycle if a supervisor was restarted. Use the live state to resume.
On malformed input, exit nonzero without replying to the malformed line.
A clean end of input exits successfully.

## Commissioning and cycle packets

Use the same hardware, controller graph, initial snapshot, and groups as
`plan`. The spec adds `servo` with these fields.

| Field | Meaning |
| --- | --- |
| `drives` | Two entries keyed by hardware device ID. Each has a distinct controller `root`, positive `gain_nm`, finite `bias_nm`, and positive `command_limit`. The root claims that device in its configured mode. Its dependency closure can include commissioned readback controllers. |
| `max_effort_nm`, `max_slew_nm_s` | Positive finite joint effort magnitude and rate bounds. |
| `max_feedback_age_ns` | Nonnegative integer maximum age for a measured joint sample. |
| `inertia`, `drag`, `gravity_nm` | Finite nominal plant parameters. Inertia is positive. Drag and gravity magnitude are nonnegative. |

Each input line provides the following. Time and freshness are integer
nanoseconds. Other numeric measurements and commands are finite. The plant
advances by the given period after each reply. The period can vary per cycle.

| Field | Meaning |
| --- | --- |
| `cycle`, `time_ns`, `period_ns` | Increasing nonnegative cycle and clock counters and a positive duration. |
| `snapshot` | Current commissioned hardware and controller readback in the existing snapshot format. The active list may still contain a drive root whose activation predates a hardware restart. |
| `activation_generations` | Map from drive ID to its reported activation generation, or null. |
| `lease` | Null or `{device,generation}`, the last authority readback. |
| `wanted` | The preferred commissioned drive for current service. It can become unavailable. |
| `pending` | Null or the outstanding action, in the action format below. |
| `measurement` | `{time_ns,position_rad,velocity_rad_s}`. Position is unwrapped. A sample may be delayed or repeated. |
| `target` | `{position_rad,velocity_rad_s,acceleration_rad_s2}` at the current cycle. |
| `applied_nm` | The last physical joint effort. Use it as the continuity reference across switches and restarts. |

## Authority, actions and recovery

Reply `{"cycle":cycle,"effort":object_or_null,"action":object_or_null}`.
An effort is `{device,generation,command}`. Write only to a ready lease
owner in the reported generation. Its root and full prerequisite closure
must be active and usable under the existing interface rules, and
`activation_generations[device]` must equal the current generation.
A stale lease or activation cannot authorize a write. Use null effort
without a usable lease. While a different drive is being prepared or
transferred, continue sending to the current usable owner.

To make progress, request at most one action when `pending` is null. An action
is `{id,kind,device,generation}`, with a nonempty ID unique during the run
and the target device's current generation. A `mode` action also carries
`mode`, the root's commissioned mode. Use it on a ready device in another
mode whose root has no current-generation activation. A `start` needs the
commissioned mode and active usable prerequisites. It activates the root
on the target drive. A `transfer` needs the entire target chain active and
usable in that generation. It changes the output lease only once the device
and authority readback reflect completion. Avoid issuing a redundant action.
One action can complete, fail or become obsolete after several cycles.
The updated readback and pending field govern the next decision.

Prepare the wanted drive while the incumbent continues service. If no usable
lease remains, restore from a viable ready chain, preferring an already active
option to a longer recovery. Resume the wanted route once it can be prepared.
The hardware can hold the last applied effort through a short authority gap.
The supervisor should restore a valid write within 12 cycles of a recoverable
loss, and transfer to a continuously ready wanted drive within 22 cycles.
Count the transfer window from when the drive is wanted, its hardware is
ready in the same generation, and its prerequisites are usable.
The drive and switch system is commissioned to support these deadlines.

## Physical tracking and limits

The supplied drive calibration maps a command to joint torque as
`gain_nm * command + bias_nm`. At each write respect the drive's symmetric
command limit, the joint effort bound, and an effort change from `applied_nm`
of at most `max_slew_nm_s * period_ns / 1e9`. A drive change must obey the
same continuity rule. Maintain safe effort when feedback is stale. The
plant approximates rotary inertia with viscous drag and gravity, and its
true parameters and external loads can vary from the nominal values.
Use measured feedback and cycle durations to correct for disturbance.

Following the initial 0.35 seconds of each run, target position error should
stay within 0.18 rad at each cycle, with RMS error at most 0.060 rad. Keep
RMS error at most 0.020 rad over the final 0.45 seconds after the
handover. After startup, budget the stated cycle period for each reply.
Separate authority handling from tracking and command limiting.
