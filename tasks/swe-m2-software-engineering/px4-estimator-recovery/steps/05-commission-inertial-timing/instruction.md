# Commission the inertial units

The next flight uses integrated inertial readings from devices with distinct clocks, sensor mounting, and temperature response. Estimate each device's timing and intrinsic calibration from synchronized bench reference rates before using these measurements for control.

Keep the earlier commands and their contracts. Implement a new command.

```bash
python3 -m px4_recovery commission --spec /path/to/spec.json --output /path/to/calibration.json
```

## Inputs

The spec names the reference and captures CSV files using paths relative to the spec. It also declares device metadata by ID.

```json
{
  "reference": "reference.csv",
  "captures": "captures.csv",
  "devices": {
    "imu-a": {
      "clock_origin_us": 71500000,
      "body_from_imu_wxyz": [0.98006658, 0.19866933, 0, 0],
      "offset_range_us": [-52000, 52000],
      "skew_range_ppm": [-1050, 1120]
    }
  }
}
```

| CSV | Header | Meaning |
| --- | --- | --- |
| Reference | `timestamp_us,wx,wy,wz,fx,fy,fz` | Reference path on the common clock. Angular rate is in radians per second and specific force in metres per second squared, both at the IMU point and expressed in body forward-right-down coordinates. |
| Captures | `device,stamp_us,interval_us,temp_c,dax,day,daz,dvx,dvy,dvz` | Raw integrated gyro and accelerometer readings in each device's axes, with temperature in degrees Celsius. `stamp_us` is the interval end on the device clock and `interval_us` is its duration on that clock. |

Reference timestamps are strictly increasing integer microseconds. Capture rows can be interleaved or arrive out of order. Device names must be declared, `(device, stamp_us)` must be unique, and each duration must be a positive integer. Numeric readings must be finite. Mount quaternions use the Hamilton convention in `w,x,y,z` order. Normalize them before use. They rotate vectors from device axes to body axes. Reference rates already include any contribution at the mounted sensor point.

## Calibration model

For each device let `scale = 1 + skew_ppm × 10⁻⁶`. For any device timestamp `d`, its common-clock time is

```text
t(d) = clock_origin_us + offset_us + scale × (d − clock_origin_us)
```

An interval's physical duration in seconds is `interval_us × scale × 10⁻⁶`. Linearly interpolate the reference angular rate and specific force at the mapped interval midpoint `t(stamp_us − interval_us / 2)`. The reference covers the mapped midpoints for every allowed clock within each declared search rectangle. Both bounds in each clock interval are included. Time units remain microseconds during clock fitting.

Rotate the two reference rate vectors into device axes. For each sensor and axis the expected raw increment is

```text
raw_delta = duration_s × (gain × reference_rate_device_axis
                         + bias + temp_slope × (temp_c − 25))
```

The gain is dimensionless and positive. Bias uses the units of the associated rate. Thermal slope uses those rate units per degree Celsius. Fit all six axis models with the same clock parameters for each device. Some captures contain small measurement noise. Absolute timing, device-axis coefficients and predictions on separate motion sequences all matter.

## Output

Write one JSON object with `status` and `devices`. An observable calibration has status `ok` and includes every device ID. For each ID report `offset_us`, `skew_ppm` and the six three-element fields `gyro_gain`, `accel_gain`, `gyro_bias`, `accel_bias`, `gyro_temp_slope` and `accel_temp_slope`. Triples use device X, Y, Z order.

Return `{"status":"unobservable","devices":{}}` when any device has fewer than 16 captures or when the motion fails to identify timing or per-axis calibration. Constant rates can confound gain and bias. Rates that change only linearly in time can leave timing unidentifiable even with independent temperature variation. Valid output values must be finite. Malformed input must return a nonzero exit status without creating or replacing the report.
