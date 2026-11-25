# Generated cases

Small OpenFOAM cases for behaviour the tutorials do not reach: programs no tutorial runs,
options, boundary conditions, models, schemes, file formats and error messages. Every program run
in a case is recorded as tests in the same way as the tutorials.

Each case is a folder `cases/<group>/<name>/` holding a complete OpenFOAM case and an `Allrun`
script that calls the programs in order. Its first comment line names the tutorial the case is
based on (or `scratch`) and what it exercises. Runs expected to fail end in `|| true`.

Each case is:

- **small:** every program run takes a few seconds at most;
- **deterministic:** two runs in fresh copies give identical files;
- **targeted:** the feature appears in the run, and no run fails unless it is an error case.

Run-time compiled code (`coded…`, `#codeStream`) is not used. `coverage_gaps.py` lists source
files the test set does not reach, which is how case targets were chosen.
