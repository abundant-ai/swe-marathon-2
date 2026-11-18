# Goose compiler rebuild

Author notes. Nothing in this file is shipped to the candidate or to either image.

The candidate gets an execute-only copy of `goose`, the compiler of the Goose programming
language (github.com/aardappel/goose, Apache-2.0, first published 2026-08-30, pinned at
`745901f`), with its documentation, its standard library's sources, its sample programs and
example runs, and writes a compiler that prints the same output. It is a MirrorCode-style task
on a target too recent to be in the training data of the models it is meant for. It replaces
`markdown-linter-rebuild`, which a cheap model nearly solved in one session (0.991).

The copy is a hardened build (`common/hardening/`): `goose run` runs a program inside the
compiler's own process, so every way for a program to bring code or a raw memory read into that
process is removed, and each build proves it before the image is used.

One step is implemented. See [Remaining work](#remaining-work).

## Development log

### 2026-11-18

- Owner: the linter target is too easy; take a bigger one. Looked at recent permissively
  licensed command-line programs with deterministic output. Chose Goose over Whim (PHP-like,
  so partly known, and about 220,000 lines with networking and databases): a systems language
  with no heap, references whose lifetimes the compiler infers, variable-size enums and
  relative links. About 75,000 lines of C++ compiler, 42,000 lines of documentation including a
  specification, and 4,035 test files. `goose run` compiles a program to C and runs it in
  process through the TinyCC built into the binary; `goose check --diagnostics json` prints
  the compiler's errors as JSON on standard output, so the type and lifetime checker is graded
  as well as program output.
- Case generator (`scripts/make_cases.py`): programs from the test suite (713 with blessed
  outputs, 2,052 that must fail to compile), the samples and the complete programs in the
  documentation. Kinds: `run` (about 40%), `check --diagnostics json` (37%), `format` from
  standard input or `format --check` over a workspace (15%), and the command line's own
  answers (8%). Every comment is removed with a string-aware scanner: the error tests name
  their expected error in comments and many run tests write the expected output after each
  `print`. Visible cases use the samples, the documentation's programs and a fixed 15% of test
  programs; private cases use the other 85% and mutated variants, and a check proves no
  private case holds a visible program verbatim. Programs that import `os`, `ffi`, the
  graphics, audio, physics or ui modules, or local modules, or that the test suite marks
  `no-jit` or `parse-only`, are left out.
- Recording: both images run every case twice with the original and keep the ones that finish
  within the per-run limit and print the same both times; the reward's denominator is the
  number kept.
- Goose prints the absolute path of standard-library files in diagnostics and runtime errors,
  so the standard library sits at `/usr/local/share/goose/stdlib` in the agent image, the
  verifier image and every build (`-DGOOSE_STDLIB_PATH`), with none beside the binary. The
  instruction tells the candidate where it is.
- The reference solution cannot read the execute-only program, so it ships the pinned build
  sources and builds the compiler in the agent container (`cmake`, `g++`), as the images do.
- No local build: this Mac's swap was nearly full. Oddish baselines are the first build.
- First upload (bundle `ca4309ce85fc`, cases from an earlier generator) to test the builds;
  the generator then gained the string-aware comment scanner and edits that always change a
  program. Current bundle `19c1c91c58fc`.

### 2026-11-18 (after the version 2 audit)

- The instruction now says error and warning messages count word for word, against upstream's
  implementation notes. Not uploaded: the owner's rule is that a task is built until it is
  real before any further run.

### 2026-11-19 (adversarial QA wave: passes 01, 04, 06, 10, 16, 19)

- **The original could be read from inside (pass 04, FAIL).** `goose run` compiles the program
  with TinyCC into the compiler's own process. Through `ffi.bytes` (an unchecked memory copy),
  `os.read_file("/proc/self/maps")`, or an `extern fn` of the user's bound to any runtime symbol,
  a twenty-line program printed the compiler's code. Auditing the same process found four more
  ways in: `-D` and `--include` put C of the user's into the program; a sidecar `.build` file
  compiles C into a library the run loads, or names headers it includes; `GOOSE_TCCLIB` points
  TinyCC at the user's headers and support archive. `--stdlib`, `GOOSE_STDLIB` and a `stdlib/` in
  the working directory would have let a user's file count as the standard library, and
  `--unsafe-no-rf-check` is unsound by its own help text.
- **Hardened build.** `common/hardening/goose-hardening.patch` (four files, 24 lines added, 17
  removed) makes the parser refuse `extern` outside the installed standard library
  (`extern fn is only allowed in the standard library`), makes the standard library the installed
  directory alone, drops the four options (each is now an unknown option), refuses any sidecar
  (`sidecar files are not supported`) and ignores `GOOSE_TCCLIB`. `apply.sh` applies it with
  `git apply` (all files or none), deletes `stdlib/os.goose` and `stdlib/ffi.goose`, and fails
  unless every file carries the change. Both images' builder stages and `solve.sh` run the same
  `apply.sh` before `cmake` and `smoke.sh` after it: about 20 runs of the new binary that must
  pass (std's and math's own externs, every standard-library module with externs) or fail with
  the expected message (each refusal above). A build that is not hardened stops there. The patch
  and scripts stay in the builder stage; the final images hold neither. The remaining
  standard-library externs were audited: libm and bit functions, byte scans bounded by their
  slice, a digit writer clamped to its buffer, and the slice pool's span tree, whose runtime
  checks every node number the program can write. None reads memory, a file or the process.
- **Leaked answers (pass 06).** Private cases no longer use shown programs at all (they were 15%,
  as variants), and a private program whose text, comments and whitespace aside, any shipped file
  holds (documentation and design notes, README, samples, standard library) or that equals a
  visible program is left out. The generator refuses to write a private case whose input a shipped
  file or a visible case holds, and packaging checks the same on the real files.
- **Verifier (pass 10, FAIL).** No more stop after 60 slow runs: the 3,300-second total bounds
  time. The workspace is removed without following links (a symlink is unlinked, a directory
  removed with its contents) and made anew; a case that cannot be set up or started counts as
  failed, never as an evaluation error. Standard output is read in pieces up to 4 MB (no output
  the recorder keeps is longer) and more is a failed case. Between cases the verifier kills the
  unprivileged user's processes, and at the end removes what that user left in `/tmp`,
  `/var/tmp` and `/dev/shm`, so the results can be written.
- **Cases (passes 01, 16, 19).** The generator was rewritten around a tokenizer that mirrors
  `src/lexer.h` (it reads 2,979 of upstream's 2,986 Goose files; the other seven are lexer-error
  tests):
  - layout changes for format inputs touch only whitespace between tokens and join two tokens
    only where they still lex apart, so no operator is split (was 29% of format inputs);
  - format inputs carry comments: the program's own where no other case is built on the same
    program, otherwise neutral ones (own-line, trailing runs sharing a column, documentation,
    block and nested block comments). `src/format.h:1-10` and `CheckSame` (`:710-737`) confirm
    that the formatter keeps every comment;
  - every case is changed so that its answer differs from what upstream publishes: identifiers
    renamed consistently to names nothing else uses (never a standard-library, builtin or
    reserved name), blank lines and indentation added so positions move, and for 95% of run
    cases a literal or a string changed. Cases left exactly as upstream wrote them fell from
    592 (39.5%) to 6; an estimate puts the run cases still printing upstream's expected file at
    about 45 (3%), and `verifier/recording.py` counts them exactly when the image is built;
  - the command line has one case per behaviour (36, was 108 for 20 answers);
  - `run --diagnostics json` only where the program has diagnostics: on programs that do not
    compile (a new kind, 129 cases, 96 with JSON) and on the run tests that declare warnings (9);
  - new kinds: programs that import the standard-library modules written in Goose (50),
    programs over several files (54: upstream's local-module tests and 27 benchmark programs with
    their `rng` module, sized down to a fraction of a second);
  - programs that use threads (out of scope) or packages are left out; programs with block
    comments are now usable.
  - Standard input and program arguments reach a Goose program only through `os`, which the
    hardened build removes, so no case reads them; 26 run cases pass arguments after `--`.
- **Instruction.** The goal is now a clean-room policy (documentation, standard library and the
  released binary, never the source), with the consumers of exact output named: CI golden files,
  an editor plugin that parses `--diagnostics json`, scripts on exit codes. A context line lists
  where the deployment build differs from the documentation, and calling C (`extern` functions
  and blocks, sidecars) is out of scope. How diagnostics are compared is unchanged.
- Not built or uploaded: no local Goose build on this Mac. Oddish preflight passes on bundle
  `f98273d8a455`. The first baselines are also the first proof that the patch builds.

### 2026-11-19 (round 2: the rest of QA pass 10)

- **A set-id file could run as root (F6, must-fix).** The backoffice task's QA found that on
  Oddish's Docker backend a submitted file can arrive set-user-id root. Before any submitted code
  runs, the verifier now:
  - seals `/app/rebuild` in place: root-owned, no set-id or sticky bit, executables 0755, other
    files 0644, directories 0755, links left as they are, devices, pipes and sockets removed. It
    stays where it is, since a submission may name its own files by absolute path, and it cannot
    rewrite itself between cases;
  - runs submitted code through `setpriv --reuid nobody --regid nogroup --clear-groups
    --no-new-privs`, and fails closed (no reward file) unless a process started exactly that
    way shows `NoNewPrivs: 1`, the unprivileged user and group in all four ids, no
    supplementary group, no permitted, effective or ambient capability, and the process, file
    size and core limits;
  - copies `id(1)` beside the submission as a set-user-id and set-group-id root file, runs it
    the same way and fails closed unless it reports `nobody` and `nogroup`: a set-id file gains
    nothing.
- **Resource limits (F6, F8).** Every run, at recording, in the examples runner and in grading,
  starts with the same limits: an 8 MB stack (`goose run` runs programs on the main thread, so the
  deep-recursion cases end at the same depth everywhere), 512 processes (only where root starts
  the run), 256 MB files, no core files, and 256 GB of writable mappings. The data bound is high
  on purpose: the original reserves 2 GB of address space per data stack (`MAP_NORESERVE`, which
  `RLIMIT_DATA` counts) and silently takes smaller stacks when refused. Memory is guarded instead
  by priority: the verifier sets its own `oom_score_adj` to -1000 and every run's to 1000.
- **Run times (F4).** The recorder times both runs of each case and keeps only those that finish
  in at most 0.5 seconds both times, a quarter of the limit; `recording.json` gives the cases
  left out as slow or unsteady, by kind, and the kept runs' maximum, 99th percentile and total.
  The recording fails if more than 15% of cases are unsteady or fewer than 60% are kept.
- **Bytes (F7).** Standard output is compared byte for byte (two different invalid bytes no
  longer compare equal); the recorded file holds it as text with surrogate escapes. More than
  1,000,000 bytes fails a run.
- **Run conditions in the instruction (F5).** It now says, as behaviour: an unprivileged user that
  cannot write to `/app/rebuild`, a new working directory under `/tmp` holding only the run's
  files, `HOME` at `/tmp` with nothing left there from earlier runs, and the same resource
  limits as `run_examples.py`. The verifier makes that true: before each case it kills the user's
  processes and removes what the user left in `/tmp`, `/var/tmp` and `/dev/shm`.
- **Metrics (F10).** `metrics.json` gives cases run, passed and failed overall and by kind,
  timeouts, outputs over the limit, setup errors, the total and longest run time, why it stopped
  (if it did), the limits the sandbox has, and the recording's description.
- **Trivial floor (F9).** A one-line `exit 1` script passes at least 46 of the 1,500 private cases
  (3.1%): 13 command-line errors and 33 runs of programs that do not compile without
  `--diagnostics json`. `exit 2` passes at least 1 (`format --check` of a missing file). Printing
  nothing with exit 0 passes an unknown number (programs that print nothing, `format --check` over
  files that need nothing). The exact counts, after the recording's drops, are
  `empty_stdout_by_exit` in `recording.json`, which the first baseline's `metrics.json` carries.
- **Smoke test.** Its positive program now checks `popcount(255) == 8` and `sqrt(16.0) == 4.0` with
  `assert` and prints one word; the build compares only the exit status and that word. Upstream
  confirms the old format anyway (`test/stdlib/stdlib_bits.goose:12` prints `true true true`).
- Cases unchanged (private `cdc3a904`, visible `d3cb403c`). Preflight passes on bundle
  `5cb265da1a10`. Still not built.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-rebuild-compiler` | Implemented: instruction, agent image with the execute-only compiler, separate verifier image, reference solution. |
| Further steps | Not designed. Candidates: the next upstream commits from their changelog; `goose build` with an external C compiler. |
| Hardening | `common/hardening/`: the patch, `apply.sh` (before each build) and `smoke.sh` (after it), staged by packaging into both images' build contexts and the solution. |
| Private inputs | `steps/01-rebuild-compiler/tests/private/cases.json` and `experiment/visible.json`, Git-ignored, from `scripts/make_cases.py`. Outputs are recorded when the images are built; `recording.json` beside them describes the recording and appears in `metrics.json`. |
| Upstream source | Not in Git. Packaging stages the build sources less `stdlib/os.goose` and `stdlib/ffi.goose` (into both images and the solution) and the documentation and samples (into the agent image) from a checkout at the pinned commit. |
| Oracle | The original compiler, built by `solve.sh` from the shipped sources with the images' hardening and flags. |
| Ratings (`harbor check`) | Not run. |

## Design dimensions

### Novelty

MirrorCode (Epoch AI and METR) has the same setup: an execute-only program, its
documentation and visible tests, graded on held-out tests. The difference is the target: a
whole language implementation first published after the training cutoff of the models under
test, with a memory model no other language has. SWE-Marathon v1's `rust-c-compiler` builds a
compiler to a public standard the models know; here the language is only in the shipped
documentation.

### Verifiability

Standard output and exit code are compared exactly; every kept case printed the same output
twice from the original. Partial progress is the share of cases that match.

### Realism

A clean-room implementation, written from the manual and the released binary by a team that may
not read the source, is how compatible second implementations are made (Wine, Samba, the PC
BIOS). The exact bar has real consumers: golden files recorded from the compiler and editor
tooling that parses its JSON diagnostics. The documentation, samples and standard library are
the upstream's own; cases include programs that do not compile, programs over several files,
the standard library's Goose modules and commented code to format.

### Difficulty

A rebuild needs a parser for a new syntax, a type checker with inferred lifetimes and its
exact error messages, an implementation that runs programs with the same output (including
aborts and their exit codes), a formatter that keeps comments, and the command line. The linter
it replaces was 12,000 lines; this target is about 75,000 lines of C++, of which about 35,000 to
50,000 are in scope (MirrorCode's large bucket), and its error messages come from a novel
analysis. The upstream compiler was written with AI in the image of its author's Lobster; that
lends architecture, not the graded behaviour. QA passes 17 and 19 expect 0.25 to 0.55 for a
strong model in one session. Not yet measured with a model.

### Initial feasibility

Solved by construction: the original passes every kept case. For an agent, unknown.

## Workload

A run is one trial of 9.6 hours (one task row per experiment, no continuation tasks). The
instruction states no time budget.

## Verification

1. `/app/rebuild` arrives as the declared artifact.
2. The verifier checks the unprivileged run first (no_new_privs, ids, groups, capabilities,
   limits, and a set-id root copy of `id` that must report `nobody`), then seals `/app/rebuild`:
   root-owned, read-only for anyone else, no set-id bits. Any failure of either is an evaluation
   error, before submitted code runs.
3. Before each case it kills every process of `nobody`, removes what `nobody` left in `/tmp`,
   `/var/tmp` and `/dev/shm`, and writes the case's files into a new `/tmp/goose-case`, owned by
   `nobody`. `/app/rebuild/goose` runs there as `nobody` with no_new_privs, the case's arguments
   and standard input, no network, the recorder's resource limits, 2 seconds, and at most
   1,000,000 bytes of output.
4. A case passes when the exit code and the bytes of standard output equal the recorded ones. A
   case that cannot be set up or started, runs too long or prints too much fails; none of that is
   an evaluation error.
5. After 3,300 seconds of runs in all the verifier stops, and the rest count as failed (1,500
   runs at the 2-second limit take about 3,000; every kept case took at most 0.5 seconds when
   recorded). At the end it cleans up after `nobody` again, then writes the results.

### Reward formula

```
reward = cases_passed / cases_kept
```

- Continuous, fixed denominator per image build (the private cases kept by the recording).
  No executable: reward 0.
- An evaluation error (not root, privileges cannot be dropped or the drop does not hold, the
  submission cannot be sealed, private inputs unreadable) leaves no reward file.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verify.py` and `tests/verifier/runcases.py`; `tests/verifier/recording.py`
  describes the recording (cases kept by kind, cases left out as slow or unsteady, run times,
  run cases that print upstream's expected file, cases a program that prints nothing would pass)
  for `metrics.json`.
- Floor: an `exit 1` script passes at least 46 of 1,500 private cases (3.1%); see the log entry
  of the second 2026-11-19 round for the rest.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 2, 3, 5, 10).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read, copy, trace or dump the compiler from outside its process | File mode and group of the program in the agent image | QA pass 04, finding 2 (reasoned, not run) | `/opt/goose/goose` is `root:goose`, mode 2711: execute-only and setgid, so secure execution ignores `LD_PRELOAD` and the process is not dumpable | A traced exec drops the gid; Linux still makes a process that runs a file it cannot read non-dumpable, but the sandbox runtime on Oddish was not tried | Probe as `candidate` on Oddish | 🟡 YELLOW / UNASSESSED |
| 2 | Read the compiler from inside its process: `goose run` compiles the program into the compiler with TinyCC | Hardened build (`common/hardening/`) | QA pass 04, finding 1 (a 20-line program printed the code through `ffi`, `os` and a user `extern`); four further ways in found by the audit | No `os` or `ffi` module; `extern` only in the installed standard library; no `-D`, `--include`, `--stdlib`, `GOOSE_STDLIB` or `GOOSE_TCCLIB`; no sidecars; no unsound option. `smoke.sh` proves each refusal at every build of both images and of the solution; the remaining standard-library externs read nothing outside their arguments (audited) | A memory-safety bug in the compiler, its runtime or TinyCC; `embed_file` still reads, at compile time, any file the candidate can read anyway (the binary is not one) | The first build's smoke test, then pass 04's programs run as `candidate` on Oddish | 🟡 YELLOW / UNASSESSED |
| 3 | Run as root, or as a user who can read the program | `[agent] user` on Oddish | Not tested on this task | `user = "candidate"` | Depends on each harness | Short trial that prints `id` | 🟡 YELLOW / UNASSESSED |
| 4 | Deliver a wrapper that calls the original | Separate verifier image | By design | The final verifier image holds no copy of the compiler | None found | Keep | 🟢 GREEN / LOW |
| 5 | Fetch the public source | Agent network policy | Not probed on this task | `network_mode = "no-network"` for the agent; the source is not in the agent image | The repository is public; a harness with network access would defeat the task | Probe from a trial | 🟡 YELLOW / UNASSESSED |
| 6 | Lookup table over the visible cases or the shipped programs | Private cases | QA pass 06 (229 cases on shipped programs, one private test printed in a design note); by check since | No private case is built on a shipped program or a variant of one; a private program that a shipped file holds or that equals a visible program is left out; the generator and packaging refuse a private case whose input a shipped file or a visible case holds (checked) | Upstream tests that differ from a visible one by a few tokens (pass 06, note 4) | Keep | 🟢 GREEN / LOW |
| 7 | Read expected output or errors out of the case files, across cases | Case generation | By check | No run or check input has a comment (the tests write expected errors and outputs in comments). Format inputs carry the program's own comments only where no other case is built on that program, since a submission could keep notes between cases in `/tmp`; otherwise neutral ones (checked) | A comment that reveals another program's answer | Read trajectories | 🟢 GREEN / LOW |
| 8 | Recall upstream's published answers (tests beside their expected files) | Case generation | QA pass 19, finding 2 (39.5% of cases were upstream tests unchanged) | Every case renamed, moved or edited so its answer differs; 6 private cases unchanged; about 45 run cases (3%) estimated to still print upstream's expected file, counted exactly by `recording.py` at build | A model that recalls a test and also runs it correctly; that is the work | Read `recording` in the first baseline's `metrics.json` | 🟢 GREEN / LOW |
| 9 | Tamper with the reward files, or suppress them by forcing an evaluation error | Separate verifier container | QA pass 10 (a symlinked workspace forced an evaluation error) | Verifier starts fresh with only `/app/rebuild`; the submission runs as `nobody`; the workspace is replaced without following links; a case that cannot be set up or started, runs too long or prints too much fails that case; `nobody`'s processes are killed and its files removed before every case and before the results are written; its runs hold the out-of-memory killer's first claim and the verifier none (checked) | Exhausting the disk within one case faster than the per-case cleanup | Keep | 🟢 GREEN / LOW |
| 11 | Run as root in the verifier through a set-user-id or capable file in the submission, then read the recorded answers | Privilege drop and sealing | QA pass 10, F6, and the backoffice task's QA (a submitted file can arrive set-user-id root on Oddish's Docker backend) | The submission is sealed root-owned without set-id bits before anything runs; `setpriv --no-new-privs` keeps any file from adding privileges; a process started that way must show no_new_privs, the unprivileged ids, no groups and no capabilities, and a set-id root copy of `id` must report `nobody`, or nothing is graded (checked: sealing and the refusals) | A kernel or runtime that ignores no_new_privs; the run-time probe then refuses to grade | First baseline's verifier log | 🟢 GREEN / LOW |
| 10 | Infer an evaluation from the files and text | Instruction and example files | Lesson from `markdown-linter-rebuild` | Neutral runner text; no reference, grading, session or time wording (checked) | An agent can still guess that more cases exist | Read the first trajectories | 🟡 YELLOW / UNASSESSED |

