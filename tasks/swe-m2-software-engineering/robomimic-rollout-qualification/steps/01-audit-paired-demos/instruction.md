# Audit a paired manipulation recording

I need an offline evaluation tool for a small MuJoCo manipulation study. We
recorded a successful and unsuccessful demonstration from each initial state.
Before replaying them, check the native robomimic HDF5 layout and confirm the
paired recordings and train/valid partition are trustworthy. Build a modular
Python package at /app/rollout_qualification.

```bash
python3 -m rollout_qualification inspect --dataset DATASET.hdf5 --output REPORT.json
```

The file follows the robomimic /data/demo_* and /mask layout. /data has an
env_args JSON string attribute with env_name "QualificationSlide-v1" and
env_kwargs containing positive integer substeps, nonnegative integer delay,
filter_alpha in (0,1], positive action_limits aligned with MuJoCo actuator
order, and goal. goal has two slide-joint names in joints, two finite
positions in target, and a positive radius in metres. The planar task uses
named slide joints and their native MuJoCo model. Pin MuJoCo 3.3.7.

Each demo group contains finite numeric actions with shape [N,nu] and
states with shape [N,mj_stateSize(model,mjSTATE_FULLPHYSICS)]. States are
pre-action snapshots. Integer num_samples equals N and N is positive.
model_file is the embedded MJCF string. The study adds pair_id and role
attributes, with nonempty IDs and role success or failure. controller_state
is a JSON string with filtered and queue, a filtered actuator vector and a
list of delay actuator vectors, oldest first. Use this controller state with
the corresponding simulator state. Both masks contain demo names as strings.
Each demo must be in exactly one of train or valid.

Each pair contains exactly two demos, one of each role. They must have the
same split, MJCF, full-physics first snapshot and controller state. Do not
use metadata labels as simulated outcomes.

Write {schema_version:1,pairs:[...]}. Sort by pair_id. Each entry has
pair_id,split,success_demo,failure_demo,success_samples,failure_samples.
Reject malformed masks, inconsistent paired states, or an invalid model
and leave any existing output intact.
