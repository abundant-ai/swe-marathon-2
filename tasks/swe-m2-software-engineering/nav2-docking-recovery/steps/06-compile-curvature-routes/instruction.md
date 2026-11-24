# Generate docking routes from a surveyed floor plan

Our new aisle maps give us obstacle rectangles and surveyed poses. They no
longer come with a taught path. Compile each map into a navigation graph
for the existing docking supervisor. The loaded vehicle needs a minimum
turning radius while staging. It can reverse, but it cannot pivot in place.
Preserve the existing docking, charge confirmation and restart behavior.

```bash
python3 -m dock_recovery compile --layout LAYOUT.json --output REPORT.json
```

## Survey and motion limits

`bounds`, `obstacles`, `footprint`, `margin_m`, `forward_max_mps`,
`reverse_max_mps`, `angular_max_radps`, `position_tolerance_m` and
`heading_tolerance_rad` have the same meaning as in the staging configuration.
`tick_seconds` is the supervisor timestep. All dimensions and speeds are
finite, and distance, timestep, speed limits and tolerances are positive.
`margin_m` may be zero. Each rectangle has increasing coordinate bounds.

`origin` is `[x_m,y_m]` and `step_m` is the positive lattice spacing. `start`
and `staging` are integer triples `[column,row,heading]`, where `heading`
is 0, 1, 2 or 3 for east, north, west or south. Grid indices count from
`origin`. `turn_radius_cells` lists one to four distinct positive integer
radii in units of `step_m`. Endpoints of all motion primitives lie in the
lattice. Stay in bounds with the full swept, margin-inflated footprint.

Generate routes using one-cell straight moves or quarter-circle turns with
one of the listed radii. Each primitive is one constant body twist over a
positive integer number of ticks. Both forward and reverse are available.
Choose the shortest valid number of ticks per primitive under the given speed
and angular-rate limits. Axis-aligned clearance at the endpoints alone is
insufficient. The angular sweep and direction of travel both matter.

## Temporary aisle closures

`closures` maps up to four distinct nonempty IDs to closed rectangles. These
are possible independent external holds. A held zone makes every edge whose
margin-inflated vehicle footprint touches it unavailable. An open zone does
not constrain motion. `route_limit_ticks` bounds staging travel time for the
nominal map and for each single closure that permits a route. The supervisor
receives blocked edge IDs from the applicable closure. It still operates on
measured pose, obeys holds at node entry, and restarts from the existing
journal. On the stationary handoff observation include `"stage_edge": null`.

## Output

If no nominal route fits within `route_limit_ticks`, return
`{"status":"blocked","navigation":null,"blocked_edges":{}}`. Otherwise
return `{"status":"ready","navigation":{...},"blocked_edges":{...}}`.
`navigation` follows the existing staging configuration. Include a usable
nominal route and a usable route within the limit for every single closure
that can be routed around within that limit. If a closure cannot be routed
around, its blocked IDs must still prevent using any edge through it. The
graph may contain only the needed routes or additional certified edges.
Each `blocked_edges` key is a closure ID, and its value lists exactly the
unique IDs of edges in your graph whose swept footprint touches that zone.
Preserve the surveyed start and handoff locations, chassis dimensions,
map and speed limits in the generated configuration. Invalid input exits
nonzero without replacing a previous report. Separate map parsing, motion
certification, route search and the supervisor in focused modules.
