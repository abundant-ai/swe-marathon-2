# Run a safe controller across unfamiliar layouts

Keep the map planner and add a streamed differential-drive controller. The harness starts the robot at the start cell center with a measured heading, applies each submitted twist with unicycle dynamics, and reports its resulting pose. The controller can plan in cells and track using any safe path, including safe shortcuts.

```bash
python3 -m barn_qualification stream --spec MAP.json
```

The config adds `dt` in seconds, positive `max_v` and `max_w` in m/s and rad/s, positive `goal_tolerance_m`, and positive integer `deadline` in ticks. An observation is `{"tick":integer,"pose":[x_m,y_m,yaw_rad]}`. Ticks increase from zero. Return and flush `{"status":"running"|"waiting"|"succeeded"|"timeout","v_mps":number,"w_radps":number}` per line. Speed is nonnegative and forward. Positive turn rate is counterclockwise. Commands are held over that tick interval and there is no velocity for lateral travel.

Keep the footprint clear of all occupied geometry at every instant, including between observations. Stop when within goal tolerance. Use stationary `waiting` when no route can be followed. At the deadline, choose success if at the goal, otherwise timeout. Terminal states stay stationary. Finish reachable courses within the allotted travel time. Use stderr for diagnostics.
