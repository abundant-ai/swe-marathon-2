# Dogwood rebuild: Phase C report (2026-11-27)

Author notes, never shipped. Phase C takes the task to QA-ready. The coordinator's scope was:
- the agent-facing material;
- the gaps Phase B named (V near-miss pairs, more K shapes, `format` and `schema` cases);
- the coverage inventory and kill matrix, the stub zoo, the leak scan and a 3+1 determinism run;
- calibration;
- the close-out: bundle, hashes, preflight and backups.

Everything ran in local Docker Desktop (linux/arm64) under the shared heavy lock. Nothing touched
Oddish except `oddish preflight`, a local check that uploads nothing.

## 1. The agent-facing material

**The shipped guide** (`environment/docs/`, 539 files, copied to `/app/docs` in the image):
- `scripts/build_docs.py` builds it from the pinned 1.2.0 source and `scripts/docs_edits.json`
  (318 scripted edits).
- Chapters 07 (Rust API) and 11 (MCP) are left out. The trace file format, which the library
  chapter described, moved into the command-line chapter.
- The Rust API, MCP, LSP, Lean and `net` passages are cut. Corpus citations and tooling wording
  are rewritten.
- The "total transferred" prose is fixed. The timestamp contract now reads "out of contract,
  unspecified".
- Seven statements that contradicted the build were corrected.
- Rules the build enforces but the guide never stated are now stated: positive and bounded
  windows, one declaration per event kind, reserved binder names, duplicate record keys,
  provider declaration checks, and the trace's entity parents.
- The 93 example bundles, LICENSE and NOTICE ship with it.

**The brief** (`instruction.md`) is in the requester's voice. It now states the run conditions
the grader applies:
- standard input is empty unless a command reads `-`;
- the process, file and output limits;
- runs share nothing;
- what the copy of the project leaves out;
- leftover processes are stopped when the work ends;
- JSON layout is free.

It states no session budget. The session length is a single parameter, `task.toml` `[agent]
timeout_sec` (34,560 s).

**Independent review.** A reviewer read the brief, the guide and the image, and judged them
clean. Its findings were applied (commit 9fa766a):
- standard-input cases;
- the grader's registry at the working machine's path;
- a 1 s per-run limit, with a deadline sized from the case count;
- the clean-room line made report-only;
- stale wording in the examples.

## 2. The gaps Phase B named

- **V near-miss pairs.** The generator's 64 near-miss kinds each break one stated rule; the
  restriction templates add more. An accepted bundle counts only when paired with a rejected
  one, so a `validate` that always accepts passes no unit.
- **K shapes.** `scripts/pairs.py` has eight dual shapes (Phase B had one):
  - `previous`;
  - `since` over another key, and over the key's own event;
  - a pin on some kinds only;
  - a session pin;
  - three mirror-rule cases.
- **`format`, `schema` and the command line:**
  - `format` on a layout-disturbed copy, and from standard input;
  - `check-parse` in both formats, and on a copy with one token broken;
  - `schema action`, `event` and `providers` in both formats;
  - `--help`, `-V`, and usage and I/O errors.

## 3. Coverage inventory and kill matrix

**The inventory** (`checks/features.json`) has 417 ids: 256 features, 151 restrictions and 10
out of scope. Each id has:
- a quote that the shipped guide holds;
- its family;
- its routes;
- its detectors.

**Templates.** The generator writes valid bundles and in-contract traces, so many stated
rejections had no case. `scripts/restrictions.py` breaks each such rule on purpose, with two
instances per template:
- 96 restriction templates, plus 5 trace templates and a sandbox template;
- 22 feature templates, plus a `scriptFile` template.

All of them are Phase C work. The first pass wrote 58 restriction templates and 17 feature
templates (commits d47191e and 18b173f). The first full selections then still left gaps, so 38
more restriction templates and 5 more feature templates were added, and one older template was
corrected (it broke the argument-type rule instead of the binding-field rule). They cover:
- event-schema declarations, fields, pins and spreads;
- temporal well-formedness;
- macro definitions and calls;
- provider declarations and an undeclared provider at replay;
- saturating arithmetic, lexical binder scope and call checks;
- a namespaced call read as a provider by its shape;
- a policy `def` winning over the library's.

Before any full run, every template went through the release build in a small container, and
each fails with its own rule's message. The generator's seed is drawn once and kept (private, in
the cache). A rerun after a template change therefore keeps the generator's bundles. The first
full selection had shown that, in another seed, the generator covered some rules only by random
draws.

