# Reconcile a pushing rig's wrench frames

The two-axis arm carries a force–torque sensor whose origin is offset from the pusher. Our logs use the sensor axes. Translate each measurement to its pusher point in the lab frame and report the corresponding joint torques. Write an offline, modular Python package in `/app/wrenchlab`.

```bash
python3 -m wrenchlab transform --spec SPEC.json --output REPORT.json
```

The spec contains `arm`, `calibration`, and `samples`. All lengths are metres and rotations are radians, positive counterclockwise. The two planar revolute joints have angles `q=[q1,q2]`. `arm.lengths_m` contains the two positive link lengths. `arm.world_from_base` has `xy` and `yaw_rad`. From the base, the first link follows heading base yaw plus `q1`, and the second adds `q2`. The tool frame starts at the end of the second link and has that link's heading. `arm.pusher_offset_m` is the pusher point in tool coordinates.

`calibration.tool_from_sensor` has `xy` and `yaw_rad`. It specifies the sensor's origin and axes in the tool frame. `calibration.bias` is an additive sensor reading `[fx,fy,mz]` in newtons and newton-metres. Each sample provides a unique nonempty `id`, `q`, and `raw_wrench` in the same channel order. Read finite numbers and exclude booleans.

Return `{"samples":[...]}` in input order. Each report row contains the input `id`, `pusher_position_m` (world XY), `world_wrench` (world XY force and moment about the pusher point), and `joint_torque_nm` (two torques). Subtract bias first. Rotate force into the world frame and shift the moment from the sensor origin to the pusher. Use the Jacobian of world pusher pose with respect to joint angles and the virtual-work relationship to obtain joint torques.

Malformed input must exit nonzero and preserve an existing report. Publish successful reports atomically.
