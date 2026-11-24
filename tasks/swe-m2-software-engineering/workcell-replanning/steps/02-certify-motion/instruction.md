# Check clearance along a recorded motion

The console has been checking only joint waypoints. A link or the object we are carrying can cross a fixture between those readings. Add a command that checks the entire commanded motion against a reconstructed scene. Keep scene replay working.

```bash
python3 -m workcell certify --spec SPEC.json --output REPORT.json
```

The spec contains `robot` and a `scene` in the previous formats, a nonnegative `margin_m`, and a `trajectory` of at least two waypoints. Each waypoint is `{"time_ms":integer,"q":[x,shoulder,elbow]}`. Times start at zero and increase strictly. The controller interpolates each raw joint coordinate linearly over each segment, without wrapping angles. Joint speed is the absolute change divided by the segment duration in seconds.

At every point the upper arm and forearm are capsules with the stated radii around their centreline segments. An attached object's capsule is transformed by the tool pose at that point. Check all arm-link and load capsules against every world capsule. Also check the attached load against the upper arm. The adjacent links and the forearm-to-load contact are intentional and can overlap. For each checked pair the required clearance is `distance_between_centrelines - radius_a - radius_b >= margin_m`.

Return an object with the input scene's `revision`, `status`, `segment_index`, and `witness_fraction`.

- `valid` means joint limits, joint speeds, and the clearance margin hold along every segment. Use null for both other fields.
- `joint_limit` or `speed_limit` identifies a segment that violates the corresponding limit. Use its zero-based index and a null witness.
- `collision` identifies a segment and a fraction in `[0,1]` where a checked pair falls below the margin. The fraction is measured from the segment's start in the same joint interpolation.
- `unresolved` identifies a segment whose clearance you cannot establish and uses a null witness. Use it for numerical uncertainty, including a path too close to the clearance boundary to certify reliably.

If multiple kinds of failure exist, report joint limits first, then speed limits, then clearance. An unsafe measured spot is enough to reject its segment. A valid result needs a continuous argument for the actual joint interpolation. Use geometry and motion bounds or another conservative method. Keep malformed input and output handling from scene replay. An out-of-limits trajectory is a normal report, while a malformed waypoint is an input error.
