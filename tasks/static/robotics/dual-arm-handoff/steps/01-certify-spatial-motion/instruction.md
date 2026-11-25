# Certify a loaded move in a two-arm cell

I need a headless collision checker for two teachable arms in a shared
assembly cell. Each arm has a vertical carriage, yaw joint, and two
pitch joints. Build a modular Python package in `/app/dual_arm`.

```bash
python3 -m dual_arm certify --spec SPEC.json --output REPORT.json
```

## Geometry and timing

The spec describes `arms.left` and `arms.right`. An arm has `base` (world
XYZ of the carriage at zero height), two positive `lengths` and two
positive link capsule `radii`. There are four `limits` pairs
`[min,max]`, four positive `speed` limits and four positive `accel`
limits. Joint order is height, yaw, pitch and elbow. Units are metres,
radians and seconds.

The configuration `[h,y,p,e]` starts at the base plus `[0,0,h]`.
A link direction at yaw `y` and pitch `b` is
`[cos(y) cos(b), sin(y) cos(b), sin(b)]`. Use pitch `p` for the first
link and `p+e` for the second. The tool frame is at the final link tip,
with rotation `Rz(y) Ry(-(p+e))`.

A shape has centre-line endpoints `a` and `b` in XYZ and positive
`radius`. Endpoints may coincide. `payload.left` and `payload.right`
give the same part's shape in each gripper's local frame. `owner`
is `"left"` or `"right"`. Transform the payload by its current owner's
tool frame. Check arm against arm, payload against both arms, and all
five shapes against every fixture. The two links of one arm meet at
a joint and need no mutual clearance check. The specified gripper
offset is part of the payload calibration.

Each `fixtures` entry has `radius` and ordered `samples` with integer
`tick` and world endpoints `a`, `b`. Interpolate endpoints linearly
between samples and hold the nearest sample outside that interval.
A fixed fixture can have one sample. Use `margin` metres of minimum
separation after subtracting both radii. `tick_seconds` is positive.

## Motion

`before` and `after` are objects each with four coordinates for both
`left` and `right`. `start` and `end` are integer ticks with
`0 <= start < end`. Each coordinate follows rest-to-rest interpolation
`q(u) = before + (3u² - 2u³)(after - before)`, where `u` is the elapsed
fraction. Check continuous swept clearance, joint bounds, speeds and
accelerations. A collision between the endpoints must make the motion
unsafe. Report `{"safe": true}` or `{"safe": false}`.

Numbers must be finite. Reject malformed fields or models without
overwriting an existing output. Publish complete JSON atomically.
