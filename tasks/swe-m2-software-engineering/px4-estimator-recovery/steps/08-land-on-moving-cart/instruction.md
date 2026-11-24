# Land on a moving laboratory cart

Add a precision-landing mode to `/app/px4_recovery` for a multicopter in a flight enclosure. The cart curves through the enclosure and may move throughout approach and touchdown. The camera sends delayed observations of a landing marker. Independent vehicle localization continues even when the marker disappears. The aircraft needs to match the motion of the landing surface and stop descending when the marker evidence is too old.

Keep the earlier estimator, commissioning, flight, and stationary-pad commands available. Organize the new mode into focused modules for input and time handling, motion estimation, and flight control.

## Stream interface

Run `python3 -m px4_recovery land-moving --spec SPEC.json`. Read newline-delimited JSON on standard input. Print one flushed JSON object for each observation. The example under `/app/example/moving-cart-observations.jsonl` can be used with `/app/example/moving-cart-spec.json`.

The specification provides these fields.

| Field | Meaning |
| --- | --- |
| `period_us`, `deadline_us` | Control period and mission deadline in microseconds in the stream time base. The enclosure uses a 40 ms cycle and a 14 s mission. |
| `max_capture_age_us`, `abort_age_us` | Maximum acquisition age for target use, and maximum gap after descent begins before abort. Nominal values are 460 ms and 1.45 s. |
| `deck_down_m`, `staging_down_m`, `min_stale_clearance_m` | Deck and staging heights in NED and minimum altitude above the deck during a target blackout in the approach envelope. |
| `hold_yaw_rad`, `hover_collective`, `max_body_rate_rad_s` | Commissioned heading, nominal hover collective and absolute per-axis body-rate cap. |
| `minimum_quality`, `camera` | Minimum detection quality and `body_from_camera_wxyz` unit quaternion with `lever_arm_m` from vehicle origin to camera optical center in body axes. |

Each packet has `now_us`, which starts at zero, and the following arrays.

- `navigation` contains the independent ownship state samples received since the previous packet. Each sample has integer `at_us`, `position_ned_m`, `velocity_ned_mps`, and `q_ned_from_body_wxyz`. The array includes a state at `now_us`. All positions use north, east, down order. These observations remain available during marker outages.
- `target_detections` contains newly delivered observations. Each has an `id` string, integer `capture_us`, `position_camera_m` relative to the optical center at acquisition, and numeric `quality` from 0 to 100. The source may deliver batches out of order or repeat earlier observations. A repeated observation preserves its original ID and capture timestamp. Return delivery time does not refresh an old measurement.

Each reply contains `phase` (`approach`, `descend`, `hold`, or `abort`), `body_rates_rad_s` as three commanded body rates and `collective` in [0,1]. Include `target` as null while unsupported, or an object with `at_us` equal to the current packet time, `capture_us` identifying a recent observation that supports it, and the estimated current `position_ne_m` and `velocity_ne_mps` as two-component arrays. Estimate the target to the current time from the capture-time camera and vehicle observations. After the first second, report an estimate on at least 75% of ticks with recent qualifying target observations. Keep those horizontal positions within 0.06 m RMS of the current target position.

## Landing and target loss

- Approach above the deck and begin the final descent after matching the cart's horizontal position and velocity. A successful touchdown occurs within 0.097 m of the deck center by the mission deadline, with relative horizontal surface speed at most 0.15 m/s, downward speed at most 0.30 m/s, and fresh target evidence. Avoid contact with the enclosure. The cart trajectory and its physical velocity are unavailable to the worker.
- When the latest usable marker acquisition has aged beyond `max_capture_age_us`, enter hold, stop descending and brake while maintaining the specified deck clearance. Use independent vehicle localization to execute the hold. Resume descent after reacquiring fresh and consistent evidence and matching the cart's motion again.
- After descent begins, a sustained loss beyond `abort_age_us` latches abort within one control period for the rest of the stream. Remain clear of the deck and enclosure. Keep returning bounded commands so the aircraft remains controlled.