**Evidence rules** (`checks/coverage.py`), strongest first:
1. A mutant that names the id and changes the case's answer.
2. For a restriction: the breaking shape (a detector, or a template built to break it) plus a
   refusal. A template for a rule with a known message must show that message.
3. For a feature: a successful case whose inputs use it, or one of its messages.

A feature needs 3 cases and a restriction needs 1. One feature needs 2, and the reason is
recorded: the version flag has two spellings and one answer.

## 4. Selection and the stub zoo

`scripts/select_cases.py` keeps no unit that a trivial program can pass. A case is weak when:
- its output is empty;
- its output is its command's most common answer;
- its output is given more than once for its command;
- it is a uniform replay stream;
- it is a `format` that returns its input.

A weak case is paired with a case of its own command whose answer is unique, or it is dropped.
In F only, a weak case with no partner on its own command takes a strong F case of another
command, so constant schema and version answers stay, in pairs. A unit whose every answer is
also given elsewhere is dropped.

## 5. The grader: hardening and robustness

Phase C changes:
- Output capture is bounded: 8 MB per run, 16 MB for the build log.
- Standard input is fed from a bundle file.
- Cases run in an order hashed from their ids, under a deadline of 1.25 s per case (at least
  600 s). The deadline therefore binds only a run that overruns.
- Every leftover process of the build user and of the run user is ended. The sweep repeats until
  none is left.
- The grader adopts orphans (`PR_SET_CHILD_SUBREAPER`). The platform's PID 1 may never reap, and
  zombies count against the 512-process limit.
- What a run or the build leaves in `/tmp`, `/var/tmp`, `/dev/shm` and `/run/lock` is removed,
  as the brief promises.
- Each run's folder stays root's, so a run cannot move or replace it.
- The built program must be a regular file inside the build folder.
- A delivered program that the machine cannot start fails its own cases. The evaluation is at
  fault only when `/bin/true` cannot start either.
- Comparing outputs never raises on candidate output: deep JSON, rule lists of mixed types, and
  empty or overlong rule numbers are compared as printed.
- A link loop in the project is left out instead of raising (Python 3.11's `Path.resolve`
  raises on loops).
- Gold is recorded from a program file named `dogwood`. The usage text names the file a program
  was started as, so a differently named recording binary would have failed 12 help answers of
  the oracle.
- Delivered files that copy Dogwood's own source are listed for the clean-room review. The list
  does not change the score.

## 6. The six problem classes from HarfBuzz's QA (the coordinator's addition)

