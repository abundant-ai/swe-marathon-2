# Plan through constrained navigation maps

Build a modular Python package in `/app/barn_qualification` for checking and traversing cluttered planar maps. The maps use the same occupied/free raster abstraction as the BARN occupancy exports. Put geometry and map handling in reusable functions so we can run the controller and qualify traversals with the same coordinate convention.

```bash
python3 -m barn_qualification plan --spec MAP.json --output REPORT.json
```

The spec has `rows`, an array of equal-length nonempty strings, using `#` for occupied and `.` for free. Columns increase in world x. Rows increase in world y from the first string, with the lower-left grid corner at [0,0]. Each cell has size `resolution_m`. A cell index is `[column,row]`; its position is the cell center. The robot is a disc of `radius_m`. Maintain an additional clearance of `margin_m` from closed occupied squares and the world boundary. The spec declares `start` and `goal` cell indices.

Plan a shortest route using only one-cell cardinal moves. Check the swept disc on every move, including endpoints. Return `{"status":"ready","cells":[...]}` including both start and goal for a feasible route, or `{"status":"blocked","cells":[]}` when there is none. Any shortest safe route is valid. Reject malformed grids or dimensions with nonzero exit and preserve any existing report. An occupied start or goal is well formed and blocked. Example inputs are under `/app/example`.
