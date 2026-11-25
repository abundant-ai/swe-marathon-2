# Coating cell examples

`job.json` and `scans.json` form a registration example. The job gives the CAD
mesh, calibrated rotary axis, and a pose from initial setup. Each scan records
partial points in its camera frame. Recover the home part pose from the scans
and the measured positioner angles.

`cell/arm.urdf` and `cell/arm.srdf` describe the articulated arm using simple
collision geometry. The base is at the origin. The six joints run from
`turret_yaw` to `nozzle_roll`. The `tool_tip` frame sits at the nozzle outlet
and points along the spray axis.

Run these commands from `/app` after building your application.

```sh
/app/coating register --job /app/examples/job.json --scans /app/examples/scans.json --output /tmp/registration.json
/app/coating register --job /app/examples/ambiguous-job.json --scans /app/examples/ambiguous-scans.json --output /tmp/review.json
```

The first scan set supports a mounted part pose. The second covers only the
interior of a broad planar face and leaves the mounting translation unresolved.

The agent and verifier images include `cc` and the C standard library headers.
To compile a native helper at runtime, put build files in a writable temporary
directory chosen through the process's `TMPDIR`. Verification makes the
packaged application read-only. Ship compatible binaries under
`/app/coating_app/` with the rest of the application, or rebuild temporary
helpers when the process starts.

Use the registered curved witness with the motion planner.

```sh
/app/coating plan-pass --job /app/examples/motion-job.json --registration /app/examples/motion-registration.json --output /tmp/pass.json
```

This job places the nozzle on a fixed-positioner coating pass. Its mesh has a
curved target and adjacent faces outside the coating region.
