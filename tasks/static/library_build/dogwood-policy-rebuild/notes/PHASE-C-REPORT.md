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

RESULTS-PENDING
