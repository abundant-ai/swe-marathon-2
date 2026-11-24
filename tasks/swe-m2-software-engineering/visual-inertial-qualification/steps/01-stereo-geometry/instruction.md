# Check geometric support in stereo feature tracks

Our stereo recordings are already undistorted and feature-matched. Some proposed tracks have almost no parallax or fail the calibrated camera model. Build a modular offline package in /app/visqual that triangulates each matched feature and gives us a reason when it cannot be used.

    python3 -m visqual triangulate --spec SPEC.json --output REPORT.json

The spec contains rig and matches. rig.left and rig.right each have positive focal lengths fx and fy and principal point cx and cy, in pixels. rig.left_from_right has translation_m and quaternion_xyzw and maps coordinates from the right camera into the left. A quaternion has four scalar-last entries and any finite nonzero norm. All coordinate arrays are JSON numbers and exclude booleans.

Each match has a distinct nonempty id and left_uv and right_uv in pixel coordinates. Make the two calibrated forward rays unit vectors, using z forward. Transform the right ray and origin into the left frame. Use the midpoint of the closest points on the two infinite lines as the triangulated position. Reject parallax below positive rig.min_parallax_rad, or exactly parallel rays, with status low_parallax. Reject a midpoint whose depth in either camera is not strictly positive with behind_camera. Reproject into both cameras. Use the greater pixel Euclidean error of the two views. If that exceeds nonnegative rig.max_reprojection_px, report reprojection_error.

Write {"matches":[...]} in input order. Each result has id, status, position_m and reprojection_px. A successful status is ok. Use null position and error for low_parallax or behind_camera. For reprojection_error use null position and the measured error. Reject malformed input with a nonzero exit and preserve the previous output. Publish accepted reports atomically.
