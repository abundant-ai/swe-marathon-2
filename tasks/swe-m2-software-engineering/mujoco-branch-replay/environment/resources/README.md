# MuJoCo rollout studies

Use the installed MuJoCo 3.3.7 Python bindings in headless mode. The package
inputs use inline MJCF plus an optional text asset map. The three commands
cover full rollouts, resume from a checkpoint, and persistent studies that
branch from saved states.

The first step's `trace` command accepts this small example.

```json
{
  "model": {
    "xml": "<mujoco><worldbody><body pos='0 0 1'><freejoint/><geom type='sphere' size='.1'/></body><geom type='plane' size='5 5 .1'/></worldbody></mujoco>",
    "assets": {}
  },
  "end": 3,
  "sample_ticks": [0, 3],
  "updates": []
}
```
