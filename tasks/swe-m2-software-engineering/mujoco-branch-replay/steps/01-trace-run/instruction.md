# Record a reproducible MuJoCo rollout

I need a headless tool to reproduce controller regressions. Our runs use
small MuJoCo models with contact, actuator dynamics, and sparse changes to
inputs. Write a modular Python package in `/app/simbranch` using MuJoCo
3.3.7 and NumPy in the supplied CPU environment.

```bash
python3 -m simbranch trace --spec SPEC.json --output REPORT.json
```

`model` has the MJCF text in `xml` and an `assets` object mapping relative
file paths to UTF-8 string contents. Supply those assets in memory during
compilation. Reject absolute paths and parent-directory traversal. Filesystem
paths are unnecessary for a model in this format. Compute its `model_id`
as lowercase SHA-256 of the UTF-8 canonical JSON for
`{"xml": xml, "assets": assets}`, with sorted keys, compact separators, and
non-ASCII characters escaped.

`end` is an integer tick from 0 through 1200. `sample_ticks` is a list of
distinct integer ticks from 0 through `end`. `updates` contains records with
`tick` and `set`. A tick is an integer from 0 up to but excluding `end`.
`set` names one or more replacement arrays from the following fields.

- `ctrl` and `qfrc_applied` have lengths `nu` and `nv` respectively.
- `xfrc_applied` and `mocap_pos` have shapes `(nbody, 6)` and `(nmocap, 3)`.
- `eq_active` has one integer 0 or 1 per equality constraint.

Use finite JSON numbers and exclude booleans. An array for a zero-size
dimension may be empty. Reject two assignments to the same field at one
tick. Initialize from the compiled model's reset data. At each boundary,
take requested samples before applying that tick's updates and before the
next `mj_step`. Updates persist until replaced. Simulation time comes from
the compiled model's timestep.

Write `{"model_id": string, "samples": [...]}` with one record per requested
tick sorted by tick. Each sample has `tick`, `qpos`, `qvel`, and `act`, read
from the native simulation state. A malformed model or input must produce a
nonzero exit and leave any existing output file intact.
