# Register the part from partial scans

Build an offline coating application in `/app`. Start by giving the cell operator a usable part pose from several partial scans taken as the positioner rotates. A wrong alignment can put the spray on a mask or miss a strip entirely. Return a review result when the scans leave two materially different poses plausible.

Keep the application highly modular. Separate coordinate and geometry rules from file I/O and command handling. Use the supplied robot and cell description, CAD mesh, and sample job under `/app/examples`.

## Command

```bash
/app/coating register --job JOB.json --scans SCANS.json --output REGISTRATION.json
```

The job and scans are JSON. Lengths are in metres, angles are in radians, and times are in integer nanoseconds. A pose is an object with `translation_m` as `[x,y,z]` and `quaternion_xyzw` as a unit quaternion. A pose named `destination_from_source` transforms a point from the source frame into the destination frame.

The job contains these fields for registration.

| Field | Meaning |
| --- | --- |
| `job_id` | Nonempty string identifying the coating job. |
| `part_mesh` | An indexed triangle mesh with `vertices_m` and `triangles` arrays in the part frame. Each triangle contains three zero-based vertex indices in outward winding order. The triangle index identifies that face throughout the job. |
| `base_from_axis` | Calibrated pose of the positioner axis in the robot base. Positive positioner angles rotate around the axis frame's positive Z. |
| `registration` | An object with `initial_base_from_part_home`, `search_translation_m`, `search_rotation_rad`, `translation_tolerance_m`, `rotation_tolerance_rad`, `scan_match_tolerance_m`, and `min_scan_inlier_fraction`. The search ranges bound translation distance and relative rotation angle from the seed. The pose tolerances define the largest useful error in the pose sent to coating. |

`SCANS.json` is an object with `capture_epoch`, a nonempty string, and `captures`, an array of records. Each record contains a unique nonempty `capture_id`, the measured `positioner_rad`, `base_from_camera`, and `points_camera_m`, an array of camera-frame XYZ points. Captures in an epoch share one part mounting. The scans cover different regions of the part and can include clutter and spurious points. The seed is only an initial estimate within the declared search ranges.

Find `base_from_part_home`, the part pose at positioner angle zero. At an observed angle `a`, the part pose follows from applying the rotation about the calibrated axis to that zero-angle pose. With poses composed right to left, the transform is `base_from_axis * Rz(a) * inverse(base_from_axis) * base_from_part_home`.

An alignment is consistent with a capture if at least `min_scan_inlier_fraction` of its points fall within `scan_match_tolerance_m` of the part surface at that capture's angle. Use these bounds to judge competing alignments across the captures. An empty individual capture provides no support.

## Report

Write `{job_id,capture_epoch,status,base_from_part_home,capture_ids}` to the output. Use `status:"registered"` only when the observations support a pose within the useful tolerance, and include the supporting acquisition IDs. Use `status:"review"` and a null pose when the evidence is insufficient, conflicting, or consistent with alternative poses farther apart than the useful tolerances. An empty scan set is valid and requires review. This is a successful command call with a review outcome.

Malformed inputs exit nonzero and leave an existing output untouched. Publish a complete report as one replacement. Include development examples for a recoverable offset and for an ambiguous scan, with commands that reproduce both results.

Keep `/app/coating` executable. Put any application modules or additional
runtime files the executable needs under `/app/coating_app/` and keep them
available when extending the application in later steps.
