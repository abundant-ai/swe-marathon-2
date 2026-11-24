# OpenFOAM rebuild

Author notes; not shipped.

The agent rebuilds OpenFOAM v2606 (tag `OpenFOAM-v2606`, commit `481094fdf34f`, GPL-3.0) from
scratch, in the style of [ProgramBench](https://arxiv.org/abs/2605.03546). It can run the
installed programs but not read them, and has their published documentation and the tutorial
cases. It is graded on how closely its programs reproduce recorded runs of the real ones. Tests:
[AdnanElAssadi/openfoam-rebuild-tests](https://huggingface.co/datasets/AdnanElAssadi/openfoam-rebuild-tests).

## Task

- **Given:** the 272 installed programs (execute-only), `/app/docs` (the v2606 guides, the
  documentation site, release notes and repository docs), `/app/tutorials`, a C++/Python
  toolchain and MPI. There is no network. The agent has 12 hours, and `/app/timer.sh` shows the
  time left.
- **Delivered:** source in `/app/rebuild` and a `compile.sh` that builds one executable per
  program into `/app/rebuild/bin` within two hours, without network.
- **Rules:** learn OpenFOAM only by running it and from its documentation and examples. Do not
  reproduce its source, decompile, trace, wrap or call the installed programs.

## Tests

Each test is a recorded run of a real OpenFOAM program: the case folder before the run, the
command, and what the program printed, returned, wrote, changed and removed. One run gives
several checks: exit code, files, stdout, stderr and each output file.

- **Sources:** every program run of the tutorials (solvers shortened to a few time steps), plus
  small cases written for features, options and error messages that no tutorial reaches
  (`scripts/generate/cases/`). Line coverage of OpenFOAM by the test set: 60.6%.
- **Stability:** each run is replayed several times with OpenFOAM. Checks that vary between
  identical runs, and checks that a do-nothing program passes, are dropped
  (`scripts/harvest/merge.py`, `scripts/harvest/unstable_checks.json`).
- **Comparison:** text must match exactly. A number may differ by one unit in its last printed
  digit, or by 10× OpenFOAM's own spread where that varies. Binary numbers may differ by a
  relative 1e-12. Banners, dates, hosts, process ids, paths, run times and memory use are
  normalised away, as are the C++ function names and source lines in error messages.
- **Size:** 9,414 recorded runs and 103,880 checks at dataset revision `738fa60`.

Not tested: run-time compiled code (`#codeStream`, `coded…`), the cfMesh, OpenQBMM and VTK
modules, and `applications/test`.

## Reward formula

```
reward = checks_passed / checks_kept
```

`checks_kept` is fixed by the dataset revision (103,880 at `738fa60`). A failed build passes no
check. Each recorded run is replayed with the submission's programs as UID 10001, with `HOME`
and `TMPDIR` new empty folders, a read-only `/app/rebuild`, and a time limit of
max(30 × OpenFOAM's time, 10 s). Also reported: resolved (all checks pass) and almost (≥ 95%).
Evaluation error: no reward file. One step. Implemented in `tests/verifier/runner.py`; tests in
`checks/`.

## Reference solution

`solution/solve.sh` copies the installed OpenFOAM into the submission with a wrapper per
program. A do-nothing submission scores 0.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED.

| # | Attack | Mitigation | Severity |
| --- | --- | --- | --- |
| 1 | Reproduce OpenFOAM's source from memory | Clean-room rule; no source in the image; similarity check against upstream | 🟡 YELLOW / UNASSESSED |
| 2 | Read, copy or trace the installed programs | Setgid mode 2711, libraries readable by that group only, loaded through `ldconfig` | 🟡 YELLOW / UNASSESSED |
| 3 | Wrap or deliver the original | Verifier image (`tests/Dockerfile`) holds no OpenFOAM, only the same toolchain | 🟡 YELLOW / UNASSESSED |
| 4 | Fetch the source | No network | 🟡 YELLOW / UNASSESSED |
| 5 | Pass tests without an implementation | Every kept check fails a do-nothing program | 🟢 GREEN / LOW |
| 6 | Read expected outputs during grading | Tests and dataset root-only (`chmod go-rwx`); programs run as UID 10001 | 🟡 YELLOW / UNASSESSED |

## Layout

| Path | Contents |
| --- | --- |
| `environment/` | Agent image: OpenFOAM built in a separate stage, `/app/docs`, `/app/timer.sh` |
| `common/reference/build.sh` | Builds the reference OpenFOAM |
| `steps/01-rebuild-openfoam/` | Instruction, reference solution, verifier and its image |
| `scripts/harvest/` | Records test runs and builds and publishes the dataset |
| `scripts/generate/` | Cases for features the tutorials do not reach |
| `scripts/coverage/`, `scripts/docs/` | Coverage feature list; builds `/app/docs` |
| `checks/` | Verifier regression tests |

## Development log

### 2026-11-19

- Agent image built: OpenFOAM programs execute-only and libraries readable only through the
  programs; image checks for every program starting, parallel runs and refused reads pass.
- Verifier core: OpenFOAM file reader, output normaliser and comparer.

### 2026-11-20

- Tests recorded from the tutorials and two rounds of generated cases; dataset published.
- Full-scale verifier runs fixed parallel runs, scheduling of multi-process runs and several
  normalisation gaps.
- `/app/docs` and the reference solution added; instruction finalised.

### 2026-11-24

- Third round of generated cases. Dataset revision `738fa60`: 9,414 runs, 103,880 checks.
  On the previous revision, OpenFOAM graded as a submission failed 2 and 3 of 103,883 checks in
  two runs. The causes (a run-time format and three checks that vary between identical runs)
  are removed in `738fa60`.
- Agent budget set to 12 hours, with the budget stated in the instruction and `/app/timer.sh`.
- Verifier regression tests added in `checks/`.
- Pending: oracle trials on `738fa60` and a graded 12-hour model trial.
