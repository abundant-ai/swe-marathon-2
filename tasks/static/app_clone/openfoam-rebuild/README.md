# OpenFOAM rebuild

Author notes; not shipped.

The agent rebuilds OpenFOAM v2606 (tag `OpenFOAM-v2606`, commit `481094fdf34f`, GPL-3.0) from
scratch, in the style of [ProgramBench](https://arxiv.org/abs/2605.03546). It can run the
installed programs but not read them or their libraries, and has their run-time data and
scripts, the published documentation and the tutorial cases. It is graded on how closely its programs reproduce recorded runs of the real ones. Tests:
[AdnanElAssadi/openfoam-rebuild-tests](https://huggingface.co/datasets/AdnanElAssadi/openfoam-rebuild-tests).

## Task

- **Given:** the 272 installed programs, which it can run but not read, their run-time data
  (`/opt/openfoam/etc`) and scripts, `/app/docs` (the v2606 guides, the documentation site,
  release notes and repository docs), `/app/tutorials`, a C++/Python toolchain and MPI. There is no network. The agent has 12 hours, and `/app/timer.sh` shows the
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
  identical runs are dropped, and so, as in ProgramBench, are checks that a program printing
  nothing and exiting with 0 or with 1 passes (`scripts/harvest/merge.py`,
  `scripts/harvest/second_dummy.py`, `scripts/harvest/unstable_checks.json`).
- **Comparison:** text must match exactly, and integers too. Other numbers may differ by one
  unit in the last digit either side printed (in exponent form at most in the sixth
  significant digit), or by 10× OpenFOAM's own spread where that varies. Binary numbers may
  differ by a relative 1e-12. Dictionary entries may come in any order. Banners, dates, hosts,
  process ids, paths, run times and memory use are ignored, as are the C++ function names and
  source lines in error messages. The instruction states these rules.
- **Size:** 9,413 recorded runs and 102,431 checks at dataset revision `3468bf6`.

Not tested: run-time compiled code (`#codeStream`, `coded…`), the cfMesh, OpenQBMM and VTK
modules, and `applications/test`.

## Reward formula

```
reward = checks_passed / checks_kept
```

`checks_kept` is fixed by the dataset revision (102,431 at `3468bf6`). A failed build passes no
check; a program that cannot be started fails every check of its run. Each recorded run is replayed with the submission's programs as UID 10001, with `HOME`
and `TMPDIR` new empty folders, a read-only `/app/rebuild`, and a time limit of
max(30 × OpenFOAM's time, 10 s). Also reported: resolved (all checks pass) and almost (≥ 95%).
Evaluation error: no reward file. One step. Implemented in `tests/verifier/runner.py`; tests in
`checks/`.

## Reference solution

OpenFOAM itself, as source: `solution/solve.sh` puts OpenFOAM's source (the pinned tag, hardened
like the installed build) and its build script into `/app/rebuild`, and its `compile.sh`
builds it in the verifier and writes a wrapper per program. It runs as the agent's user.
`scripts/package.sh` adds the source to the bundle; it is not kept in Git. A do-nothing
submission scores 0.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED.

| # | Attack | Mitigation | Severity |
| --- | --- | --- | --- |
| 1 | Reproduce OpenFOAM's source from memory | Clean-room rule; no source in the image; artifacts audited against upstream after each trial (as ProgramBench reviews trajectories), not by the verifier | 🟡 YELLOW / UNASSESSED |
| 2 | Read, copy or trace the installed programs | Setgid mode 2711, libraries readable by that group only, loaded through `ldconfig`; in the hardened build (`common/reference/hardening.patch`) every file a program opens for reading is checked, once open, to be one the user may read (`open` and `fopen` are replaced in `libOpenFOAM`), and libraries load only by name; `environment/check_hardening.sh` checks both at every image build | 🟡 YELLOW / UNASSESSED |
| 3 | Wrap or deliver the original | Verifier image (`tests/Dockerfile`) holds no OpenFOAM, only the same toolchain | 🟡 YELLOW / UNASSESSED |
| 4 | Fetch the source | No network | 🟡 YELLOW / UNASSESSED |
| 5 | Pass tests without an implementation | Every kept check fails a program that prints nothing and exits with 0, and one that exits with 1 | 🟢 GREEN / LOW |
| 6 | Read expected outputs during grading | Tests and dataset root-only (`chmod go-rwx`); programs run as UID 10001, never set-user-id; the input copy each run is compared against is in a folder only root opens; the verifier follows no link in the output and caps file and decompressed sizes | 🟡 YELLOW / UNASSESSED |

## Layout

| Path | Contents |
| --- | --- |
| `environment/` | Agent image: OpenFOAM built in a separate stage, `/app/docs`, `/app/timer.sh` |
| `common/reference/` | Builds the hardened OpenFOAM (agent image and reference solution) |
| `instruction.md`, `tests/`, `solution/` | Instruction, reference solution, verifier and its image |
| `scripts/package.sh` | Writes the bundle Oddish runs |
| `scripts/harvest/` | Records test runs and builds and publishes the dataset |
| `scripts/generate/` | Cases for behaviour the tutorials do not reach ([README](scripts/generate/README.md)) |
| `scripts/coverage/`, `scripts/docs/` | Coverage feature list; builds `/app/docs` |
| `checks/` | Verifier regression tests |

## Development log

### 2026-11-25

Moved the single brief, verifier and solution to the task root. Harbor reads the
agent and verifier settings from the root configuration.

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
- Oracle on `738fa60`: 1.0 in two trials (experiment `e176947f`, run as root).
- 12-hour trial, Claude Code with Opus 5.5 (trial 43, experiment `d08bc536`): reward 0.401,
  41,682 of 103,880 checks; 145 of 272 programs implemented, the rest stand-ins (about 1% of
  the reward). Its code shares 6 of 79,688 six-line windows with upstream's source.

### 2026-11-26

Changes for Oddish's QA review of version 10:

- Reference solution runs as the agent's user: OpenFOAM's source, built by `compile.sh`.
- Hardened OpenFOAM build in the image: a program opens for reading only files the user may
  read, and loads libraries only by name. `etc/` and `bin/` scripts are readable (the trial
  above read `etc/` through `#includeEtc`).
- Verifier: integers exact; finer printed precision on either side; dictionary order free; a
  missing program fails its run; owner-only executables stay executable; no set-user-id; no
  link followed; system `mpirun`; input copy out of the program's reach.
- Dataset `3468bf6`: drops the 1,449 checks (all exit codes of runs that failed with 1) that a
  program printing nothing and exiting with 1 passes.
- Instruction states the grading rules, the time limit per run and that `PROGRESS.md` is not
  graded.
- Pending: no-op and oracle trials on version 11 (experiment `20236f43`).
