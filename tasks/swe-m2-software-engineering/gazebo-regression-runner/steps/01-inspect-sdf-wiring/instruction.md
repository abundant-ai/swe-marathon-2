# Inspect a portable SDF regression world

Build a modular package in `/app/sim_regression` that resolves the frame tree and sensor wiring of a small portable SDF world. This is an offline regression utility for a declared subset of SDF.

```bash
python3 -m sim_regression inspect --world WORLD.sdf --output REPORT.json
```

The input has a single `world` and its `physics/max_step_size` in seconds. The world can declare direct `model` and `frame` children. Models can declare direct `link` children, and links can declare `sensor` children. All components require nonempty names. Scope links as `model::link`, and sensors as `model::link::sensor`. Direct world frames use their bare names. `world` is the root ID. An omitted pose is identity. A pose has six finite values `x y z roll pitch yaw` in metres/radians and roll and pitch zero. Compose x/y rotations, vertical translations, and wrapped yaw in the document's reference frame. A `pose relative_to` uses a fully scoped ID or `world`, even for a reference declared later. Otherwise its reference is the structural parent. A direct world frame defaults to its `attached_to` if given, otherwise the world.

Sensors have type `imu` or `gpu_lidar`, an absolute unique `topic`, and positive `update_rate` in Hz. Their period must be an integer number of physics steps. Write `{"dt_ns":integer,"frames":{"id":[x,y,z,yaw]},"sensors":{"topic":{"frame":id,"type":type,"period_steps":integer}}}`. Include the world root. The physics timestep in nanoseconds is rounded to the nearest integer. Reject a missing reference, cycle, duplicate ID or topic, malformed pose, or invalid timing before replacing an existing report. The offline examples are under `/app/example`.
