# Calibrate a remounted force sensor

A remount changed the sensor translation and yaw. The lab recorded known wrenches with an independent fixture so the tool can recover the sensor bias and mount. Keep the prior transform command working.

```bash
python3 -m wrenchlab calibrate --spec SPEC.json --output REPORT.json
```

The spec supplies the same `arm` and `samples`. Each sample has `id`, `q`, `raw_wrench`, and `reference_tool_wrench`. The reference wrench uses tool axes and is measured about the tool origin. Sensor readings obey the rotation and moment shift from the previous step, with the bias added in sensor coordinates.

Recover the constant 2D translation, proper rotation, and three additive biases. The captures have at least five samples, and can include isolated contaminated readings. Estimate the shared calibration from the dominant agreement without chasing isolated faults. If the independent reference forces fail to span two directions after subtracting their mean, report `insufficient_excitation`. Otherwise report `ok` and `calibration` in the previous shape, with `yaw_rad` in `[-pi,pi]`. Set `calibration` to null for insufficient excitation. Retain finite numeric validation and atomic malformed-input handling.
