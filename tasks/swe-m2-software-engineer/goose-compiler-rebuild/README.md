# Goose compiler rebuild

Author notes. Nothing in this file is shipped to the candidate or to either image.

The candidate gets an execute-only copy of `goose`, the compiler of the Goose programming
language (github.com/aardappel/goose, Apache-2.0, first published 2026-08-30, pinned at
`745901f`), with its documentation, its standard library's sources, its sample programs and
example runs, and writes a compiler that prints the same output. It is a MirrorCode-style task
on a target too recent to be in the training data of the models it is meant for. It replaces
`markdown-linter-rebuild`, which a cheap model nearly solved in one session (0.991).

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

## Current implementation

| Part | State |
| --- | --- |
| Step `01-rebuild-compiler` | Implemented: instruction, agent image with the execute-only compiler, separate verifier image, reference solution. |
| Further steps | Not designed. Candidates: the next upstream commits from their changelog; `goose build` with an external C compiler. |
| Private inputs | `steps/01-rebuild-compiler/tests/private/cases.json` and `experiment/visible.json`, Git-ignored, from `scripts/make_cases.py`. Outputs are recorded when the images are built. |
| Upstream source | Not in Git. Packaging stages the build sources (into both images and the solution) and the documentation and samples (into the agent image) from a checkout at the pinned commit. |
| Oracle | The original compiler, built by `solve.sh` from the shipped sources with the images' flags. |
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

Keeping a tool alive after its vendor is gone, from the binary and the manual, is real work.
The documentation, samples and standard library are the upstream's own.

### Difficulty

A rebuild needs a parser for a new syntax, a type checker with inferred lifetimes and its
exact error messages, an implementation that runs programs with the same output (including
aborts and their exit codes), a formatter, and the command line. The linter it replaces was
12,000 lines; this target is about 75,000, and its error messages come from a novel analysis.
Not yet measured with a model.

### Initial feasibility

Solved by construction: the original passes every kept case. For an agent, unknown.

## Workload

A run is one trial of 9.6 hours (one task row per experiment, no continuation tasks). The
instruction states no time budget.

## Verification

1. `/app/rebuild` arrives as the declared artifact.
2. Each private case is written into `/tmp/goose-case`, owned by `nobody`, and
   `/app/rebuild/goose` runs there as `nobody` with the case's arguments and standard input,
   no network, 2 seconds.
3. A case passes when the exit code and standard output equal the recorded ones.
4. After 60 runs that exceed 2 seconds, or after 3,300 seconds of runs in all, the verifier
   stops; the rest count as failed.

### Reward formula

```
reward = cases_passed / cases_kept
```

- Continuous, fixed denominator per image build (the private cases kept by the recording).
  No executable: reward 0.
- An evaluation error (not root, privileges cannot be dropped, private inputs unreadable)
  leaves no reward file.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verify.py` and `tests/verifier/runcases.py`.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 2, 4, 8).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read or copy the compiler instead of rebuilding it | File mode and group of the program in the agent image | Not attacked | `/opt/goose/goose` is `root:goose`, mode 2711: execute-only, setgid (secure execution ignores `LD_PRELOAD`, the process is not dumpable and cannot be traced by the candidate) | A runtime that ignores the setgid bit and also lets a tracer read a non-dumpable process; a static build would remove the loader, but TinyCC's in-process JIT was not tried that way | Probe as `candidate` on Oddish | 🟡 YELLOW / UNASSESSED |
| 2 | Run as root, or as a user who can read the program | `[agent] user` on Oddish | Not tested on this task | `user = "candidate"` | Depends on each harness | Short trial that prints `id` | 🟡 YELLOW / UNASSESSED |
| 3 | Deliver a wrapper that calls the original | Separate verifier image | By design | The final verifier image holds no copy of the compiler | None found | Keep | 🟢 GREEN / LOW |
| 4 | Fetch the public source | Agent network policy | Not probed on this task | `network_mode = "no-network"` for the agent; the source is not in the agent image | The repository is public; a harness with network access would defeat the task | Probe from a trial | 🟡 YELLOW / UNASSESSED |
| 5 | Lookup table over the visible cases or the shipped programs | Private cases | By design and by check | Private cases come from test programs never shipped, or from mutated variants; no private case holds a visible program verbatim (checked) | None found | Keep | 🟢 GREEN / LOW |
| 6 | Read expected output or errors out of the case files | Case generation | By check | Every `//` comment is removed (the tests write expected errors and outputs in comments); a check fails on any `//` left in a case | A test whose expected output is visible some other way | Read trajectories | 🟢 GREEN / LOW |
| 7 | Tamper with reward files | Separate verifier container | By design | Verifier starts fresh with only `/app/rebuild`; submission runs as `nobody` | None found | Keep | 🟢 GREEN / LOW |
| 8 | Infer an evaluation from the files and text | Instruction and example files | Lesson from `markdown-linter-rebuild` | Neutral runner text; no reference, grading, session or time wording (checked) | An agent can still guess that more cases exist | Read the first trajectories | 🟡 YELLOW / UNASSESSED |

Licence: the upstream is Apache-2.0. Its `LICENSE` is shipped with the documentation in
`/app/docs` and with the reference solution's build.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (6 tests) | working tree, 2026-11-18 | pass |
| Oddish preflight | bundles `ca4309ce85fc`, `19c1c91c58fc` | pass |
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

## Remaining work

- Baselines of the current bundle under a new experiment (one row), then the platform's
  source audit. Model trials wait for the owner.
- Probe findings 1, 2, 4 and 8.
- `harbor check` and ratings.
