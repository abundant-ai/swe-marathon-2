# Recover through a temporary estimator blackout

Keep replay and healthy mission behavior. A mission may now include an integer `max_inertial_ticks` greater than zero. Each observation can include `imu: null` or `{"from_tick":integer,"accel":[ax,ay,az]}`, containing the independently measured NED acceleration including all dynamics over the previous physics interval.

When a full fresh local estimate is unavailable, use at most `max_inertial_ticks` of consecutive supported inertial intervals from the last trusted state. From position p and velocity v, use `p + v*dt + 0.5*a*dt**2` and `v + a*dt`. Use only packets with `from_tick == tick - 1`. Publish mode `dead_reckon` with the inertial estimate and a bounded command. Do not confirm waypoint dwell during dead reckoning. A missing or wrongly stamped inertial interval breaks the chain. Hold with null estimate and zero command until a full fresh reconstructed sample is available. A simultaneous independent position anchor can restore a group left unresolved by a lost reset. No inertial fallback is used when the limit field is absent.

On successful reacquisition resume the same outstanding waypoint. An unrecoverable mission must stop and return `abort` by its deadline. A dropout is neither a waypoint completion nor permission to consume unmatched acceleration samples.
