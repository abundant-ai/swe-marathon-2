# Execute the world as a headless regression

Keep the inspector. Run a pinned MuJoCo backend for the portable planar world while exposing SDF frames and ROS-shaped measurements. MuJoCo 3.3.7 and NumPy are installed. This task supports no general SDF plugin or Gazebo Transport execution.

```bash
python3 -m sim_regression run --world WORLD.sdf --spec RUN.json --output TRACE.json
```

Each world model in this subset has one link with one centered box collision of full sizes `sx sy sz`. Its link and collision poses are identity relative to the parent. The model pose describes the initial box center and yaw. One model named `robot` in the run spec is mobile. The others are static and may be relocated. Robot rotation is about the vertical axis and its z is fixed.

The run spec contains positive integer `steps` (emit before physics stepping each step, starting at zero), positive `mass_kg`, nonnegative `damping` (applies to all three joints), integer `seed`, `reset_steps` (distinct increasing positive absolute steps), `commands`, `relocations` and `qos`. Use the SDF timestep, MuJoCo Euler integration, no gravity, a planar body with x/y slides and a yaw hinge, and three unit joint motors. The mobile geom is the declared box with the declared mass. Use default MuJoCo contact parameters. Other boxes move as kinematic mocap bodies.

- Commands are ascending `{"step":integer,"force_n":number,"torque_nm":number}` events starting at step zero. Keep the active command until the next event. Apply force along the robot's current forward axis and torque on yaw.
- Relocations are ascending `{"step":integer,"model":id,"pose":[x,y,z,yaw],"jitter_m":number}` events. Jitter adds two independent values from Python `random.Random(seed).uniform(-jitter_m,jitter_m)` to x and y, in event order. Use zero jitter for exact moves. Reset returns every body to its SDF pose and zero robot velocity and restarts simulation time at zero. Global commands and relocation event order continue. If reset and relocation share a step, reset first.
- Emit `{"steps":[...]}`, with one row containing `step`, `epoch` (starts zero, increments on each reset), `time_ns` relative to the current epoch, `base` as the current robot model world pose, `contacts` as sorted names of models touching the robot, and `messages`.
- Publish each robot sensor at epoch ticks divisible by its period. Each message contains `topic`, `frame`, `qos` from the run spec's topic-to-profile map, and `pose`, the sensor world pose from the robot body and static SDF sensor extrinsics. An IMU `value` is the sensor yaw in radians. A lidar `value` is a single horizontal ray distance along sensor x, at its origin height, to the first model geometry other than the robot, or null for no intersection. Do not infer unobserved ground truth from command magnitudes.

Reject malformed inputs without overwriting an existing trace. This command runs headless without a display.
