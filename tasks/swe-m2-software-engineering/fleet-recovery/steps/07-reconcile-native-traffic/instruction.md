# Restore a native traffic crossing without releasing it early

A read-only carrier reports progress through a shared office passage. A responsive courier can follow a new path, but a late schedule update and a fleet-adapter restart can change both the planned trajectory and the physical state the courier must respect. Preserve the earlier commands.

Implement `python -m fleet_recovery rmf-handover --spec SPEC.json --state DIRECTORY`. Consume one JSON line and flush one JSON reply per observation. The runtime includes the released ROS Jazzy `rmf_traffic` headers and library. For the public C++ starter, read `/app/example/rmf/README.md`. You can invoke `rmf-native` or link the same native library directly. You must use the commissioned native interpolation and continuous conflict calculation for this checkpoint.

## Manifest

- `map` names the common map. `carrier_profile` and `courier_profile` specify `radius`, `linear_speed`, `linear_accel`, `angular_speed` and `angular_accel` in SI units.
- `nodes` maps named courier stops to `[x,y]`. The courier begins at `start_node` and must serve `goal_node`. The directed `edges` entries are `{from,to,requires_clearance}`. An unguarded branch may provide a useful physical bypass.
- `crossing` specifies monotonic carrier progress as `position[axis] * sign`, with axis 0 or 1 and sign +1 or −1. Use `clear_progress_m` to find the first native checkpoint at or beyond the crossing clearance. All supplied carrier plans are straight along the declared axis.
- `carrier_lane_tolerance_m`, `telemetry_max_age_ns` and `settle_tolerance_m` define the accepted lane cross-track error, evidence age and measured courier settlement.
- `probe` supplies `start_ns` and courier control `poses`, independent of the actual route commands. Report its first collision with the mirrored carrier itinerary, calculated using the profiles and native cubic trajectories. A missing collision is null.

Use `rmf_traffic::agv::Interpolate::Options(true)` to stop at the commissioned vendor vertices when building both trajectories. Each supplied control pose has `[x,y,yaw]`. Native interpolation adds accelerate, cruise and brake checkpoints. Carrier checkpoint IDs are zero-based native trajectory indices.

## Observation

Each packet is `{tick,time_ns,required_version,schedule,carrier,courier,closed_edges}`. Times share a monotonic navigation domain. Sample ticks begin at zero and increase by one. A schedule update is null or one of these two kinds.

| Update | Meaning |
| --- | --- |
| `{kind:"snapshot",version,plan_id,start_ns,poses}` | A full authoritative trajectory and schedule version |
| `{kind:"delta",base_version,version,delay_ns}` | Add a signed delay to the existing itinerary start time |

Accept only newer snapshots. Accept a delta only when its base equals the current mirrored version and its new version is greater. A missing delta or stale full snapshot must leave the last accepted version and timing intact. The mirror is ready only when its version equals `required_version`. Keep the last accepted plan and version visible while waiting for reconciliation.

The `carrier` object is null or `{plan_id,capture_ns,position:[x,y],vendor_remaining}`. If its capture is newer than the last accepted capture for the same active plan, in the interval `[time_ns-telemetry_max_age_ns,time_ns]`, and on the carrier's lane, derive the greatest native checkpoint at or behind the measured progress. Use −1 when its first waypoint has yet to be reached. Keep progress monotonic on an unchanged plan. A replacement plan discards prior progress. Vendor remaining-point count may be approximate and does not certify a native checkpoint. Polls, delays, elapsed route time and old-plan reports do not constitute physical progress. Keep the most recent accepted carrier evidence until it expires.

For an up-to-date mirror, report the valid measured checkpoint and compute `conflict_at_ns` from the full route and probe. Use null for an unavailable checkpoint. While the mirror is stale, both fields are null. A guarded new entry requires a current mirror, fresh measured progress for the active plan and a reached checkpoint at or beyond clearance.

The `courier` object contains `{position:[x,y],settled}`. A settled token acknowledges a prior command only when the actual position lies within its target tolerance. `closed_edges` lists unavailable directed pairs `[from,to]`. Keep already issued motion until its measured settlement. Supply useful safe movement when a complete usable route exists. With no safe path yet, unguarded motion to a waiting bay is available.

## Reply and persistence

Return `{tick,status,schedule_version,carrier_plan,checkpoint,conflict_at_ns,command}`. The status is `moving` while a command is outstanding, `done` after measured service, `wait_schedule` while idle with a stale mirror, or `wait_carrier` while idle with a current mirror. An active command is `{id,from,to,max_speed_mps}`, with a unique nonempty id, actual settled origin, a directed next waypoint and positive speed within the courier's configured limit. Return the same command object until its measured settlement. Once settled, a new movement has a different ID.

Commit state and its complete response before replying. After a coordinator restart a repeat of the latest identical parsed packet returns the identical reply. An altered same-tick packet, older tick or gap returns `status:"rejected"` with its tick and null for the other five fields. Rejected packets preserve the accepted state.

The native scenarios deliberately restore authority only after real measured clearance. The verifier applies commands to a separate continuous 2D motion plant and measures swept footprint clearance, eligible guarded release, both completed routes, and a delivery deadline that can require taking a bypass.
