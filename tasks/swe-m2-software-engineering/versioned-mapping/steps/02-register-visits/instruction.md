# Register a second visit without survey poses

The next recording has odometry in a local frame. We know the approximate site position and heading of that local frame. Find a rigid registration against the map so we can use the run without surveying every pose. A narrow view down a corridor can leave more than one plausible match. The tool should allow the operator to distinguish that from a reliable fix.

Keep `build` and its map format working. Add this command.

```bash
python3 -m versioned_mapping register --map MAP.json --visit VISIT.json --prior PRIOR.json --output REGISTRATION.json
```

Use the earlier visit format with poses in the visit's local frame. The prior contains `center: [x,y,yaw]` in the site's frame, positive finite `xy_radius_m` and `yaw_radius_rad`. Search the inclusive ranges centered on each component. The x and y bounds form a square. Yaw uses the numerical interval around the supplied yaw, which may straddle a full turn. Accept radii up to 3 m and 1 radian.

A transform `[x,y,yaw]` maps local coordinates into the site frame by rotating, then translating. Use occupied evidence from the map and the visit's hit endpoints. A supported endpoint lands within 0.12 m of the center of an occupied map cell. Evaluate support over all hit endpoints, including positions outside the map. No-return beams are not endpoints.

Write a JSON report with `status`, `world_from_visit`, `hit_endpoints`, `supported_endpoints` and `coverage`. Report `ok` with a transform when at least six hit endpoints are present and at least 65% are supported. Report `insufficient_support` otherwise. Report `ambiguous` if the best hypothesis and an alternative each support at least 80% of hit endpoints, their coverage differs by at most 0.02, and the hypotheses differ by at least 0.6 m in translation or 0.3 radians in wrapped heading. These distances distinguish separate alignments from small changes around one fit.

For `ok`, report the supported count and fraction at the returned transform. In the other statuses use null for `world_from_visit`, and report the count and fraction at the best supported hypothesis, or zero if there are no hit endpoints. Reject malformed data atomically as before.
