# Bring up the protected drive in ROS 2 Controller Manager

The simulated supervisor is ready. Connect it to the real ros2_control
interfaces so we can fault-test the hardware and middleware boundary.
Build a ROS 2 Jazzy package that loads a fenced actuator as a
`hardware_interface::SystemInterface` plugin and recovers a controller
chain using the Controller Manager services. Use the provided local
device simulator during development. Keep the earlier CLI commands.

Build the `fenced_drive` ament CMake package from
`/app/control_recovery/native/fenced_drive`. Register
`fenced_drive/FencedSystem` through pluginlib. The plugin instance owns
one commissioned joint. Controller Manager loads one independent instance
per drive. A drive going down must not revoke a healthy joint's controller
or corrupt its device endpoint.

## Device exchange

The hardware configuration names `device_file`, `command_file`, and
`max_sample_age_ns`. Both files already exist at configuration time and
each contains 64 bytes. Exchange records using shared file-backed memory.
Never overwrite or truncate the device file. The device is the sole
sample writer. Each plugin instance is its command file's sole writer.

Records are little-endian. Each field occupies eight bytes. Sample fields
in order are `sequence`, `generation`, `sample_ns`, `healthy`,
`position_rad`, `velocity_rad_s`, `applied_nm`, and `reserved`. The first
four and the reserved field are unsigned integers. The three physical
states are IEEE 754 doubles. `sample_ns` is Linux CLOCK_MONOTONIC time in
nanoseconds. `healthy` is 0 or 1. The link may repeat data, a device boot
may advance generation, and an invalid sample may arrive mid-transfer.

The command fields are `sequence`, `generation`, `written_ns`, `mode`,
`command_value`, `sample_sequence`, and two reserved unsigned zeros.
`command_value` is a double. Modes 0, 1 and 2 mean inhibit, position, and
effort. Both sides use a sequence counter. An odd sequence marks a write
in progress. Publish a completed record with the next even sequence using
release ordering. A read is usable only if the acquire loads of the sequence
before and after copying the record agree at an even, nonzero value.

## ROS interfaces and authority

Expose the commissioned joint's `position`, `velocity`, `effort`,
`drive_generation`, and `drive_healthy` state interfaces. Expose `position`
and `effort` command interfaces. No command can leave the device before a
finite command is supplied under an active, valid claim. Stop sending an
enabled mode when the sample is unhealthy, stale, nonfinite, from the
future, or from a different generation than the prepared claim. An inhibit
record uses mode 0, zero command and the largest coherent generation seen,
with the latest accepted sample sequence for that generation. A delayed
sample from a smaller generation is unhealthy and cannot lower this
generation or overwrite the joint's last finite state. Controller Manager must retain live status
and be able to reclaim the joint after measurements resume.

Implement both command-mode switch hooks. At most one mode may own this
joint. Use the declared start and stop sets with exact resource names and
respect an unrelated joint's requests. Prepare validates that the resulting
claim can be made and records the expected generation. Perform commits
only the prepared request while the device is still healthy and that
generation remains current. A reboot requires a new claim. Releasing a
mode remains possible when the link is down. Inhibit safely during
deactivate and shutdown. Keep `read`, `write` and the perform hook free of
blocking I/O and heap allocation in their normal update paths.

## Recovery bridge

Install a ROS executable named `recover_drive` that uses the live
Controller Manager endpoints. The verifier will pass `--ros-args` with
a namespace and these string parameters.

| Parameter | Value |
| --- | --- |
| `controller_manager` | Relative or absolute manager service prefix |
| `protected_joint` | Name of the hardware joint under recovery |
| `state_topic` | Topic carrying `control_msgs/msg/DynamicJointState` |
| `owned_controllers` | Comma-separated managed controllers in dependency order |
| `preferred_controllers` | Ordered subset to restore once healthy |

In addition to the states above, expose `drive_authorized_generation`.
Its value is zero without a claim, or the generation last committed for
the current claim. It is deliberately distinct from `drive_generation`
after a reboot. The supervisor may start after a reboot with a stale
controller still listed as active. It must detect that condition from
readback and release the obsolete claim before restoring the preferred
controllers. Use live lifecycle and hardware readback to confirm
ownership. Controllers are already loaded and configured. Never
deactivate an unrelated healthy controller. After a rejected strict
switch, query the current state before retrying with a bounded timeout.

The drive simulator follows the commands it actually reads, so recovery
must restore the requested motion as well as the lifecycle state. Keep
transport, mode authority and recovery coordination in separate modules.

In each exercise the initial owners and the independent joint are active.
The two reboot exercises restore position tracking or transfer authority to
effort control using the supplied preferred controller list.
Fenced mode claims, native ROS service recovery, and physical tracking
are scored separately. The final reward keeps 20% of the previous
checkpoint and assigns 80% to native behavior. Native credit is 10% for
working startup and live movement, 20% for generation and mode fencing,
and 70% for the independent recovery checks, including a supervisor arriving after the reboot and continued tracking
of the healthy drive.