| Class | Finding in Dogwood | What changed |
| --- | --- | --- |
| Comparison framing in the brief | The brief said the tool "prints the same standard output and ends with the same exit status as the 1.2.0 build" for the same input | That sentence is gone. The brief says what our tools read (standard output in both formats, and the exit status), and that each of them was built around what the 1.2.0 build prints, so a changed report, message or status breaks it |
| Graded but undocumented | `--help`, `help`, `<command> --help`, `--version` and `-V` were graded (14 cases) but stated nowhere in the guide | Chapter 12 now states them (docs edit 319); their inventory ids are anchored there. No other graded behaviour is known to contradict the guide: Phase C corrected the seven it found (commit d47191e), every inventory id's quote is in the shipped guide, and every rule's evidence comes from the build acting as the guide states |
| Documented but never graded | Every command and option the brief and chapter 12 name has cases (`--policy-schema`, `--event-schema`, `--providers`, `--macros`, `--trace`, `--format`, all four `--emit` forms, `-` for standard input, `explain` without a schema, the three `schema` parts) | None needed |
| Stubs above 0 | The zoo had no-op bodies that exit 0 (`silent`) and each command's usual status (`usual-status`) | `exit1` and `exit2` (every command prints nothing and fails) and `forge` join the zoo |
| Reward forging | The grader deleted reward files only at its start and wrote by name into the output folder, which the platform may make writable by every user, with `reward.json` read before `reward.txt`. A check found worse: stopping a grading of the `buildrs` stub mid-build left its forged `reward.txt` (1.0), because clearing planted files at the end protects only a grader that reaches the end | Before any build or run the grader closes the folder to everyone but its owner (mode 0755, as root) and gives it its own mode back after writing. It opens the folder once without following links, ends every process of `builder` and `nobody`, removes whatever stands under its output names, creates each output with `O_EXCL` and `O_NOFOLLOW` relative to the folder's descriptor, and writes the reward last; an evaluation error clears the reward files too. Root copies the built program from an `O_NOFOLLOW` descriptor and opens nothing by name in a folder another user owns while that user can still act. The `forge` stub tries all of this against a world-writable folder, and a grading stopped mid-run is checked to leave no reward |
| Emulated against real amd64 | No answer holds a float or a libm result. Cedar decimals are fixed-point, and every provider decimal in the cases comes from `parse_decimal` of a string literal (checked over every provider script). The gold is recorded on the grading machine itself, at image build | None needed |
| Guide licensing | `environment/docs/` carries Dogwood's LICENSE and a NOTICE of our changes, but the repository's other excerpts (the doc edit list, the inventory's quotes, the mutant patches) had no attribution | A `NOTICE` at the task root names them and the licence |

## 7. The final case set

The last full run (2026-11-27 23:24 UTC) built the final set from the kept generator seed:

| Step | Result |
| --- | --- |
| Candidates | 6,916 cases over 1,150 bundles |
| Release build, 6 runs each | 6,849 byte-identical, 6,890 identical after normalisation |
| Selection | 4,282 cases in 2,304 units, over 1,150 bundles |
| Dropped | 26 unstable over 6 runs, 7 whose answer names a cycle member, 1,162 constant, 371 empty and 350 shared answers with no partner, 61 uniform replay streams, 464 over the L cap, 193 over the X cap |

| Family | Weight | Cases | Units |
| --- | --- | --- | --- |
| R core replay | 0.20 | 514 | 257 |
| B-dedup | 0.17 | 160 | 40 |
| B-scope | 0.05 | 160 | 40 |
| K key-local slicing | 0.15 | 432 | 108 |
| V validate | 0.13 | 350 | 175 |
| V-msg validate messages | 0.05 | 700 | 350 |
| L lowering | 0.10 | 532 | 450 |
| M macros | 0.05 | 14 | 9 |
| P providers | 0.05 | 51 | 30 |
| X explain | 0.03 | 379 | 350 |
| F format, check-parse, schema, command line | 0.02 | 990 | 495 |

M is small. Macro cases mostly land in V, L, X and F, by command: the macro restriction
templates are `check-parse` and `validate` cases.

**Verifier timeout.** At most 1,200 s of build, then 4,282 cases at 1.25 s each (the deadline
allows each case its full 1 s limit, plus 0.25 s to set up and end it), comes to 6,552 s.
`timeout_sec` is 7,800 s, which leaves 1,248 s. The oracle takes about 2 minutes.

## 8. Determinism

- **Release build ×3 over the final set:** 4,282 of 4,282 cases give one answer after
  normalisation. 4,247 are byte-identical; the other 35 differ only in rule-list order, which is
  compared as a set.
- **A perturbed run (1 CPU, serial, a long `TMPDIR`, umask 077):** every answer equals the three
  runs.
- **The grading image's recording (3 more runs):** 4,282 cases recorded, with no case lacking a
  single answer.
- **Cross-check in the kill matrix:** no case changed in 6 or more of the 33 mutant builds. A case
  whose answer varies run to run would look like that; an earlier run's `cycle ... containing X`
  case changed in 19.

Phase C also found and removed three sources of instability:
- messages naming one member of a cycle, chosen by hash order;
- a scope-omission template whose validator errors came one per action, in hash order;
- three cases that were stable in three runs only by luck (the candidate set is now recorded
  six times).

## 9. Leak scan and wording

- **Leak scan** (`checks/leaks.py`, 4,282 cases): no case reads only files equal to a shipped
  example's or an upstream directory's, no policy equals a public one, and no policy is a near
  copy (word 5-grams, Jaccard 0.9 or more).
- **Wording sweep** (`checks/test_wording.py`): 759 hits on the brief, the docs, the image's
  visible names and the registry's crate names, 0 unjudged. In the build's own answers there
  are 5 hits, all Cedar's help text "try testing for the attribute's presence", which is
  domain sense and cannot be changed.

## 10. Calibration

**Band check, on the final set** (each mutant built and run over all 4,282 cases):

| Mutant | Score | Families that move |
| --- | --- | --- |
| M-dedup (no projection or deduplication) | **0.830** | B-dedup only (0 of 40 units) |
| M-scope (bodies without a past operator read the whole history) | **0.950** | B-scope only (0 of 40) |
| M-global (no key-local rewrite) | **0.900** | K only (36 of 108 units pass) |

M-dedup sits in the 0.70-0.85 band. Each of the three moves only its own family.

**Kill matrix:** all 33 mutants are killed (0 survivors). Every mutant moves at least one
family; the scores run from 0.830 (M-dedup) to 0.9998 (the formatter's comment rule, which moves
4 F units). Seven mutants needed new templates before they were killed (section 3). The runs
are in the cache (`runs/mut/`).

**Weights** stay as `notes/DESIGN.md` section 3 lists them (R .20, B-dedup .17, B-scope .05,
K .15, V .13, V-msg .05, L .10, M .05, P .05, X .03, F .02).

**Difficulty estimate** (DESIGN.md section 3a): frontier about 0.47 (0.35-0.60), mid-tier about
0.19 (0.08-0.30). It is an estimate until the first trials.

## 11. The grading image on the final set: baselines, the zoo and the probes

All gradings ran beside a PID 1 that never reaps (`docker exec` into `sleep infinity`, as the
platform runs `test.sh`), with an output folder writable by every user.

| Grading | Result |
| --- | --- |
| Oracle (upstream's own 1.2.0 source), twice | **1.0** and **1.0**, 4,282 of 4,282 cases; 129 s and 106 s in all, of which the build took 100 s and 87 s |
| Empty submission, twice | **0.0** and **0.0** (no `Cargo.toml`) |
| The oracle with odd files around it: a 5 GB sparse file in `target/`, 20,000 small files, two link loops and a self-link, links outside the project, to a directory and to nothing, a pipe and a socket | **1.0** (96 s) |
| The oracle with a 1.1 GB file outside `target/` | **0.0**, "project over the copy limits", no evaluation error |
| A forced evaluation failure (a case without a recorded answer) | exit 1, no reward file, `evaluation-error.txt` names the case |
| The zoo, 23 projects | every one **0.0**, none with an evaluation error (table below) |

| Stub | Reward | Cases it passes alone | Notes |
| --- | --- | --- | --- |
| nop, silent, exit1, exit2, usual-status | 0.0 | 0, 5, 4, 366, 365 | no-op bodies; their passing cases are all paired with cases they fail |
| accept, reject, deny, allow | 0.0 | 228, 5, 386, 41 | |
| cat, count, echo | 0.0 | 9, 15, 5 | |
| most-common, lookup | 0.0 | 619, 5 | built from the release's own answers |
| wrapper | 0.0 | 0 | the grading image has no `dogwood` |
| hang, flood, forkbomb | 0.0 | 5 each | each misbehaving run fails alone; a run of the forkbomb is bounded by the process limit and ended with its group |
| daemon | 0.0 | 5 | 292 detached processes ended, one per `format` run; 312 s |
| garbage | 0.0 | 0 | deep JSON, mixed rule lists and overlong numbers are compared as printed |
| buildrs | 0.0 | 0 | its build script's leftover process holds the build's output, so the build stops at the 20-minute limit; one `builder` process ended; the reads and the reward write it tries fail |
| forge | 0.0 | 5 | its reward writes, from the build script, from its program and from its leftover process, all fail; `reward.txt` is the grader's 0.0, with no `reward.json` and no link left |
| badexec | 0.0 | 0 | its build leaves a non-program file where `dogwood` belongs; the build is ok, every one of the 4,282 runs fails with "could not start", and there is no evaluation error (18 s). Its first build script assumed cargo's older folder depth and failed to build; it now finds the release folder by name, and was regraded on the same image |

**Grader probes:**
- **Runs share nothing.** The grader's own runner ran a program three times that counts what
  earlier runs left in `/tmp`, `/var/tmp`, `/dev/shm`, `/run/lock`, `HOME`, `TMPDIR` and its
  folder, then writes markers there, leaves a detached process and tries to move its run folder.
  Every run saw 0 markers, the run folder stayed, the 3 leftover processes were ended, and no
  marker was left.
- **Folders every user may write to:** 31 in each image. They are `/tmp`, `/var/tmp`,
  `/run/lock`, and the Rust image's `/usr/local/rustup` and `/usr/local/cargo` trees, which
  nothing in the grading reads back.
- **A grading stopped mid-run:** KILLED-PENDING

**Protection probe as `dev`** (the working machine):
- reading, copying and `dd` of `/usr/local/bin/dogwood` are refused;
- `/proc/<pid>/exe`, `mem` and `maps` are refused;
- `PTRACE_ATTACH` is refused (`EPERM`), and a traced read of its memory fails with `EIO` while
  the same read of `/bin/true` works;
- `LD_PRELOAD` is ignored, while the same library runs in `/bin/true`;
- no core dump is written;
- there is no `sudo`, and `/root` is refused;
- no `dogwood-*` crate or source is on disk, and the registry holds 275 crates.

**Stop hook:** the collect hook ended all 3 of `dev`'s processes, including one that ignores
`SIGTERM` and one in its own session.

## 12. Close-out

- **The flat bundle** (`scripts/package.py`): content hash
  `30413844e28b6e684c229f15e1af1c722a3b9c784eafa72e225217baec2de66a`, with 10,808 files and
  15,440,849 bytes. Packaged twice, the hash is the same.
- **`oddish preflight`** on the bundle: passed. Its one warning, that no `.dockerignore` kept
  `.git` out of the build contexts, was fixed (27a7a867) before the final packaging. Nothing was
  uploaded.
- **Backup:** the final `tests/private/` is in the private store as
  `dogwood-tests-private-phaseC.bundle`, verified, with the refreshed generator bundle and the
  33 mutants; the store's README has a Phase C section. Phase B's bundle is kept.
- **Session length:** one parameter, `task.toml` `[agent] timeout_sec` (34,560 s). The brief
  states no budget, so moving to 43,200 s and a stated 12 hours is a one-line change plus one
  sentence.

## 13. The 12-item gate

| # | Gate | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Inventory complete | **PASS** | 417 ids (256 features, 151 restrictions, 10 out of scope). Every quote is in the shipped guide (not stated: 0). 0 gaps on the final set. Two restrictions are unchecked, with their reasons |
| 2 | Feature-kill matrix | **PASS** | 33 mutants built and run over all 4,282 cases; all 33 killed. 37 ids carry mutant evidence, 228 features use evidence, 140 restrictions refusal evidence. A kill counts only an answer the release never gave in any recorded run |
| 3 | Stub zoo at 0.000 | **PASS** | 23 projects graded by the real grader, every one 0.0; the estimate from recorded answers is 0 units for every table stub |
| 4 | Oracle and nop | **PASS locally** | Oracle 1.0 twice and nop 0.0 twice on the final image. The platform's two runs of each come with the first upload |
| 5 | Determinism | **PASS** | 3 runs and a perturbed fourth give one answer on 4,282 of 4,282 cases; the image's recording adds 3 more; candidates were recorded 6 times; no case changes in 6 or more of 33 mutant runs |
| 6 | Wording sweep | **PASS** | 759 hits on everything the agent sees, 0 unjudged. The build's own answers have 5 residue hits (Cedar's "testing for the attribute's presence", domain sense) |
| 7 | Protection probe | **PASS (local)** | Every attempt as `dev` refused or ignored (section 11), core dumps included |
| 8 | Verifier robustness | **PASS** | The oracle takes about 2 minutes of a 7,800 s limit. With odd files around it, it still scores 1.0; over the size limit, 0.0. A forced failure leaves no reward |
| 9 | Isolation and timeouts | ISOLATION-PENDING |
| 10 | No early stops | **PASS** | No timer or kill in the working machine; the only stop is the collect hook, after the session. The agent's `timeout_sec` is 34,560 s, the brief states no budget, and the verifier's 7,800 s covers the 1,200 s build limit plus 4,282 cases at 1.25 s |
| 11 | Leak scan | **PASS** | 0 cases read only public files, 0 policies equal a public one, 0 near copies |
| 12 | Band check | **PASS** | M-dedup 0.830 (B-dedup only), M-scope 0.950 (B-scope only), M-global 0.900 (K only, 36 of 108 units) |

**The coordinator's six classes from HarfBuzz's QA** (section 6): the comparison framing,
the undocumented flags and the reward forging were found and fixed. The stubs, documented
features, floats and licensing were checked, with the zoo and the notice extended.

## 14. Resources

- **Heavy jobs:** five full pipeline holds on 2026-11-27, and one short regrading hold. The two
  long holds were 18 and 57 minutes; three were stopped early, by me, when they had found what
  needed fixing. Peak memory per container was 3.17 GB (mutant builds).
- **Disk:** about 3 GB while the two task images stood. All of this Phase C's containers,
  images (toolchain, environment, grading), volumes and build-cache records were removed by exact
  name or ID.
- **Waiting:** most of the day went to waiting for the shared lock and for memory above 30%.

## 15. Commits

All are on `neel/dogwood-policy-rebuild` and pushed: e08c74f, 9fa766a, d47191e, f3daff1,
ae20a17, 18b173f, 63d830e0 (the coordinator's checkpoint), eafd7235, db7f9472, 07f2ca37,
97fd330f, 7e4e880c, 2e0056df, f3a25824, 852fc932, 43730c3e, 4b426569, 8d38b6cd, 7c6059cc,
aa1321fa, 44080216, 27a7a867, and the commit that holds this report.
