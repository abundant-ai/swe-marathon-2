# Recover episodes when camera clocks disagree

A capture service restarted and its frame hashes are missing. The logger retained
raw camera ticks and sync pulses, including some bad pulses, plus a time window
for each committed episode. Reconstruct the episodes we can release. A camera
file may contain several episodes, and a dropped frame can leave a plausible
clip with the correct duration. Preview the repair before publishing it. Keep
the earlier commands working.

```bash
python3 -m lerobot_repair time-plan --dataset DATASET --ledger CLOCKS.json --output PLAN.json
python3 -m lerobot_repair time-apply --dataset DATASET --ledger CLOCKS.json --plan PLAN.json --output NEW_DATASET
```

## Capture journal

Use the earlier v3.0 dataset layout with one to three RGB cameras. The new
ledger is a JSON object with schema_version 1 and these fields.

- sync_tolerance_ns, frame_tolerance_ns and max_drift_ppm are nonnegative
  integers. frame_tolerance_ns must be less than half the nominal frame period.
  max_drift_ppm may be at most 50,000.
- cameras maps every dataset camera name to a nonempty array of boot epochs.
  An epoch has a nonempty string id unique within that camera, a pulses array
  and a shards array. Each pulse has integer sensor_ns and reference_ns on the
  device and master clocks. Sensor stamps are distinct within the epoch. A shard
  has chunk_index, file_index and sensor_ns, an array of strictly increasing
  integer stamps in decoded frame order. Each chunk/file pair belongs to at most
  one epoch per camera. Timestamps may be signed or use a large Unix epoch.
- episodes contains records with distinct nonnegative integer episode_index
  values, Boolean committed, and integer earliest_ns and latest_ns. The latter
  bound the first frame on the master clock inclusively. The capture order is
  ascending episode ID.

## Clock fits and clip candidates

For each boot epoch, consider the affine clock line through each pair of
pulses. Consider lines with positive slopes within max_drift_ppm of 1. Its
inliers are all pulses whose absolute master-clock residual is at most
sync_tolerance_ns. Use the unique largest inlier **set** if it contains at
least three pulses. Several lines can establish the same inlier set. If
distinct inlier sets tie for the largest or there is insufficient support,
the epoch is unusable. Fit ordinary least squares on that set. The refitted
slope must remain in bounds, and every selected pulse must still be within
tolerance. Convert each sensor stamp with the refit and round to the nearest
integer, ties to even. Preserve nanosecond arithmetic near Unix-sized values.

A camera shard is usable when its clock is usable, the named MP4 satisfies
the earlier fixed-rate decoding rules and the number of decoded frames agrees
with its shard stamp array. Adjacent frames in a clip must be consecutive
decoded frames of a single shard. For a candidate clip of length n and a
proposed episode start s, corrected frame i must be within frame_tolerance_ns
of s + phase(i), where phase(i) is i * 1,000,000,000 / fps rounded to the
nearest integer, ties to even. Every camera must support the same integer s
inside the episode's journal window. Check all frames. Treat the byte-level
hashes and old metadata as unavailable evidence for this command.

## Resolve competition between episodes

An assignment selects at most one clip tuple and a feasible start per episode.
It may skip episodes. In ascending episode order, if an assigned episode of
length n starts at s, the next assigned episode must start at or after
s + phase(n). Find the maximum possible assigned episode count across all legal
assignments. Keep an episode only if every maximum-count assignment selects the
same clip tuple for it. Start times may differ while the selected clips agree.

Use the plan format from the earlier command and add matched_count for the
maximum assigned count. Use UNCOMMITTED for missing or uncommitted ledger
entries, and INVALID_FRAME_ROWS for committed episodes with invalid or absent
frame rows. Use NO_TIMED_CLIP when no complete tuple has a common feasible
start and UNRESOLVED_ASSIGNMENT when a tuple exists but no tuple is invariant
across all maximum assignments. A kept episode has an empty reasons array and
the earlier video clip bounds. Include every episode known to the dataset or
ledger. The source and ledger fingerprints use the earlier rules.

time-apply re-derives the reviewed plan and publishes its kept episodes using
the existing native compaction, statistics and receipt rules. Use the canonical
digest of the complete time plan, including matched_count. Keep source and
earlier publications intact. Reject malformed journals, altered plans and
plans without any keepable episode using the earlier error behavior.
