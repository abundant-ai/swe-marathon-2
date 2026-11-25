# Coordinate the arm and rotary positioner

Add a coordinated planner to `/app/coating`. We have parts whose return faces cannot be covered with the positioner locked. Turning the part makes the surface reachable, but the tool still has to follow the coating recipe in the moving part frame. Keep `register` and the fixed-positioner `plan-pass` command working.

```bash
/app/coating plan-coordinated --job JOB.json --registration REGISTRATION.json --output PLAN.json
```

Use the same job, recipe, registration, trajectory schema, and error behavior as `plan-pass`. The seventh axis can now move within its declared position, speed, and acceleration limits. A ready trajectory still begins at the measured start configuration at rest. Finish with the positioner at `final_positioner_rad` and all axes stopped by the job duration.

Plan the arm and rotary motion together. Apply the instantaneous axis rotation to the fixture bodies and the registered part. Evaluate the recipe and the tool's progress in the moving part frame. Use the same part, fixture, world, and self-clearance rules throughout the interpolated motion.

The choice of coverage order, arm configuration, rotary direction, and surface subdivision is open. An infeasible scene can be reported as blocked with an empty trajectory.

Preserve focused code for frame transforms, process rules, and motion constraints. In your development record, compare an indexed pass with a coordinated pass on a part whose curved return requires the fixture to turn. Include the commands, duration, and resulting coverage and dose figures.
