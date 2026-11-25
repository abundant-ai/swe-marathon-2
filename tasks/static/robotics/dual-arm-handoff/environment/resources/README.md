# Dual-arm assembly cell

The task uses authored three-dimensional capsule models, taught paired
poses and predicted fixture trajectories. The Python runtime is offline.
Build the `dual_arm` package incrementally and record exact command
authority when dispatching against a changing forecast.

## Native robot asset

`ur5e-headless.xml` is derived from MuJoCo Menagerie's BSD-3-Clause Universal Robots UR5e model. The collision shapes, joints, inertials, native drive parameters and attachment site are retained. Visual meshes, materials and the tracking light are omitted. Collision geoms have explicit names for inspection. Upstream Menagerie commit is `f3b6013629c7b94f8ee93fd977b161fa8350f9bc`. The original XML SHA-256 is `ffd0a7b336d3c2d27c35a15cc0d4aaa95196769aca190ac8d6522d3318c345a0`. `UR5E-LICENSE.txt` is the unmodified upstream copyright and license. The fixture and payload geometry are authored. [Pinned source and license](https://github.com/google-deepmind/mujoco_menagerie/tree/f3b6013629c7b94f8ee93fd977b161fa8350f9bc/universal_robots_ur5e)
