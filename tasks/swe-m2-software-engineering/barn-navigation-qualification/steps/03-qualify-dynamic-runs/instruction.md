# Replan on occupancy updates and qualify the measured run

The operator can temporarily close or reopen cells while the robot is moving. Keep the prior commands working. A stream observation may provide `revision` (nonnegative integer, default 0) and `rows` (full occupancy snapshot with the original shape). A higher revision installs the supplied rows before deciding the next command. An equal or older revision cannot overwrite the known grid. Wait safely if the current route is cut, retry when space opens, and choose a safe detour from the measured pose when one is available. A missing pose is null and requires zero motion until a usable pose returns. The robot's current footprint is clear when an update arrives.

Add an offline qualification command for a static map and an independently observed traversal.

```bash
python3 -m barn_qualification qualify --spec MAP.json --input TRACE.json --output REPORT.json
```

The trace is a nonempty array of `{"tick":integer,"pose":[x_m,y_m,yaw_rad]}` records with strictly increasing ticks. Treat successive measured centers as straight segments for this offline report. Use the configured radius and margin. Report `{"status":"succeeded"|"collision"|"timeout"|"incomplete","duration_s":number,"distance_m":number,"first_collision_tick":integer_or_null}`. Duration is (last tick minus first tick) times dt. Distance is the sum of center displacements. Report collision if any full trace segment or its endpoints intersects the required clearance region, even if the final pose reaches the goal. Attribute a collision to the segment's ending tick (or the first tick if initially colliding). Otherwise report success if the last pose is within goal tolerance, timeout if it reaches or exceeds the deadline, and incomplete otherwise. Preserve existing output after malformed input. The qualification is for observed motion, independent of the controller's claimed status.
