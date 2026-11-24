# Build an occupancy map from surveyed runs

We use 2D lidar to revisit an indoor site where visibility varies from run to run. I need a tool that turns scans from surveyed poses into a reusable occupancy map. A scanner can establish free space along its beam. Areas it cannot see must remain distinguishable from free space.

Build a modular Python package at `/app/versioned_mapping`. This first request uses one run with poses already expressed in the site's frame.

```bash
python3 -m versioned_mapping build --grid GRID.json --visit VISIT.json --output MAP.json
```

## Inputs

The grid is a JSON object with positive integer `width` and `height`, a positive finite `resolution_m` and an `origin_m` array `[x,y]` giving the lower-left corner. Cell `[column,row]` covers a half-open square. The map excludes its maximum x and y edges.

A visit is a JSON object with a nonempty string `id` and a nonempty `scans` array. Each scan contains a `pose` array `[x,y,yaw]` in metres and radians and a nonempty `beams` array. Each beam is `[angle,range,hit]`, with angle relative to scanner yaw, positive range in metres, and a Boolean hit flag. Poses and beam values are finite. Angles grow counterclockwise. A no-return beam records free space up to its range and supplies no occupied endpoint.

## Map output

Write a JSON object with `schema_version: 1`, the four grid fields, and a `cells` array. Each entry is `[column,row,state]`, with state `free` or `occupied`. Omit unknown cells. List each observed cell once in row-major order.

Cells whose interiors the ray traverses hold free evidence, except the occupied endpoint cell of a hit. A corner or grid-line touch alone does not add free evidence. An endpoint inside the map uses the half-open cell rule. A hit anywhere in the visit takes precedence over free evidence for that cell. Clip all evidence to the grid, including beams originating outside it.

Repeat runs with identical inputs must produce identical file bytes. Malformed input must return nonzero and leave an existing destination intact.
