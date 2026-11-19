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
installed unchanged in both images and in the reference solution. One step is implemented. See
[Remaining work](#remaining-work).

## Development log

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
interpreter and its manual, so the agent must design its own experiments to learn each behaviour
(the "no examples" variant). The target is a language implementation first published on
2026-09-16, after the training data of the models under test, with a notation of its own.
SWE-Marathon v1's interpreters and compilers target languages the models know; the Goose task in
this repository ships example runs; the markdown-linter rebuild was a smaller, example-driven
target that a cheap model nearly solved.

### Verifiability

Standard output and exit status are compared byte for byte with what the original printed when
the verifier image was built; every kept case printed the same three times (twice, then
perturbed) without crashing. Partial progress is the share of cases that match.

### Realism

Clean-room reimplementations written from a manual and a binary are how compatible second
implementations are made (Wine, Samba, the PC BIOS), and keeping a language frozen at one
release, inside a product, is a common reason to own one. The exact bar has real consumers: golden
files, a notebook front end that parses the worker's JSON and highlights error spans, shell jobs
that act on exit status. The documentation is upstream's own; the cases come from upstream's
reference suite and library, and from programs of the kinds an analytics team writes (reports
over tables, text tools on standard input, validators that report what went wrong, modules).

### Difficulty

A rebuild needs a reader for a new notation (runs grouped by spaces, strands, brackets, operator
binding, sub- and superscripts), around 70 primitive functions and 25 operators over a number tower
with exact and fixed-width integers, rationals, complex numbers and three float widths, dfns with
predicates, guards and recursion, keyed axes and records, modules, the display engine (precision,
exponent forms, boxes, elision, widths, trees, notation), `⍕`, error messages with their kinds,
positions and carets, the worker's JSON (exact float encoding), and the command line. Upstream's
core is about 31,000 lines of Rust. With no examples, the agent must also decide what to probe;
the documentation's own examples show values in source form, not as `bpl` displays them. Not yet
measured with a model; QA passes give estimates.

Floors without an implementation, by design: a table of the command line's answers plus one
constant answer per kind passes at most 5% (enforced by the recorder); any one answer is at most
1.5% of the cases. `recording.json` measures them at each build (`baselines`).

### Initial feasibility

Solved by construction: the original passes every kept case. For an agent, unknown.

## Case mix

The private cases are drawn from what the language does, in these kinds (counts as generated;
the recording keeps most):

| Kind | Count | What it asks | Source |
| --- | --- | --- | --- |
| `expr` | 419 | `bpl -e CODE`: one expression's displayed value | upstream's own reference records (core, static, regex, the mathish files), rewritten |
| `script` | 230 | `bpl main.bpl`: multi-line programs, setups, settings, `⎕←` output | the same, multi-line |
| `apl` | 119 | as `expr`, from records ported from APL suites | APLcart, April, ngn, Dyalog, BQN ports; with their error records and session use about 10% of all cases |
| `error` | 219 | errors caught by a guard and printed (`$e`, its kind and message, its line and column), or a run ending in an error after some output (exit 1) | upstream's error records (a fifth from the APL ports) |
| `worker` | 169 | `bpl --worker` sessions: code, setups with echo off, bindings of arrays, calls on encoded arguments; replies with exact values, displays and errors with spans | upstream's records |
| `display` | 170 | values and functions under `•prefs` (box, prec, width, limit and edges, trees, notation), `]display`, `]dissect`, `⍕` with format specs | upstream's records, and values built here |
| `stdin` | 89 | programs reading `⎕` lines, programs given with `bpl -`, lines piped into `bpl` | upstream's records |
| `module` | 50 | a main program loading upstream's library modules (`lib/`) with `•load` | upstream's library records |
| `program` | 260 | 25 new programs with seeded data: reports, a word counter, a ledger, a grade book, validators with custom error kinds, CSV and JSON on standard input, number theory, matrices, exact rationals, complex roots, ciphers, a module of one's own, `bpl -` with arguments | `scripts/programs.py` |
| `cli` | 19 | the command line's own answers, one case per behaviour: help, version, removed modes, wrong arguments, missing and refused files, arguments, the worker's request errors, piped errors | `make_cases.cli_cases` |

Rewrites (private seed, `scripts/rewrite.py`): every name the code assigns becomes an unused
ordinary word, consistently (never a key, a module name, or a name in code that runs text);
numbers in value positions take other values of the same form (never a size, count, position,
axis, rank, iteration count or function code, never 0 or 1, never in a check such as `≡`); words
in prose strings take other words of the same length. Up to three rewrites per case; the
recorder keeps the first that ends as the unrewritten code does and prints something else.
Comments are removed from upstream's code (some state results). No record or program that the
shipped documentation holds, or whose skeleton (names, numbers and text abstracted) it holds,
becomes a case (311 of core's records were near-copies); packaging repeats the check on the real
files. Left out: randomness, the clock, files, the network, drawing, `•hash`, `•deflate`,
`•mime`, `⇄`, `•storage`, `•memory`, `•explain`, `•index`, `•host` facts other than the
command line's, `]help`, `]clear`, and the `threads`, `seed` and `fusion` settings.

## Workload

A run is one trial of 9.6 hours (one task row per experiment, no continuation tasks). The
instruction states no time budget.

## Verification

1. `/app/rebuild` arrives as the declared artifact.
2. The verifier reserves `reward.txt` (0) and `metrics.json` before anything runs, picks a uid
   inside the user namespace's map for submitted code and checks the unprivileged run first
   (no_new_privs from the status file or `prctl`, ids, groups, capabilities with a missing
   `CapAmb` counted as 0, limits, and a set-id root copy of `id` that must report that uid); a
   failure is an evaluation error. It seals `/app/rebuild` (root-owned, read-only, no set-id
   bits, at most 200,000 entries and 4 GB) and searches it for the original's build marker: a
   submission that cannot be sealed or holds the marker gets reward 0 with a note.
3. Before each case it kills that uid's processes, sweeps what it left in every world-writable
   directory and its System V IPC objects, and writes the case's files into a new
   `/tmp/bpl-case` with new empty `HOME` and `TMPDIR`. `/app/rebuild/bpl` runs there with
   no_new_privs, the case's arguments and standard input, no network, the recorder's environment
   and limits, 2 seconds, 4 GB of memory in use, 1 GB and 100,000 files added to the disk, and at
   most 1,000,000 bytes of output.
4. A case passes when the exit status and the bytes of standard output equal the recorded ones.
   A case that cannot be set up or started, runs too long, prints too much or passes a limit
   fails; none of that is an evaluation error.
5. One deadline (3,300 s from the start) covers sealing, scans, cleanup and cases; the cases
   left count as failed. At the end the verifier cleans up, writes `reward.txt` in place, then
   `metrics.json`.

### Reward formula

```
reward = cases_passed / cases_kept
```

- Continuous, fixed denominator per image build (the private cases kept by the recording).
  No executable: reward 0.
- An evaluation error (not root, privileges cannot be dropped or the drop does not hold, private
  inputs unreadable) leaves no reward file.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verify.py` and `tests/verifier/runcases.py`; `tests/verifier/recording.py`
  describes the recording (cases kept by kind, drops by reason, settling, cases whose kept form
  is upstream's code with only its names changed, the APL share, run times, the baselines, the
  build) for `metrics.json`.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 2, 3, 5, 10, 12, 14, 15).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read, copy, trace or dump the interpreter from outside its process, or preload a library into it | File mode and group; the link | Goose QA passes 04 and 04b (the same layout) | `/opt/bpl/bpl` is `root:bpl` 2711: execute-only and set-group-id, so not dumpable; static, so no loader honours `LD_PRELOAD` or `LD_AUDIT` | Not a PIE: the binary's own code and data sit at fixed addresses (stack, heap and mappings still move); the sandbox's handling of a traced set-group-id exec is unmeasured | `/logs/agent/probe.txt` of the first oracle trial | 🟡 YELLOW / UNASSESSED |
| 2 | Read the interpreter from inside its process: a program reads `/proc/self/mem` or `maps`, runs a program, compiles code, or reads files outside its directory | Hardened build | Audit of every file, process and unsafe site in `src/`, `cli/`, `jit/`, `image/` (host.rs, files.rs, data.rs, the CLI, the worker, the editor) | Reads only under the start directory, checked on the opened file, never `/proc`, `/sys`, `/dev`; no writes; no `curl`; no JIT; no test-kit requests; no history file. `smoke.sh` proves each at every install | A memory-safety bug in the interpreter or its dependencies (rustymath has unsafe SIMD code) | The first build's smoke test, then probes from a trial as `dev` | 🟡 YELLOW / UNASSESSED |
| 3 | Run as root, or as a user who can read the program | `[agent] user` | Not tested on this task | `user = "dev"` | Depends on each harness | Short trial that prints `id` (the probe prints it) | 🟡 YELLOW / UNASSESSED |
| 4 | Deliver the original, or a wrapper that calls it | Verifier image; `/app` ownership; the marker | Goose QA passes 07 and 13 | The verifier image holds no copy; `/app` is root's and sticky, so `dev` cannot replace `/app/rebuild`; a submission holding the images' marker is refused (checked: the search, its chunking, the images-only staging) | A copy the agent cannot read anyway, transformed to hide the marker | First trial as `dev`: `/app/rebuild` cannot be renamed | 🟢 GREEN / LOW |
| 5 | Fetch the public source or upstream's tests | Agent network | Not probed on this task | `network_mode = "no-network"`; no upstream source, test, notebook result or design note in the image | The repository and its reference files are public; a harness with network access would defeat the task | Probe from a trial | 🟡 YELLOW / UNASSESSED |
| 6 | Look up answers from what is shipped | Case generation | Checked on a stand-in upstream and on the real files at packaging | No example runs ship; no case holds a documented program or a near-copy (skeleton match: 311 core records left out); `make_cases.leaks` runs again at packaging | The documentation's examples teach behaviour by design (they show values in source form, not as displayed) | Keep | 🟢 GREEN / LOW |
| 7 | Read an answer out of the case's own input | Generation and recording | Checked | Comments removed from upstream's code (some state results); the recorder drops a case whose input holds its whole answer (5 in the local recording) | Short answers a program spells out literally | Read `dropped` in `recording.json` | 🟢 GREEN / LOW |
| 8 | Recall upstream's published expectations | Rewrites | Local recording: 248 of 1,739 kept cases in upstream's code form | Names, value literals and prose words rewritten under the private seed; the recorder prefers rewrites that change the answer; `recording.json` counts the cases still in upstream's form (`kept_as_upstream_code`, mostly error records, whose messages are the same for any implementation) | BasedPL was published 2026-09-16; models trained later may know it, and its reference files | Read `kept_as_upstream_code`; re-check for models trained after 2026-09 | 🟢 GREEN / LOW |
| 9 | Tamper with the reward files, or suppress them by forcing an evaluation error | Separate verifier container | Goose QA passes 07, 07b, 10, 10b (the same verifier) | Reward reserved first and written in place; bounded, link-refusing reads; one deadline; capped submissions; `rm -rf` sweeps; every per-case exception a failed case (checked) | Kernel keyrings survive between cases; they carry no answer | Keep | 🟢 GREEN / LOW |
| 10 | Infer an evaluation from the files and text | Instruction and image | Checked: no grading, hidden, budget or session wording; no examples or runner shipped | Neutral requester text | An agent can still guess that more programs exist | Read the first trajectories | 🟡 YELLOW / UNASSESSED |
| 11 | Run as root in the verifier through a set-id or capable file | Privilege drop and sealing | Goose QA pass 10 F6 | Sealed root-owned without set-id bits; `setpriv --no-new-privs`; the drop is checked by status or `prctl` and a set-id `id`, or nothing is graded (checked) | A kernel that ignores no_new_privs; the probe then refuses to grade | First baseline's verifier log | 🟢 GREEN / LOW |
| 12 | Pass cases with no interpreter: the command line's answers, constant answers per kind | Case mix and selection | Local recording: 3.7% | Any one answer capped at 1.5%; the recorder drops cases until a table plus constants passes at most 5%; `recording.json` measures four baselines | Display of simple literals is legitimate early work | Read `baselines` in the first baseline's `metrics.json` | 🟡 YELLOW / UNASSESSED |
| 13 | A crash of the original graded as an answer | Recording | Checked with a stand-in | Signals, exit statuses other than 0, 1 and 2, panics and allocation failures are dropped; more than 2% fail the build | None found | Read `dropped_crashed` | 🟢 GREEN / LOW |
| 14 | Answers that depend on the machine: thread counts, hash order, the memory limit, CPU features | Recording | Local recording: no case unsteady or perturbed | Two runs and a perturbed one (one CPU, one worker thread); answers naming the machine's memory dropped; rustymath chooses SIMD paths at compile time (`x86-64-v3`), not at run time | A host without AVX2 cannot run the original at all (the smoke test then fails the build); last-digit float differences between thread counts the perturbed run does not reach | Read `dropped_perturbed` and `dropped_unsteady` | 🟡 YELLOW / UNASSESSED |
| 15 | A busy host fails a graded run spuriously | Disk and file limits | macOS showed spurious file-limit stops (APFS estimates inodes from free space) | Limits from the Goose verifier; at recording a stopped run is retried and reported apart | On Linux the limits measure the whole filesystem under `/tmp`, which other containers may write to | Read `disk_limits` in the first trials' `metrics.json` | 🟡 YELLOW |

Licence: the upstream is Apache-2.0. Its `LICENSE` is shipped with the documentation in
`/app/docs` and with the reference solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (36 tests) with `ci_checks` (27), Python 3.13, and `check_repository.py` | working tree, 2026-11-19 | pass |
| Local build of the hardened original | `scripts/build_original.py`, 2026-11-19 | builds (one warning); static, not PIE; marker once; no local path |
| `apply.sh` | a fresh export of v0.1.95 | applies once, refuses a second time; result identical to the patched tree that was built |
| `smoke.sh` | upstream's v0.1.95 macOS release binary | fails at the first hardening check, as it must; never yet run on the hardened Linux binary (no Linux here) |
| Local recording (the private cases, upstream's macOS release binary) | cases `a26424a7` | 1,739 of 1,744 kept, none unsteady, crashed, machine-dependent or perturbed; floors 3.7% (table and constants), 1.5% (largest answer), 1.5% (nothing, exit 1) |
| Oddish preflight | see [Build and deliver](#build-and-deliver) | pass |
| Oddish baselines, QA, `harbor check` | none | not run |

## Build and deliver

```bash
git clone https://github.com/AnswerDotAI/basedpl <checkout>     # any branch; the commit is read by hash
python scripts/build_original.py --checkout <checkout>         # once: experiment/build/bpl, build.txt
python scripts/make_cases.py <checkout>                        # private cases from experiment/seeds.json
BASEDPL_CHECKOUT=<checkout> python scripts/package_step.py     # add --flat for a bundle without steps
```

The case seed and the build marker come from `experiment/seeds.json`, which `scripts/seeds.py`
makes once at random and which is never committed: anyone with the generator, upstream's
checkout and the seed could regenerate the hidden cases. The build needs Rust 1.100.0 with the
`x86_64-unknown-linux-musl` target, zig and `cargo-zigbuild`; packaging refuses a binary whose
sha256 is not build.txt's.

## Remaining work

- The 20 QA passes, then baselines of the current bundle under the task's one experiment: the
  first run of the hardened binary on Linux (its smoke test in both images and in the solution),
  the first recording (read `recording` in the reference run's `metrics.json`: drops by reason,
  settling, `kept_as_upstream_code`, the APL share, the baselines, the build), and the first run
  of the privilege checks as root. Read `/logs/agent/probe.txt` and `smoke.txt`.
- A static PIE: build with a linker that produces `-static-pie` for musl (rust-lld with Rust's
  self-contained musl, or a Linux builder), then rebuild every image from that binary.
- Two oracle trials on different workers should each score exactly 1.0; any failed id goes on a
  deny-list and the cases are recorded again.
- `harbor check` and ratings.
