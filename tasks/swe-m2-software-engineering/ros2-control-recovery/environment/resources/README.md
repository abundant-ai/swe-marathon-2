# Controller recovery payloads

The tool models exclusive command interfaces, chainable controller
dependencies, and observed hardware generations. Pass an externally
observed JSON snapshot and apply one approved command at a time. A
controller can safely remain active when it and its dependencies own
usable interfaces in the selected target configuration.

The task environment has Python 3.12. The model uses a software simulator
rather than live hardware services.

The candidate image includes ROS 2 Jazzy and the Controller Manager headers
for the final checkpoint. Load `/opt/ros/jazzy/setup.bash` before building.
Run `python3 /app/examples/native_manager_demo.py` after sourcing it for a
minimal lifecycle example with stock simulated hardware.
Run `python3 /app/examples/native_drive_demo.py /tmp/drive` for a single
plant connected through device and command files. Supply those paths to
your joint's hardware parameters. The example starts from generation 1.

## Loaded two-drive chain

Jazzy's Controller Manager loads two responsive upper instances over the
persistent `pair` controller. Check the native graph with
`ros2 control list_controllers -c /LIFT/controller_manager --claimed-interfaces`.
The hardware exposes two effort outputs and a healthy left encoder. The
signed beam force and the operator's height reference are available on
`feedback/strain`, `feedback/goal`, and `feedback/goal_velocity`.
The calibrated static force estimates are `feedback/weight_left` and
`feedback/weight_right`.

The adapter observes device authority on `/LIFT/pair_authority`. A
`std_msgs/msg/String` message can contain
`{"reported_epoch":80,"required_epoch":81,"healthy":true,"sample":20,"stamp_ns":123456789}`.
The actual timestamp uses the local monotonic clock. This example
describes a retired right encoder, even though its observation health
flag is true. [Jazzy cascade control](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/controller_chaining.html)