The original also prints the C of its own runtime and of any program (`--emit-runtime`, `-o`),
as upstream documents. That shows how programs are lowered and how values print, not the
parser, checker or formatter; a candidate may use it like any other output of the original.

Licence: the upstream is Apache-2.0. Its `LICENSE` is shipped with the documentation in
`/app/docs` and with the reference solution's build.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (20 tests) with `ci_checks` (27), Python 3.13, and `check_repository.py` | working tree, 2026-11-19, round 2 | pass |
| Oddish preflight | bundles `ca4309ce85fc`, `19c1c91c58fc`; `f98273d8a455` (hardened build, new cases); `5cb265da1a10` (verifier round 2) | pass |
| Hardened build | bundle `5cb265da1a10` | not built yet: `apply.sh` tested on a pristine copy of `src/` (applies once, refuses twice), `smoke.sh` tested against stand-ins that do and do not refuse |
| Privilege drop | bundle `5cb265da1a10` | not run as root yet: sealing and the refusal of a weak drop are checked; the drop itself, the status check and the set-id probe first run in the first baseline |
| Oddish baselines, version 1 | bundle `ca4309ce85fc` (earlier generator), task `...goose-compiler-rebuild-9979b548`, experiment `goose-compiler-rebuild-20261118` (https://www.oddish.app/experiments/4b947cc6), one row | reference 1.0 twice (1,500 of 1,500: the recording kept every case), no-op 0.0 twice. First build of both images and of the solution's compiler; Archil, no fault |
| Oddish baselines, version 2 | bundle `19c1c91c58fc` (current generator), same task, experiment `goose-compiler-rebuild-v2-20261118` (https://www.oddish.app/experiments/f14b3da8), one row | reference 1.0 twice (1,500 of 1,500), no-op 0.0 twice |
| Oddish source audit, version 2 | trial 13 | no must-fix finding. Two should-fix: upstream's `docs/implementation.md` says an equivalent implementation need not reproduce diagnostic wording, while the JSON diagnostics are compared exactly (answered in the instruction since); the example outputs are recorded at build time and cannot be inspected in the package (kept: the original must produce them) |
| `harbor check` | none | not run |

## Build and deliver

```bash
git clone https://github.com/aardappel/goose <checkout> && git -C <checkout> checkout 745901fd48224feb782d707922a20dcd25c669fd
cd tasks/swe-m2-software-engineer/goose-compiler-rebuild
python scripts/make_cases.py <checkout> --count 1800 --seed 20261118 --visible 300 \
    --out-private steps/01-rebuild-compiler/tests/private/cases.json --out-visible experiment/visible.json
GOOSE_CHECKOUT=<checkout> python scripts/package_step.py        # add --flat for a bundle without steps
```

The hardening lives in `common/hardening/`: packaging stages it into both build contexts and the
solution, and every build runs `apply.sh` before `cmake` and `smoke.sh` after it.

## Remaining work

- Baselines of the current bundle under a new experiment (one row): the first build of the
  hardened compiler, whose smoke test must pass in both images and in the solution, and the
  first run of the privilege checks as root. Read `recording` in the reference run's
  `metrics.json` (cases kept by kind, slow and unsteady drops, run times, run cases that still
  print upstream's expected file, the exact floor) and `limits`. Then the platform's source
  audit. Model trials wait for the owner.
- Probe findings 1, 2, 3, 5 and 10 from a trial; run pass 04's programs as `candidate`.
- Open: a deterministic subset of `os` (standard input, arguments, files in the workspace) would
  bring input-reading programs back without `ffi` (pass 01, F4); the exact diagnostics bar is the
  owner's call (pass 01, F1).
- `harbor check` and ratings.
