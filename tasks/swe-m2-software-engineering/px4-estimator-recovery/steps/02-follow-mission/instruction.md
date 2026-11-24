# Follow a mission through reported estimator resets

Connect the reconstruction to a software-only flight supervisor. It commands bounded acceleration to a short sequence of NED waypoints. This harness uses an independent point-mass test plant.

```bash
python3 -m px4_recovery stream --spec MISSION.json
```

The mission spec contains `dt` in seconds, `waypoints` as three-element positions, positive `max_accel` per-axis acceleration limit, `position_tolerance` and `speed_tolerance` as Euclidean norm tolerances, positive integer `dwell_ticks`, `deadline` as the last integer tick, and `max_age_us` as permitted capture age. Observations contain consecutive integer `tick`, integer `now_us` on the capture clock, and `local` with a decoded position record or null. Each line has one response and must flush.

Return `{"mode":"track"|"hold"|"complete"|"abort","acceleration":[ax,ay,az],"estimate":[x,y,z]_or_null,"waypoint":index}`. Track the current waypoint using fully valid fresh reconstructed state. Require consecutive qualifying physics observations for the dwell, then advance the waypoint without skipping. Use the final index count for completion. Hold at zero commanded acceleration when no full fresh state exists. Issue zero acceleration on terminal outcomes. After the deadline, a mission that has not completed must abort. Consecutive status and estimates must reflect the corrected NED frame, including repeated 8-bit wraparound and declared resets.
