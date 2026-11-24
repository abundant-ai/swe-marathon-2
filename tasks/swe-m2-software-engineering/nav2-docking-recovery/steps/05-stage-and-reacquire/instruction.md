# Reach the docking approach from the other side of the charger

Some robots arrive from the service aisle with the charger facing the wrong way or out of view entirely. Extend the existing controller so it can reach a certified staging pose through the facility's nonholonomic motion graph. From there, reacquire the tag and use the existing approach, charge and retry behaviors.

A config can include a `navigation` object. Its absence keeps the earlier interface.

- `nodes` maps pose IDs to 2D world poses `[x_m,y_m,yaw_rad]`. `start` and `staging` are named poses. The mission begins at the start pose. An observation in the navigation phase includes `map_pose` with the current world pose or null if localization is unavailable.
- `edges` is an array of directed `{id,source,target,segments}` objects. Each segment is `{"ticks":positive_integer,"v_mps":number,"w_radps":number}`. Each segment has nonzero linear or angular speed. Each tick applies the constant body twist for the existing `tick_seconds`. A segment can turn in place or follow a forward or reverse arc. The nominal end pose of each edge is its target node. Follow edges as taught. A missing pose can pause a segment and resume its remaining ticks at unchanged pose. Each issued nonzero command advances exactly one tick. The same transport event and restart rules still apply.
- `footprint` is `[half_length_m,half_width_m]` for a body-aligned rectangle about the robot origin. `bounds` and each item of `obstacles` is `[min_x,min_y,max_x,max_y]` in the world frame. The rectangular footprint must stay inside the bounds and clear of each closed obstacle, including turns and between-tick motion. `margin_m` expands both half-extents for route clearance. The defined edges can be individually blocked by geometry even if both endpoints are clear. The map geometry is fixed during one mission. After staging, stay clear of the same obstacles while approaching and retreating.
- `forward_max_mps`, `reverse_max_mps`, and `angular_max_radps` bound motion in this navigation phase. Edges outside those bounds are unavailable. `position_tolerance_m` and `heading_tolerance_rad` are allowed differences from a named pose on entering its edges.
- `blocked_edges`, an observation array of edge IDs, reports a temporary external lane hold. Never begin a held edge. A hold does not revoke an edge already in progress. Replan at named poses as holds change. If none of the routes can be taken now, stop and wait until a route opens or the mission deadline. Directions and graph membership remain as taught.

Keep the original response fields. While navigating to staging, include
`"stage_edge":id_or_null` for the selected edge. Null indicates a wait at
a node. During an odometry or map pose outage request zero velocity.
The first response at the measured staging pose with no remaining edge
must be stationary. It may omit `stage_edge` or include it as null.
Use that observation's tick as the start of fresh acquisition. Ignore a
tag captured before the handoff and require a fresh usable detection
before the rear approach. Do not release navigation state on a restart.
Stop safely if unable to reach staging and charge by the original mission
deadline.
