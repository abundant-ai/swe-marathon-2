# BasedPL interpreter rebuild

Author notes. Nothing in this file is shipped to the agent or to either image.

The agent gets an execute-only copy of `bpl`, the interpreter of the BasedPL array language
(github.com/AnswerDotAI/basedpl, Apache-2.0, first published 2026-09-16; pinned at tag v0.1.95,
commit `af3609a9348471494d2bed952cbbf2a5ecdbd53e`, 2026-11-18), and its documentation, and
writes an interpreter that prints the same output. This is idea 9 of the owner's sheet, "no
examples": MirrorCode with only the binary and the docs. Unlike the Goose task it ships no example
runs, no expected outputs, no runner and no tests; the agent finds out what the interpreter does
by running it. A judge panel chose the target (harbor-lh `ops/swe-marathon-v2/decisions/`).

The copy is a hardened build (`common/hardening/`), built once on the author's machine and
installed unchanged in both images and in the reference solution. One step is implemented. QA
waves 1 and 2 (20 passes) have been answered in rounds 1 and 2; bundle `7462d71fe5a7` replaces
the retired `4164eb806274`. See [Remaining work](#remaining-work).

## Development log

### 2026-11-19 (rounds 1 and 2: QA waves 1 and 2)

- **QA.** Wave 1 (01, 04-08, 10, 12-14) and wave 2 (02, 03, 09, 11, 15-20): 9 FAIL, 11 CONCERN.
  Reports and summary: harbor-lh `ops/swe-marathon-v2/qa/basedpl/`. Every must-fix is answered
  below; the should-fixes not taken are listed with a reason at the end of this entry. Bundle
  `4164eb806274` is retired: it carried the Goose round-5 verifier.
- **Delivery and the egress window** (04, 07, 08; decision `2026-11-19-egress-window-DECISION.md`).
  The platform reopens public egress after the agent's turn and before `/app/rebuild` is
  collected. `environment/prepare-delivery` is the task's one `[[verifier.collect]]` hook, as
  root. It records whether TCP 443 on pypi.org and github.com answers (3 s each) and every live
  process of `dev` with its command line, then kills them with `kill -9 -1` as `dev` until none
  is left. It gives back the 64 MiB and 64 inodes that `reserve-delivery-room` set aside at setup
  (`setup_begin` and `setup_complete`), and fixes links as `dev`. Then, as root, it walks
  `/app/rebuild` by directory descriptor, removes what Harbor's copy would refuse, and refuses
  the delivery past 100,000 entries, 1 GB or 1,000-byte paths, or when a `tar -czf` of it fails
  or takes more than 100 s. It writes `.delivery.json` (the egress check, the processes, the
  kill rounds, and every entry with size, mtime, ctime and sha256) and the `.delivered` mark.
  All of this is ported from the back-office task's rounds 6-7. `verify.py` treats nothing
  arriving, or a mark that counts more than arrived, as an evaluation error. It writes the
  record to `metrics.json` (`delivery_record`), outside the reward. It refuses any delivered file
  whose sha256 is one of the 12 builds upstream publishes for 0.1.95: three release binaries
  and nine Python extensions, recorded by `scripts/upstream_builds.py`, hashes only. It also
  refuses any file holding the unhardened usage text `--kernel -f CONNECTION_FILE`, and a missing
  or malformed marker is an evaluation error (13 F4). The instruction states the copy's limits.
- **Verifier** (10, 11, 12, 13, 20). Goose round 6 (`1c81537`) is ported. The reward is reserved
  as `.reward.tmp` and renamed onto `reward.txt` only at the real end. Less than 512 MB free
  before grading, or after a cleanup mid-evaluation, is an evaluation error. Free space at the
  start and end, the evaluation's wall time and the summed cleanup time are in `metrics.json`,
  and shared memory counts by its creator too. The disk and file limits count only the run's
  own files: what its uid owns under the directories it can write to, plus deleted files it
  still holds open. They are counted only when `/tmp`'s or `/dev/shm`'s free figures fall past a
  limit, so other writers never stop a run. A case stopped by the memory, disk or file limit runs
  once more. A run that ended before its deadline is drained, not timed out. The run directory is
  `/tmp/bpl-run`. `TOTAL_SEC` is 4,200 and both verifier timeouts are 4,500: 1,778 generated cases
  at 2.1 s plus margins fit, and the check reads the generator's counts.
- **Images** (04, 12, 20). `sudo` is gone from the agent image. In the agent image's final
  stage, the installed set-group-id build runs the whole smoke test as `dev`. That includes a new
  unprivileged section: from `/`, `/opt` and `/opt/bpl`, reads of the build itself and of
  `/proc/self/exe` must be refused by the kernel or the path rule, and any failure stops the
  build. The patch's path rule lets the build's own path through from `/`, so the 2711 mode is
  what refuses it, and it is now proved as `dev`. `solve.sh` records the same reads as `dev` in
  `/logs/agent/reads.txt` for the first oracle trial.
- **Instruction** (01, 03, 09, 15). The requester's reasons now hold:
  - client data keeps scripts and golden files inside CI;
  - a legal policy of clean-room provenance applies to anything embedded for years, for a release
    upstream will not support.

  Worker replies must reproduce byte for byte, because saved notebooks keep them. The run
  conditions read as the job runner's behaviour, with no harness path and no "case" or "tests".
  The clean-room rules cover the build. Crashes need not be copied, and the out-of-scope features
  have reasons; code that mentions them must still load. The scope is stated as the whole manual:
  every glyph and system function page, `∂`, the worker protocol and the command line.
- **Cases** (02, 05, 06, 13, 14, 16-19).
  - Error cases print a computed value before the error (`LEADS`), never a literal an echo could
    copy. 60% of uncaught errors, and every syntax error, run as worker requests, whose replies
    carry the kind, message, span and display. Guards always print the message.
  - Worker sessions keep notebook state: definitions then uses, a function then calls, a display
    setting then values, a bound name used again.
  - Stdin cases are multi-line records, and the piped ones get a failing line at a statement
    boundary.
  - Display settings are chosen to suit the value.
  - Differentiation records are thinned to 5.7% of kept cases, from 12.1%.
  - The kind counts were rebalanced.
  - Fixes: a `_` subscript needs a digit (six cases had become undefined-name errors); no literal
    next to `=` or `≠` is rewritten; the leak index holds every run of 2-6 consecutive documented
    statements; and the leak check covers every rewrite the recorder may settle on.
- **Recording** (05, 11, 13, 17, 18).
  - Three main runs pinned to four worker threads, plus the perturbed run.
  - Memory text on standard error also counts as machine-dependent.
  - A display case is kept only if its setting changes what it prints.
  - A rewrite whose answer is all zeros, empty or false is passed over.
  - `expected_sha256` is written.
  - Answers showing the maths library's last bits are dropped: a float to 15 or more digits, an
    exponent of -12 or below, or a 32- or 16-bit float, from code using circular functions,
    exp or power, gamma, matrix division, decompositions or numeric inverses. Worker replies
    are judged one by one.
  - `recorder.no_interpreter` is the strongest dispatcher the reports describe: the command
    line's table, an echo of leading literals then exit 1, and one constant per visible shape.
    `select` holds it to 5%, and the recorder fails the build above that.
- **Measured** (stand-in recording `experiment/local-recording-6`, cases `01f5d1d2`): 1,673 of
  1,778 kept. Dropped: 86 whose display setting changed nothing, 16 showing last bits, 3 whose
  input holds the answer; none unsteady, crashed, machine-dependent or perturbed. The
  no-interpreter dispatcher passes 2.1% as measured by the recorder, and 1.85% when run as a
  program against the packaged bundle. The largest answer is 0.5%; nothing with exit 1 is 0.5%.
  APL ports are 7.1%, and cases in upstream's code form 214 (133 of them error records). Grading
  from the packaged bundle gives the stand-in reference 1.0 (1,673 of 1,673, 29.5 s), the no-op
  exactly 0, and the dispatcher 0.0185. The stand-in is upstream's unhardened macOS build, so
  the dispatcher's table of its `--help` holds the usage text the verifier refuses; that one
  refusal was switched off for the measurement.
- **Not taken, with reasons.**
  - A static PIE: no second build is allowed here. The 2711 mode, proved as `dev`, covers the
    path rule.
  - Upstream's `lib/*.bpl` stay out of the image (18 F2). The module cases run them as hidden
    library code. Shipping them would also ship the code that 39 module cases keep verbatim, and
    a gap in an implementation's reader shows up across those cases anyway.
  - The temperatures template still prints means with long floats (18 F3), as part of the tail.
  - The 25 program templates stay (02 F5).
- **Checks.** 43 task checks and the 27 repository checks pass with Python 3.13, and
  `check_repository.py` passes. Bundle `7462d71fe5a7` (248 files, 33,253,911 bytes) was built
  twice with the same hash, and Oddish preflight passes.

### 2026-11-19

- Started from the judge panel's choice for idea 9 ("no examples"): BasedPL, pinned at v0.1.95.
  The hardening patch, the pinned `Cargo.lock` and the local build script are in place; the
  rest of the task follows.
- **Target.** BasedPL is an APL-family array language from Answer.AI: Rust, about 31,000 lines
  in its core crate (`src/`, 84 files) plus the command line, a Cranelift JIT and a test kit. Its
  notation is new (runs grouped by spaces, `[…]` vectors, `ₓ`/`ᵣ` number kinds, `ᵇ` bitwise
  lifting, keyed axes, error guards with `$e`), its number tower has exact integers of several
  widths, rationals, complex numbers and three float widths, and its display, `⍕` formatting,
  error messages with source carets and the `--worker` JSON protocol are all exact text. The
  documentation is 215 pages (863 KB as shipped): the guides, a page per glyph and per system
  function, and the study notebooks.
- **Hardening patch** (`basedpl-hardening.patch`, nine files, 64 lines added, 109 removed;
  `apply.sh` applies it with `git apply`, all or nothing, and fails unless every file carries the
  change and nothing it removes is left):
  - `src/host.rs`: every file read (`•nget`, `•load`, `•image`, and through `src/lib.rs` the
    command line's program file) opens the file, takes its real path from `/proc/self/fd`, and
    refuses it unless it lies under the working directory the process started in and outside
    `/proc`, `/sys` and `/dev` (a link, `..` or a swapped link leads nowhere else);
    `•fetch` returns an error and never starts upstream's `curl`.
  - `src/data.rs`, `src/files.rs`: `•nput` writes no file (`"-"`, standard output, still works);
    `•metadata`, `•readdir`, `•copy`, `•rename`, `•remove` and `•mkdir` refuse.
  - `jit/src/lib.rs`: `Kernel::compiled` always declines, so no machine code is generated from a
    program (Cranelift is never called); stages run on their precompiled kernels.
  - `cli/src/cli.rs`, `cli/src/main.rs`: no `--kernel` (Jupyter, sockets) and no `--costs`
    (timings of files); the usage text matches. `cli/src/worker.rs`: the worker serves `code`,
    `call` and `bindings` only, not the test kit's `case`, `check`, `reference`, `page`, timing
    and route requests, which read files. `cli/src/editor.rs`: no REPL history file.
  - `cli/src/main.rs`: a build marker (`BPL-BUILD-MARKER-` and 32 hex digits, from
    `cli/src/build_marker.txt`), kept in the binary by `std::hint::black_box` and never printed.
  - Audited and left: BPL has no FFI and no shell; the `bpl` binary links no Python (the `py`
    crate is a separate extension); `•host "env"` shows only the caller's own environment.
  - Non-deterministic features are kept out of every case rather than patched (the panel allowed
    either): random numbers, the clock, plots and images, `•uuid`'s random versions, `•index`'s
    fresh names, and the interpreter's reports on itself. The JIT is patched out because it also
    generates code in the process.
- **One build** (`scripts/build_original.py`, the one local build allowed on this Mac): Rust
  1.100.0, `cargo zigbuild --release --locked --target x86_64-unknown-linux-musl -j 2 -p
  basedpl-cli --no-default-features` with upstream's own flags (`-C target-cpu=x86-64-v3`,
  `-Zshare-generics=yes`), stripped, every local path remapped. 4 min 38 s; one warning (fields
  of `•fetch`'s request never read). The result is static (no `PT_INTERP`, so no loader and no
  `LD_PRELOAD`) but not a PIE: zig's musl link does not produce `-static-pie`, and a second build
  was not allowed. 36,003,624 bytes, sha256 `60d2aed1d5b77ae8eeb74687a283bb9538577c2092dea283ba2704ccb9c5d27a`;
  the zero marker occurs once; no local path is embedded. `Cargo.lock` (281 packages; rustymath
  0.1.63, the rustyline and plotters forks at fixed commits) is pinned in `common/hardening/`,
  since upstream commits none and its dependencies move daily.
- **Images.** Both images and the solution install that build from `bpl.xz` with `mark.py`,
  which refuses any binary whose sha256 is not build.txt's and writes the image's private marker
  (`experiment/seeds.json`) over the zeros (the solution keeps the zeros). `smoke.sh` then proves
  the hardening on the installed binary in each image's builder stage: a value, a script, a module
  and standard input still work; reads outside the directory, by path, `..`, link, program file
  or module, and of `/proc/self/{maps,environ,mem}`, `/sys`, `/dev/null` and `/dev/stdin` with the
  working directory at `/`, are refused without printing the process's own files; no file is
  written, listed, copied, moved, removed or made; `•fetch` refuses and does not run a `curl`
  placed first on `PATH`; with `BASEDPL_COMPILE=always` no stage takes the compiled route;
  `--kernel` and `--costs` are usage errors; the worker refuses `case` and `check`. In the agent
  image the binary is `/opt/bpl/bpl`, `root:bpl` mode 2711 (execute-only, set-group-id, not
  dumpable), `/app` is root's and sticky and `/app/rebuild` root's and writable by all, and the
  agent is `dev`. The documentation is `/app/docs`; nothing else of upstream's is in the image.
- **Cases** (`scripts/make_cases.py`, `rewrite.py`, `programs.py`, `bpl_text.py`): 1,744 private
  cases from the private seed, by kind: `expr` 419, `script` 230, `apl` 119, `error` 219,
  `worker` 169, `display` 170, `stdin` 89, `module` 50, `program` 260, `cli` 19. See
  [Case mix](#case-mix). No visible set exists.
- **Verifier** (from the Goose task's round 5): separate image, root, records at build; see
  [Verification](#verification). The recorder runs each settled case twice and once perturbed
  (another binary path, 4 KB of environment padding, a stack 256 KB smaller, one CPU, one worker
  thread through `RAYON_NUM_THREADS=1`), keeps it on CPU time (0.25 s) and wall time (1 s), drops
  crashes (exit status other than 0, 1, 2, a signal, a panic or allocation-failure report) and
  answers that name the machine's memory (`memory limit of … MiB`), then caps any one answer at
  1.5% of the cases and the cases a no-interpreter dispatcher answers at 5%.
- **Instruction.** A requester who must keep 0.1.95's behaviour for years inside a product they
  license themselves asks for a clean-room implementation; the consumers of the exact output are
  CI golden files, a notebook service on `bpl --worker` that highlights error spans, and shell
  jobs on exit status. It states the hardened build's differences, the run conditions (user,
  directory, environment, pipes, limits, 2 s, 4 GB, 1 GB and 100,000 files written, the size cap
  on `/app/rebuild`) and what is out of scope, and gives no example, budget or grading.
- **Fixes found while checking.** System functions are excluded by their exact name (`•js` had
  matched `•json` and left out every record that parses JSON); the command-line cases take their
  share of an answer first, so no answer passes 1.5%; a recording run stopped by the disk or file
  limit (both measure the whole filesystem under `/tmp`) is run again and reported apart; the
  recorder's checks run in directories of their own, since two recorders on one machine share
  `/tmp/bpl-case`.
- **Checks.** 36 task checks (registered in the root `pyproject.toml`) and the 27 repository
  checks pass with Python 3.13; `check_repository.py` passes. A local recording of the 1,744
  private cases with upstream's own macOS release binary (not the hardened Linux build, so its
  answers are not the task's and stay in `experiment/`) kept 1,739: none unsteady, crashed,
  machine-dependent or changed when perturbed; the slowest run 17 ms; 5 dropped because their
  input holds the answer. Free answers 3.7% (command-line table plus one constant per kind), the
  largest answer 1.5%, printing nothing and exiting 1 1.5%, exiting 0 0.06%; cases from the APL
  ports 9.7%; cases kept in upstream's code form 248 (124 of them error cases, whose messages are
  the same for any implementation).
- Not built on Oddish and not run, on the owner's rule. Oddish preflight passes; the bundle is
  named in [Validation](#validation).

## Current implementation

| Part | State |
| --- | --- |
| Step `01-rebuild-interpreter` | Implemented: instruction, agent image with the execute-only interpreter and the documentation, separate verifier image, reference solution. |
| Further steps | Not designed. Candidates: the next upstream releases (0.1.96 onwards change semantics in patch releases); the worker's deadlines and interrupts. |
| Hardening | `common/hardening/`: the patch, `apply.sh`, the pinned `Cargo.lock`, `mark.py` (install and mark) and `smoke.sh` (proof at every install). |
| The original | `experiment/build/bpl` and `build.txt` from `scripts/build_original.py`, not in Git; packaging compresses it into both images and the solution. |
| Private inputs | `steps/01-rebuild-interpreter/tests/private/cases.json`, Git-ignored, from `scripts/make_cases.py` and `experiment/seeds.json`. Answers are recorded when the verifier image is built; `recording.json` beside them describes the recording and appears in `metrics.json`. |
| Oracle | The original, installed with the zero marker by `solve.sh`; then a non-scoring probe (`probe.c`) writes `/logs/agent/probe.txt`. |
| Ratings (`harbor check`) | Not run. |

## Design dimensions

### Novelty

MirrorCode (Epoch AI and METR) gives an execute-only program, its documentation and visible
tests. This task removes the tests: no example runs and no expected outputs, only the
interpreter and its manual (the "no examples" variant). The target is a language implementation
first published on 2026-09-16, after the training data of the models under test, with a notation
of its own. SWE-Marathon v1's interpreters and compilers target languages the models know; the
Goose task in this repository ships example runs; the markdown-linter rebuild was a smaller,
example-driven target that a cheap model nearly solved.

What "no examples" removes is narrower than it sounds (QA 14 F3, 17 F2). The documentation holds
about 3,900 single-line examples, and replaying them through the build gives the agent its own
ground truth for every documented main path within the first hour. What the agent must design
experiments for is the tail: messages, error kinds, display modes, the worker's encoding, the
structure of `∂`. That tail is where most of the reward lies, and QA 15 found self-tests built
from the docs miss the features of 58.5% of graded cases. "No examples" adds an estimated 10-20%
to the work, not a different order of it.

### Verifiability

Standard output and exit status are compared byte for byte with what the original printed when
the verifier image was built; every kept case printed the same four times (three runs with four
worker threads, then perturbed) without crashing, its answer shows no last bits of the maths
library, and, for a display case, its setting changes what it prints. Partial progress is the
share of cases that match.

### Realism

Clean-room reimplementations written from a manual and a binary are how compatible second
implementations are made (Wine, Samba, the PC BIOS). Keeping a language frozen at one release
for years, when upstream will not support it, is a common reason to own one, and a legal policy
that anything embedded that long is written clean-room with a provenance record is a common
reason not to fork. The exact bar has real consumers:
- golden files that CI keeps beside client data;
- saved notebooks whose worker replies must reproduce byte for byte;
- shell jobs that act on exit status.

The documentation is upstream's own. The cases come from upstream's reference suite and library,
and from programs of the kinds an analytics team writes: reports over tables, text tools on
standard input, validators that report what went wrong, and modules.

### Difficulty

**What a rebuild needs.**
- A reader for a new notation: runs grouped by spaces, strands, brackets, operator binding, sub-
  and superscripts.
- About 70 primitive functions and 25 operators, over a number tower with exact and fixed-width
  integers, rationals, complex numbers and three float widths.
- Dfns with predicates, guards and recursion; keyed axes and records; modules.
- Differentiation (`∂`). It is 5.7% of kept cases, down from 12.1% in upstream's suite, and the
  instruction names it.
- The display engine (precision, exponent forms, boxes, elision, widths, trees, notation) and `⍕`.
- Error messages with their kinds, positions and carets.
- The worker's JSON, with exact float encoding, and the command line.

Upstream's core is about 31,000 lines of Rust.

**Shape** (QA 16). The task is long because it is wide, not deep. The serial path (the reader
and evaluator, then `∂` or the worker) is about a tenth of the work, the leaves can be built in
any order, and nothing short of a real interpreter scores above the floor.

**Estimates.**
- QA 14, a strong human engineer: about 25-30 days for half the reward, 35-50 for 80%, 60-80
  for 95%.
- QA 15, an agent such as claude-code with DeepSeek Flash: about 11-16 h for half, so one 9.6 h
  session earns 0.15-0.45.
- QA 17 and 19, one session: a frontier model 0.35-0.60, DeepSeek Flash 0.20-0.40, GLM 5.3
  0.12-0.30.

None of these is measured yet.

**The tail.** The recorder drops answers that show the maths library's last bits: 16 in the local
recording, against 12 confirmed by QA 18. What remains of the float tail is fixed and visible but
obscure: `+/` grouping, and solver residues at ten digits. QA 15 bounds it at 2.4%.

**Floors without an implementation**, measured at every build (`baselines` in `recording.json`):
- the strongest dispatcher with no interpreter in it (`recorder.no_interpreter`) passes at most
  5%, enforced by dropping cases and by failing the build; 2.1% locally;
- any one answer is at most 1.5% of the cases;
- printing nothing and exiting 1 passes 0.5%.

### Initial feasibility

Solved by construction: the original passes every kept case. For an agent, unknown.

## Case mix

The private cases are drawn from what the language does, in these kinds (generated, and kept by
the local stand-in recording):

| Kind | Generated | Kept | What it asks | Source |
| --- | --- | --- | --- | --- |
| `expr` | 419 | 417 | `bpl -e CODE`: one expression's displayed value | upstream's own reference records (core, static, regex, the mathish files), rewritten |
| `script` | 167 | 167 | `bpl main.bpl`: multi-line programs, setups, settings, `⎕←` output | the same, multi-line |
| `apl` | 120 | 119 | as `expr`, from records ported from APL suites | APLcart, April, ngn, Dyalog, BQN ports; with their error records and sessions 10% of kept cases |
| `error` | 235 | 235 | errors caught by a guard that prints the message (`$e`, the message, kind and message, or line, column and message): 156; uncaught errors in the worker, whose reply carries kind, message, span and display: 57, every syntax error among them; a run that prints a computed value and ends in an error (exit 1): 22 | upstream's error records (a fifth from the APL ports) |
| `worker` | 189 | 174 | `bpl --worker` sessions in notebook form: records' code, definitions used by later requests, a function defined then called, a display setting then values, bindings of arrays used again, calls on encoded arguments; replies with exact values, displays and errors with spans | upstream's records |
| `display` | 230 | 144 | values and functions under `]display` (65), `]dissect` (29), `•prefs` box (13), trees (8), width (8), notation (6), limit and edges (6), prec (4), and `⍕` with format specs (6); kept only where the setting changes what is shown | upstream's records, and values built here |
| `stdin` | 89 | 88 | multi-line programs given with `bpl -`, lines piped into `bpl` with a failing line among them, programs reading `⎕` lines | upstream's records |
| `module` | 50 | 50 | a main program loading upstream's library modules (`lib/`) with `•load` | upstream's library records |
| `program` | 260 | 260 | 25 new programs with seeded data: reports, a word counter, a ledger, a grade book, validators with custom error kinds, CSV and JSON on standard input, number theory, matrices, exact rationals, complex roots, ciphers, a module of one's own, `bpl -` with arguments | `scripts/programs.py` |
| `cli` | 19 | 19 | the command line's own answers, one case per behaviour: help, version, removed modes, wrong arguments, missing and refused files, arguments, the worker's request errors, piped errors | `make_cases.cli_cases` |

**Rewrites** (private seed, `scripts/rewrite.py`).
- Every name the code assigns becomes an unused ordinary word, consistently. Keys, module names
  and names in code that runs text are left alone.
- Numbers in value positions take other values of the same form. Never rewritten: a size, count,
  position, axis, rank, iteration count or function code; 0 or 1; a number in a check such as
  `≡`, or next to `=` or `≠`.
- Words in prose strings take other words of the same length.

Each case gets up to three rewrites. The recorder keeps the first that ends as the unrewritten
code does and prints something else, and is not all zeros, empty or false where the original
answer is not. Comments are removed from upstream's code (some state results).

**What the documentation shows.** No record or program becomes a case, in any of its rewrites, if
the shipped documentation holds it, its skeleton (names, numbers and text abstracted), or its
skeleton as a whole block, a statement or a run of 2-6 consecutive statements. Packaging repeats
the check on the real files.

Records with `∂` are drawn at 55%, which puts differentiation at about 5.7% of cases.

**Left out:** randomness, the clock, files, the network, drawing, `•hash`, `•deflate`, `•mime`,
`⇄`, `•storage`, `•memory`, `•explain`, `•index`, `•host` facts other than the command line's,
`]help`, `]clear`, and the `threads`, `seed` and `fusion` settings.

## Workload

A run is one trial of 9.6 hours (one task row per experiment, no continuation tasks). The
instruction states no time budget.

## Verification

1. **Collection.** When the agent's turn ends, the root collect hook records egress and `dev`'s
   live processes, then kills those processes. It bounds `/app/rebuild`, packs it once as the
   copy will, and marks and records it (see the development log). Harbor then copies
   `/app/rebuild`, the declared artifact, into the verifier.
2. **Before any submitted code runs**, the verifier:
   - reserves `.reward.tmp` and `metrics.json`;
   - raises an evaluation error with less than 512 MB free;
   - checks the delivery against the hook's mark: nothing arrived, or fewer entries or bytes than
     marked, is an evaluation error;
   - copies the hook's record into `metrics.json`;
   - picks a uid inside the user namespace's map for submitted code and checks the unprivileged
     run: no_new_privs from the status file or `prctl`, ids, groups, capabilities with a missing
     `CapAmb` counted as 0, limits, and a set-id root copy of `id` that must report that uid. A
     failure is an evaluation error.

   It then seals `/app/rebuild`: root-owned, read-only, no set-id bits, at most 200,000 entries
   and 4 GB. It searches the delivery for the original's build marker, for the unhardened usage
   text, and for any of upstream's 12 published builds by sha256. A submission that cannot be
   sealed, or that holds any of these, gets reward 0 with a note.
3. **Before each case**, it kills that uid's processes and sweeps what it left in every
   world-writable directory and its System V IPC objects. Less than 512 MB free after that sweep
   is an evaluation error. It writes the case's files into a new `/tmp/bpl-run` with new empty
   `HOME` and `TMPDIR`. `/app/rebuild/bpl` runs there with:
   - no_new_privs, the case's arguments and standard input, no network;
   - the recorder's environment and limits;
   - 2 seconds and 4 GB of memory in use;
   - 1 GB and 100,000 files of its own on disk;
   - at most 1,000,000 bytes of output.

   A case stopped by the memory, disk or file limit runs once more.
4. **Scoring.** A case passes when the exit status and the bytes of standard output equal the
   recorded ones. A case that cannot be set up or started, runs too long, prints too much or
   passes a limit fails; none of that is an evaluation error.
5. **Deadline.** One deadline, 4,200 s from the start, covers sealing, scans, cleanup and cases;
   the cases left count as failed. At the end the verifier cleans up, writes the reward into its
   reserved file, renames it onto `reward.txt`, then writes `metrics.json`.

### Reward formula

```
reward = cases_passed / cases_kept
```

- Continuous, fixed denominator per image build (the private cases kept by the recording).
  No executable: reward 0.
- An evaluation error leaves no reward file. The causes:
  - not root, privileges that cannot be dropped, or a drop that does not hold;
  - private inputs unreadable, or the marker or the list of upstream's builds missing;
  - less than 512 MB free at the start or after a cleanup;
  - nothing arrived, or the copy was cut short;
  - the verifier ending before the real end.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verify.py` and `tests/verifier/runcases.py`; `tests/verifier/recording.py`
  describes the recording (cases kept by kind, drops by reason, settling, cases whose kept form
  is upstream's code with only its names changed, the APL share, run times, the baselines, the
  build) for `metrics.json`.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 2, 3, 5, 10, 14).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read, copy, trace or dump the interpreter from outside its process, or preload a library into it | File mode and group; the link | Goose QA passes 04 and 04b (the same layout) | `/opt/bpl/bpl` is `root:bpl` 2711: execute-only and set-group-id, so not dumpable; static, so no loader honours `LD_PRELOAD` or `LD_AUDIT` | Not a PIE: the binary's own code and data sit at fixed addresses (stack, heap and mappings still move); the sandbox's handling of a traced set-group-id exec is unmeasured | `/logs/agent/probe.txt` of the first oracle trial | 🟡 YELLOW / UNASSESSED |
| 2 | Read the interpreter from inside its process: a program reads `/proc/self/mem` or `maps`, runs a program, compiles code, or reads files outside its directory | Hardened build | Audit of every file, process and unsafe site in `src/`, `cli/`, `jit/`, `image/` (host.rs, files.rs, data.rs, the CLI, the worker, the editor) | Reads only under the start directory, checked on the opened file, never `/proc`, `/sys`, `/dev`; no writes; no `curl`; no JIT; no test-kit requests; no history file. `smoke.sh` proves each at every install | A memory-safety bug in the interpreter or its dependencies (rustymath has unsafe SIMD code) | The first build's smoke test, then probes from a trial as `dev` | 🟡 YELLOW / UNASSESSED |
| 3 | Run as root, or as a user who can read the program | `[agent] user` | Not tested on this task | `user = "dev"` | Depends on each harness | Short trial that prints `id` (the probe prints it) | 🟡 YELLOW / UNASSESSED |
| 4 | Deliver the original, a published build of it, or a wrapper that calls it | Verifier image; `/app` ownership; the marker; upstream's hashes | Goose QA passes 07 and 13; QA 04, 08, 20 | The verifier image holds no copy; `/app` is root's and sticky, so `dev` cannot replace `/app/rebuild`; a submission holding the images' marker, upstream's unhardened usage text, or a file with the sha256 of any of the 12 builds upstream publishes for 0.1.95 is refused (checked: the search, its chunking, the hashing by size, the images-only staging); a missing or malformed marker is an evaluation error | A copy transformed to hide both the marker and the hash | First trial as `dev`: `/app/rebuild` cannot be renamed | 🟢 GREEN / LOW |
| 5 | Fetch the public source, upstream's tests or a published build, including in the window after the turn when the platform reopens egress | Agent network; the collect hook; the refusals of row 4 | QA 04 and 08 (platform finding `PLATFORM_EGRESS_WINDOW.md`); decision 2026-11-19 (A, with conditions) | `network_mode = "no-network"` for the turn; the root collect hook kills every process of `dev` before anything is copied and records whether egress was open and what was running (`delivery_record`); published builds and the unhardened usage text are refused; no upstream source, test, notebook result or design note in the image | The window stays open until the platform keeps the agent-phase policy through collection; a transformed fetched build escapes the refusals; a harness with network access would defeat the task | Audit every trial (`delivery_record`: survivors, egress, ctimes after the turn) before its score is recorded | 🟡 YELLOW / UNASSESSED |
| 6 | Look up answers from what is shipped | Case generation | Checked on a stand-in upstream and on the real files at packaging | No example runs ship; no case holds a documented program or a near-copy (skeleton match: 311 core records left out); `make_cases.leaks` runs again at packaging | The documentation's examples teach behaviour by design (they show values in source form, not as displayed) | Keep | 🟢 GREEN / LOW |
| 7 | Read an answer out of the case's own input | Generation and recording | Checked | Comments removed from upstream's code (some state results); the recorder drops a case whose input holds its whole answer (5 in the local recording) | Short answers a program spells out literally | Read `dropped` in `recording.json` | 🟢 GREEN / LOW |
| 8 | Recall upstream's published expectations | Rewrites | Local recording: 248 of 1,739 kept cases in upstream's code form | Names, value literals and prose words rewritten under the private seed; the recorder prefers rewrites that change the answer; `recording.json` counts the cases still in upstream's form (`kept_as_upstream_code`, mostly error records, whose messages are the same for any implementation) | BasedPL was published 2026-09-16; models trained later may know it, and its reference files | Read `kept_as_upstream_code`; re-check for models trained after 2026-09 | 🟢 GREEN / LOW |
| 9 | Tamper with the reward files, or suppress them by forcing an evaluation error | Separate verifier container | Goose QA passes 07, 07b, 10, 10b, round 6 (the same verifier) | No reward exists until the real end (`.reward.tmp` renamed onto `reward.txt`); bounded, link-refusing reads; one deadline; capped submissions; `rm -rf` sweeps; every per-case exception a failed case; host disk shortages are errors only after the sweep has taken back everything the uid held (checked) | Kernel keyrings survive between cases; they carry no answer | Keep | 🟢 GREEN / LOW |
| 10 | Infer an evaluation from the files and text | Instruction and image | Checked: no grading, hidden, budget or session wording; no examples or runner shipped | Neutral requester text | An agent can still guess that more programs exist | Read the first trajectories | 🟡 YELLOW / UNASSESSED |
| 11 | Run as root in the verifier through a set-id or capable file | Privilege drop and sealing | Goose QA pass 10 F6 | Sealed root-owned without set-id bits; `setpriv --no-new-privs`; the drop is checked by status or `prctl` and a set-id `id`, or nothing is graded (checked) | A kernel that ignores no_new_privs; the probe then refuses to grade | First baseline's verifier log | 🟢 GREEN / LOW |
| 12 | Pass cases with no interpreter: the command line's answers, echoed literals, constant answers per visible shape | Case mix and selection | QA 02, 05, 13, 17 measured 5.5-7.3% on the first cases; local recording now: 2.1% (recorder), 1.85% (the dispatcher run as a program) | Leads are computed values; uncaught errors mostly graded through the worker's reply with message and span; handlers always print the message; any one answer capped at 1.5%; `select` holds the strongest dispatcher (`recorder.no_interpreter`) to 5% and the recorder fails the build above it | Display of simple literals is legitimate early work | Read `baselines.no_interpreter_dispatcher` in the first baseline's `metrics.json` | 🟢 GREEN / LOW |
| 13 | A crash of the original graded as an answer | Recording | Checked with a stand-in | Signals, exit statuses other than 0, 1 and 2, panics and allocation failures are dropped; more than 2% fail the build | None found | Read `dropped_crashed` | 🟢 GREEN / LOW |
| 14 | Answers that depend on the machine or on the maths library's last bits: thread counts, hash order, the memory limit, CPU features, approximation bits | Recording | Local recording: no case unsteady or perturbed; 16 last-bit answers dropped (QA 18 confirmed 12) | Three runs pinned to four worker threads and a perturbed one (one CPU, one worker thread); memory-limit text dropped from either stream; last-bit answers dropped; rustymath chooses SIMD paths at compile time (`x86-64-v3`); `expected_sha256` lets two builds be compared | A host without AVX2 cannot run the original (the smoke test then fails the build, and an oracle row below 1.0 with `host.avx2` false is infrastructure); the x86-64 build's bits are first seen at its own recording | Two oracle trials must each score 1.0 with the same `kept_ids_sha256` and `expected_sha256` before any model trial | 🟡 YELLOW / UNASSESSED |
| 15 | A busy host fails a graded run spuriously | Disk and file limits | QA 10: a `sleep 10` submission was stopped for a file limit by the whole-filesystem figures | The limits count only the run's own files (its uid's under the writable directories, and deleted files it holds open), and only when the free figures fall past a limit; a case stopped by a limit runs once more; host shortages after a sweep are evaluation errors | None found | Read `disk_limits`, `file_limits` and `limit_retries` in the first trials' `metrics.json` | 🟢 GREEN / LOW |
| 16 | Make Harbor's copy drop an honest delivery (a running build, links that leave the directory, FIFOs, a sparse file, a full disk) so that it scores a valid 0, or make the copy fail at will | The collect hook and the mark | QA 07 F2-F3 (ported from the back-office task, rounds 6-7) | The hook kills `dev`'s processes, gives back reserved room and inodes, materialises or removes links, removes special files, bounds entries, bytes and path length, packs once within 100 s, and marks the delivery; the verifier grades what arrived, and treats nothing arriving or a short copy as an evaluation error (checked end to end with a real tar round trip and the `data` filter) | A platform copy that fails after the hook's trial pack succeeded: an evaluation error, then a re-run | Read `delivery_record` and the notes in the first trials | 🟢 GREEN / LOW |
| 17 | Read the build's own file through the hardened read path from a start directory whose rule lets it through (`/`, `/opt`, `/opt/bpl`) | File mode; the path rule | QA 04 F4, QA 12 F2 | The 2711 mode refuses the read for `dev`; the agent image's final stage proves it as `dev` (with the whole smoke test on the set-group-id build) and `solve.sh` records it in the trial | A kernel that let a non-dumpable set-group-id process read its own executable | `/logs/agent/reads.txt` of the first oracle trial | 🟢 GREEN / LOW |

Licence: the upstream is Apache-2.0. Its `LICENSE` is shipped with the documentation in
`/app/docs` and with the reference solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (43 tests) with `ci_checks` (27), Python 3.13, and `check_repository.py` | round 2 (`faf3a78` and the README after it) | pass |
| Local build of the hardened original | `scripts/build_original.py`, 2026-11-19 | builds (one warning); static, not PIE; marker once; no local path |
| `apply.sh` | a fresh export of v0.1.95 | applies once, refuses a second time; result identical to the patched tree that was built |
| `smoke.sh` | upstream's v0.1.95 macOS release binary | fails at the first hardening check, as it must; never yet run on the hardened Linux binary (no Linux here) |
| Upstream's published builds | `scripts/upstream_builds.py`, 2026-11-19 | 21 executables in 3 release assets and 9 wheels, 12 distinct hashes; upstream's Linux build holds the unhardened usage text twice, the hardened build and the docs never |
| Local recording (the private cases, upstream's macOS release binary) | cases `01f5d1d2`, `experiment/local-recording-6` | 1,673 of 1,778 kept (86 display settings that change nothing, 16 last bits, 3 quoted); none unsteady, crashed, machine-dependent or perturbed; no-interpreter dispatcher 2.1%, largest answer 0.5%, nothing with exit 1 0.5%; `∂` 5.7% |
| Local grading from the packaged bundle (`7462d71fe5a7`), through the collect hook's measuring script and a tar round trip with the `data` filter | stand-in reference behind a wrapper; no-op; the dispatcher as a program | 1.0 (1,673/1,673, 29.5 s); 0.0; 0.0185 (31/1,673: cli 19, expr 7, error 5) |
| Packaging | `scripts/package_step.py`, twice into separate directories | `7462d71fe5a7`, 248 files, 33,253,911 bytes, the same hash both times |
| Oddish preflight | bundle `7462d71fe5a7`, no-Archil CLI, locally | pass |
| Oddish baselines, QA, `harbor check` | none | not run |

## Build and deliver

```bash
git clone https://github.com/AnswerDotAI/basedpl <checkout>     # any branch; the commit is read by hash
python scripts/build_original.py --checkout <checkout>         # once: experiment/build/bpl, build.txt
python scripts/make_cases.py <checkout>                        # private cases from experiment/seeds.json
BASEDPL_CHECKOUT=<checkout> python scripts/package_step.py     # add --flat for a bundle without steps
python scripts/upstream_builds.py                              # only when upstream's 0.1.95 files change: their hashes
```

The case seed and the build marker come from `experiment/seeds.json`, which `scripts/seeds.py`
makes once at random and which is never committed: anyone with the generator, upstream's
checkout and the seed could regenerate the hidden cases. The build needs Rust 1.100.0 with the
`x86_64-unknown-linux-musl` target, zig and `cargo-zigbuild`; packaging refuses a binary whose
sha256 is not build.txt's.

## Remaining work

- Baselines of bundle `7462d71fe5a7` under the task's one experiment, on the owner's word. The
  two oracle trials on different workers are a hard gate: each must score exactly 1.0, with the
  same `kept_ids_sha256` and `expected_sha256`. A failed id goes on a deny-list and the cases are
  recorded again. Then the no-op, which must score exactly 0. These are the first run of the
  hardened binary on Linux: its smoke test as root and as `dev` in the agent image, in the
  verifier image and in the solution. They are also the first Linux recording. Read `recording`
  in the reference run's `metrics.json`: drops by reason, settling, `kept_as_upstream_code`, the
  baselines, the build. Read `/logs/agent/probe.txt`, `reads.txt` and `smoke.txt`, and
  `delivery_record`.
- Audit every trial before its score is recorded, per the egress decision: survivors and egress
  in `delivery_record`, and deliverable ctimes later than the agent's turn.
- A static PIE: build with a linker that produces `-static-pie` for musl (rust-lld with Rust's
  self-contained musl, or a Linux builder), then rebuild every image from that binary.
- `harbor check` and ratings.
- Shelf life (QA 20 item 4): the cases suit models trained before 2026-09-16, when BasedPL was
  first published. `core.bpl` supplies most of them, and the generator goes public with this
  branch. Check recall before reading a score from any model trained later, and plan a re-seed
  with new templates when that happens.
- Notices (QA 20 item 6): only upstream's `LICENSE` ships beside the redistributed binary. Before
  bundles leave Abundant, generate third-party notices for the 281 statically linked crates
  (`cargo about`) into `/app/docs` and the solution.
