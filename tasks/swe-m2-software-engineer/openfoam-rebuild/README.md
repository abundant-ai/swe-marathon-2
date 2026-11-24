# OpenFOAM rebuild

Author notes; not shipped.

A ProgramBench task ([arXiv 2605.03546](https://arxiv.org/abs/2605.03546),
[facebookresearch/ProgramBench](https://github.com/facebookresearch/ProgramBench)) whose gold
executable is OpenFOAM v2606 (tag `OpenFOAM-v2606`, commit `481094fdf34f`, GPL-3.0): the agent
gets the execute-only programs, usage documentation and the tutorial inputs, and writes an
implementation with the same observable behaviour. State: agent image, `/app/docs`, test set
(three rounds) and verifier built; oracle repeat check on the current test revision and a graded
12-hour model trial running. Tests: [AdnanElAssadi/openfoam-rebuild-tests](https://huggingface.co/datasets/AdnanElAssadi/openfoam-rebuild-tests).

## Method

ProgramBench, unchanged except where noted.

| Part | ProgramBench | Here |
| --- | --- | --- |
| Specification | The gold executable; any deterministic, observable behaviour (§A.3.4) | Same: all 272 installed programs |
| Agent start state | Execute-only executable, usage docs with implementation details removed, no internet, any language (§2.1, §2.2, §A.2.3) | Same; plus the tutorials as inputs |
| Image | Executable built separately, copied in as the only artefact; Git history removed (§A.2.3) | Same; libraries and run-time data copied too (OpenFOAM needs them) |
| Submission | Source plus `compile.sh` that builds `./executable` in a fresh container, no internet, 900 s; shipped binaries and copies of the gold deleted first (`eval.py`) | Same; `compile.sh` builds `bin/<program>` for every program |
| Tests | Behavioural; coverage-guided agent generation plus harvested existing tests; kept only if the gold passes deterministically and a dummy fails; assertion linter (§2.2, §A.3) | Same, as recorded program runs: every program run of every tutorial (solvers shortened to a few steps) and of agent-written cases for features no tutorial uses; each run gives checks for exit code, files, stdout, stderr and each output file |
| Coverage | Line coverage on an instrumented build, first-party code (§A.3.2) | Same |
| Scoring | Share of tests passed; % resolved and % almost (≥95%) | Same, over checks |
| **Deviation: numbers** | Exact output; floating point avoided (5 of 200 tasks exposed, §A.3.4) | Words exact; numbers within one unit of the last printed digit, or within 10× the gold's own spread across three identical runs where it varies; binary numbers within a relative 1e-12 |
| **Deviation: horizon** | 6 h, 1,000 steps (§B.1) | 12 h, no step limit; the instruction states the budget and `/app/timer.sh` shows the time left (as in SWE-Marathon v1) |

Exclusions (not observable or not in the gold build): run-time compiled code (`#codeStream`,
`coded…`), cfMesh / OpenQBMM / VTK modules, `applications/test`; timings, dates, hosts, process
ids and paths are normalised away.

## Reward formula

```
reward = checks_passed / checks_kept
```

`checks_kept` is fixed by the dataset revision (103,880 at `738fa60`). A failed build passes no
check. Each recorded run is replayed with the submission's programs as UID 10001, with `HOME`
and `TMPDIR` new empty folders, a read-only `/app/rebuild`, and a time limit of
max(30 × OpenFOAM's time, 10 s). Also reported: resolved (all checks pass) and almost (≥ 95%).
Evaluation error: no reward file. One step. Implemented in `tests/verifier/runner.py`.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED.

| # | Attack | Mitigation | Severity |
| --- | --- | --- | --- |
| 1 | Reproduce OpenFOAM's source from memory | Clean-room rule; no source in the image; similarity check against upstream | 🟡 YELLOW / UNASSESSED |
| 2 | Read, copy or trace the installed programs | Setgid mode 2711, libraries readable by that group only, loaded through `ldconfig` | 🟡 YELLOW / UNASSESSED |
| 3 | Wrap or deliver the original | Verifier image (`tests/Dockerfile`) holds no OpenFOAM, only the same toolchain | 🟡 YELLOW / UNASSESSED |
| 4 | Fetch the source | No network | 🟡 YELLOW / UNASSESSED |
| 5 | Pass tests without an implementation | Every kept check fails a do-nothing program; local verifier test: 0 of 67 | 🟢 GREEN / LOW |
| 6 | Read expected outputs during grading | Tests and dataset root-only (`chmod go-rwx`); programs run as UID 10001 | 🟡 YELLOW / UNASSESSED |

## Development log

### 2026-11-18

- Tutorial sweep on Oddish (495 tutorials, official v2606 rc2 image, 10-minute limit): 295 run,
  148 slower than 10 minutes, 37 need a compiler, 15 crash. Repeated runs on one machine are
  byte-identical; ARM against x86 differ by 1e-14 to 1e-3.

### 2026-11-19

- Instrumented build of v2606 final (`--coverage -O1`): 272 programs, 133 libraries.
- Harvest baseline: 439 tutorials cover 201,802 of 418,302 executable lines (48.2%). Running
  30 of them 10 minutes instead of 90 s added 0.17%.
- Instrumented and normal builds differ (`pitzDaily` converges at step 281 against 282): expected
  values come from the normal build.
- Instruction drafted, with ProgramBench's clean-room rules (§A.2.3).
- OpenFOAM has 41 file names that differ only in case (`fvcDdt.C`, `fvcDDt.C`); on macOS they
  overwrite each other. The source is therefore cloned inside the Linux build stage. The one
  colliding tutorial (`PDRFoam/flamePropagationWithObstacles`, `0.orig/B.gz` and `b.gz`) was
  corrupted in the sweep's copy; its "crash" was ours, not OpenFOAM's.
- Agent image (`environment/Dockerfile`, `common/reference/build.sh`): gold built in a separate
  stage (38 min, 8 jobs, ARM; 272 programs, 137 libraries, 0 build errors); only programs,
  libraries, `etc/`, `bin/tools`, `META-INFO` and the tutorials cross over. Programs `root:openfoam`
  2711, library tree readable by that group only, registered with `ldconfig`. OpenFOAM's
  environment loads in login, interactive and non-interactive shells (`BASH_ENV`) and through
  `PATH`. `experiment/check_agent_image.sh` as `dev`: 16 of 16 pass (reading or copying programs
  and libraries, `/proc/PID/{exe,maps,mem}` and `LD_PRELOAD` refused; `pitzDaily` to step 282,
  run-time loaded function objects, `-listScalarBCs`, `foamDictionary`, `checkMesh`, a parallel
  case under `mpirun`, `snappyHexMesh`).
- Correction: two of those passes were wrong; the checks looked only for `FOAM FATAL`.
  `decomposePar` (and every program linking KaHIP) did not start: setgid programs ignore
  `LD_LIBRARY_PATH`, so OpenFOAM's `lib/dummy` stand-ins were not found; the ones with no real
  counterpart are now registered with `ldconfig`. Parallel runs failed: mpirun's PMIx server
  refuses ranks whose group differs from its own (the setgid group), and each rank started alone;
  fixed with `PMIX_MCA_psec=none`. The checks now require every program to start and every log
  to end normally: 18 of 18 pass, including decompose, `mpirun -np 2`, reconstruct.
- Grader core (`steps/01-rebuild-openfoam/tests/verifier/`): OpenFOAM file reader (ascii,
  binary, gzip; 196 of 198 sample outputs, the other two VTK), output normaliser (banner, dates,
  ids, paths, run times, and the gold's C++ function names and source lines in error messages),
  comparer (text exact; numbers within one unit of the gold's last printed digit or a calibrated
  spread). On real outputs: a repeat run and last-digit rounding pass; do-nothing, copy-through,
  a 4th-digit change, a renamed patch and binary-for-ascii fail.

- Test recording (`scripts/harvest/`): every OpenFOAM program and `mpirun` wrapped on `PATH`; each
  call saves the case folder before, the command, and what the program wrote, changed, removed,
  printed and returned. Solvers capped at 5 time steps. Each record replayed 3 times with
  OpenFOAM (varying printed numbers masked, varying data numbers given 10× their spread, varying
  structure or integers dropped), once with a do-nothing program (checks it passes dropped), and
  once more with OpenFOAM. File contents stored once by sha256.
- Generated cases (`scripts/generate/`): `features.py` lists what the solvers report
  (`-listScalarBCs` etc.) and which no tutorial names; 90 programs no tutorial runs. Eight agents,
  one per group, wrote 153 small cases from `BRIEF.md` (shrunk tutorials changed in one place,
  error cases, hand-written mesh files), each checked twice for identical results.
- Cloud recording on Oddish (task `openfoam-harvest`, 30 machines × 16 CPUs, x86): 648 sources.
  Real OpenFOAM failed 11 of about 80,000 kept checks in the final replay, from three grader
  defects, fixed: a NUL byte some parallel runs print before the banner; a timing line
  ("… in = 0.01 s") that did not vary in the three runs; floating-point error when measuring a
  one-digit difference. Three shards' archives (over about 1 GB) were not uploaded; archives are
  now split into 500 MB parts and those shards were rerun: 100% pass.

### 2026-11-20

- Test set merged (`merge.py`): 6,316 recorded runs, 80,465 checks, 255 programs, from 476
  tutorials and 152 generated cases. Dropped: 255 unstable records, 22 compiling code at run time,
  29 with no check left, 7 duplicates, 5 killed at the time limit, 8 checks OpenFOAM failed.
  Uploaded (`publish.py`, `dataset_card.py`) in ProgramBench's dataset style: one JSON per run,
  contents under `files/`, `tests.jsonl`, card, attribution, GPL-3.0 licence. 30.6 GB; every
  record and all 62,564 referenced files checked present.
- Run times of real OpenFOAM: median 0.17 s, 99% under 5 s, all 6,316 together 0.9 h.
- Instruction: standard error is compared (ProgramBench's tests assert on it too), internal
  function and source-file names in error messages are ignored, and `compile.sh` has two hours.
- Verifier (`tests/verify.py`, `tests/verifier/`, `tests/Dockerfile`, `task.toml`): separate image
  with the candidate's toolchain, no OpenFOAM, and the dataset at a fixed revision; builds the
  submission as UID 10001 without network, then replays every recorded run. `recorded.py` is
  shared with the recording scripts. Local test on 20 records (67 checks): OpenFOAM wrapped as a
  submission 67 of 67 (reward 1.0), do-nothing programs 0 of 67, no `compile.sh` 0 (build failed).
- Round 2 of generated cases (`cases/programs2`, `options_a|b|c`, `cli`): 112 cases from four
  agents for the 17 programs without a test (`gaps_programs_round2.txt`) and for options and
  error messages of the 116 programs with one or two recorded runs (`gaps_options_round2.txt`),
  plus `cli/allPrograms` (every program with `-help`, `-help-full`, an unknown option, and in an
  empty folder). Recorded on 4 machines: 2,571 of 2,609 records stable, OpenFOAM 15,868 of
  15,868 checks, no errors.
- Test set at dataset revision `dbd2994`: 8,885 recorded runs, 96,333 checks, all 272 programs,
  from 476 tutorials and 264 generated cases; all 71,177 referenced files present. The verifier
  image is pinned to it.
- Full-scale verifier run (Oddish `openfoam-gradercheck`, revision `72ae6cf`, 80,465 checks, 16
  CPUs): do-nothing programs 0 (105 s); OpenFOAM wrapped as a submission only 62,231 (77.3%,
  46 min). Causes: (1) all 278 runs under `mpirun` hung: the verifier started `mpirun` with a
  clean environment, without the agent image's `PMIX_MCA_psec=none`, so the setgid ranks were
  refused (about 17,500 checks); (2) `publish.py` wrote a trailing empty entry into `removed`
  (about 640 checks); (3) a printed home folder (`foamHelp`); (4) a time-and-memory line
  (`foamToVTK`: "0.01 s, 313228 kB") that did not vary in the three recording runs; (5) name
  order that follows directory listing order (`setsToZones`). Fixed (1) to (4): the verifier's
  environment now has `PMIX_MCA_psec=none` and `USER=dev` as the agent image does, empty
  `removed` entries are ignored, home folders and time-and-memory lines are normalised. Local
  test with 42 records including 3 under `mpirun`: 345 of 345, do-nothing 0. For (5) and
  anything else of its kind, the rerun grades OpenFOAM twice and checks it fails in either run
  are dropped from the test set, ProgramBench's "gold passes deterministically" applied in the
  grading environment.
- Rerun (revision `dbd2994`, 96,333 checks): do-nothing 0 (118 s); OpenFOAM 92,288 (95.8%,
  49 min) and 91,101 (94.6%, 50 min). Of the failures, 3,548 and 5,152 checks were timeouts,
  all in 30 runs under `mpirun`, some of which take OpenFOAM half a second: the verifier ran 16
  tests at a time on 16 CPUs whatever their process count, so runs with 8 to 32 processes
  shared the machine with each other and with 15 other tests. The verifier now starts a run only
  when the processors it uses are free (`recorded.processes`, `recorded.run_packed`; a run
  wider than the machine runs alone); ideal time on 16 CPUs is 11 minutes. The rest (about 60
  records) are output that depends on the machine or on timing, which ProgramBench's rule
  drops: which `mpirun` rank's error and abort message come first (stderr, exit 1 or 14),
  zone and field names in directory-listing order, uninitialised values in a written file
  (`decomposePar` `pointLevel`), last-digit differences after parallel reductions, and
  "Initial memory".
- Line coverage of the set (Oddish `openfoam-testcoverage`, `c++Cov` build, all 8,885 runs):
  228,226 of 417,555 lines, 54.7% (tutorials alone: 48.2%). Solvers 79%, utilities 62%,
  libraries 52%; the largest gaps are `src/optimisation` (22%), mesh generation (19%),
  `finiteArea` (40%), `fileFormats` (38%), `sampling` (43%). 77 runs timed out with the same
  cause and write no counters, so this undercounts (mostly `snappyHexMesh`); rerun with the
  scheduling fix.
- `/app/docs` (`environment/docs`, 20 MB, read-only; rebuilt by `scripts/docs/build_docs.sh`):
  ProgramBench gives the agent the program's own documentation, so this is OpenFOAM's
  published v2606 documentation, unchanged apart from format: the User, Tutorial and
  Programmer's Guides (official PDFs, plus text), the documentation site doc.openfoam.com/2606
  (763 pages as Markdown with their images; its source is not public, so pages are converted
  from HTML, keeping each article and dropping navigation; two pages the site itself fails to
  serve are missing), the v2606 release notes, and the documentation files of the source
  repository (README, build notes, man page, licence). Nothing generated from source code.
  Licences: guides CC BY-NC-ND 3.0, site CC BY-NC-ND 4.0, repository GPL-3.0.
- Reference solution (`solution/solve.sh`): the installed OpenFOAM copied into the submission
  with a wrapper per program; locally, graded with OpenFOAM hidden, it matches OpenFOAM's own
  results, parallel runs included.
- Grader check with the scheduling fix (revision `dbd2994`): OpenFOAM 96,279 of 96,333 in
  both runs (99.94%; 42 and 41 min), do-nothing 0 (5 min). The 62 checks it failed in either
  run (17 and 19 runs: `mpirun` error order, directory-order names in `setsToZones` and
  `foamFormatConvert`, `decomposePar` of `atmFlatTerrain` and `mixerVesselAMI`, last digits
  after `redistributePar` and parallel solvers) are dropped by `dataset_card.py`, which now
  takes the verifier reports: revision `6ad2745`, 8,885 runs, 96,271 checks; the verifier image
  is pinned to it.
- Instruction revised to ProgramBench's form (about 300 words): rebuild OpenFOAM from scratch so
  that its externally observable behaviour matches the installed one; clean-room rules; delivery
  contract. Beyond ProgramBench it states only what the verifier enforces and a
  correct-looking rebuild could still fail without being told: building with `compile.sh`
  within two hours without network, one executable per program named like it, running without
  OpenFOAM or its environment variables, read-only `/app/rebuild` with empty `HOME` and
  `TMPDIR`, about as fast as the installed programs (the verifier's cutoff, max(30 x OpenFOAM's
  time, 10 s) per run, is a safety net that a program meeting this never reaches); plus modularity (repository requirement) and
  `/app/rebuild/PROGRESS.md` (progress record, as other SWE-Marathon tasks ask). Removed: what
  only describes the verifier's leniency (ignored banner, dates, hosts, paths, run times and
  function names in errors; numeric tolerance; out-of-scope features), the backstory, primers,
  program set and examples, usage modes such as `mpirun`, the module split and the tool list.
- Oddish: packaged task `swe-m2_software-engineering_openfoam-rebuild` (runtime files only),
  version 4: oracle trial and pilot (claude-code, Claude Opus 5.5, 7 days).
- Pending: coverage rerun; drop the checks OpenFOAM fails in either run and
  publish that revision; round 3 for the coverage gaps; `/app/docs`; packaging; model trial.
  (Done by 2026-11-24, below.)

### 2026-11-24

- Round 3 recorded (cases for the remaining coverage gaps) and merged; `/app/docs` built
  (`scripts/docs/build_docs.sh`: the three guides as PDF and text, the v2606 site as Markdown,
  release notes, repository docs). Grader fixes found by repeat oracle runs: run times written
  "in N seconds" are normalised like "in N s"; 22 checks whose output varies between identical
  OpenFOAM runs are listed in `scripts/harvest/unstable_checks.json` and dropped. Test revision
  `738fa60`: 9,414 recorded runs, 103,880 checks. On the previous revision (`13c4728`) two
  oracle runs failed 2 and 3 of 103,883 checks; those are what the two fixes remove.
- Pilots (claude-code, Claude Opus 5.5, Oddish): trial 36 worked 4.85 h, then ended its turn
  while helper agents ran; in print mode that ends the session and kills them (reward 0.118).
  Trial 40 ran with background tasks off (`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`) and worked
  the full 24 h without stopping; by 14 h it had started the programs behind 62% of the
  recorded runs. Oddish then ended the attempt at its 24 h limit (Modal's limit; Archil shares
  the setting) and restarted it from scratch; the attempt was not graded and its files were lost.
- Agent budget cut from 7 days to 12 hours, so that 12 h + 6 h grading + build fits under
  23 h on every provider. The agent never stops early (trial 40 was still progressing at 24 h), so a cut-off
  is certain; as in all SWE-Marathon v1 tasks, the instruction states the budget and
  `/app/timer.sh` shows the time left, so the build is not broken by chance at the cut.
- Regression tests for the verifier in `checks/` (output normalisation, comparison, replay of a
  record with stand-in programs, reward), registered in the root `pyproject.toml`.
- Running: two oracle trials on the current revision; a 12-hour pilot with
  `--max-trial-attempts 1`.

