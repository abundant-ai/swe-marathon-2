# Goose compiler rebuild

Author notes. Nothing in this file is shipped to the agent or to either image.

The agent gets an execute-only copy of `goose`, the compiler of the Goose programming
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
  instruction tells the agent where it is.
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
  failed, never as an evaluation error. Standard output is read in pieces up to 4 MB (since 1,000,000 bytes; no output
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
    hardened build removes, so no case reads them. (This entry said 26 run cases pass arguments
    after `--`; none does, and none could be seen without `os`.)
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

### 2026-11-19 (round 2, continued: QA passes 02, 04b, 05, 06b, 08, 09, 18)

One regeneration (same seed) carries every case change below. Not built: no local Goose build.

- **No C from the original (pass 08).** The patch also removes `goose build` (it leaves the
  program's and the runtime's C on disk) and `-o`, `--standalone`, `--header`, `--emit-runtime`
  and `--gen-runtime-header`. `smoke.sh` proves each refusal and that no `.c` file appeared; the
  instruction lists them with the other differences from the documentation. No graded case used
  them but the command-line case `run main.goose -o out.c`, which is gone.
- **The agent's account is `dev` (pass 09).** It was `candidate`. Dockerfile, `task.toml` and
  the checks, which also refuse the word in anything the agent sees.
- **The original read from outside (pass 04b).** The shipped `goose` was dynamically linked: where
  a sandbox runs a traced or plain exec without secure execution (gVisor is not proven either way),
  the loader honours `LD_PRELOAD` and `LD_AUDIT` and an agent's library runs inside the compiler.
  `common/hardening/build.sh`, now the one build of both images and the solution, links the
  compiler static and stripped: no loader, so no preloading. The JIT does not need `dlsym` for it:
  the compiler hands TinyCC every host symbol itself (`src/jit_runtime.c`, under `-nostdlib`), and
  every standard-library extern binds to that table or to the runtime's own static C (checked
  against the sources: all 53). Untried here: a static glibc link of the compiler itself. Where it
  does not build or does not pass `smoke.sh`, `build.sh` builds the stripped dynamic link instead,
  and `recording.json` says which (`link`). `solve.sh` ends with a non-scoring probe (`probe.c`,
  built with `gcc`, run as `dev`) that writes the kernel, whether it is gVisor's, the compiler's
  ids and `AT_SECURE` for a plain and a traced exec, whether an `LD_PRELOAD` constructor ran, and
  whether `PTRACE_PEEKDATA` and `/proc/<pid>/mem` reads succeeded, to `/logs/agent/probe.txt`.
- **`embed_file` (pass 04b).** It read any path at compile time in the compiler's process,
  `/proc/self/maps` included. It now reads only a file under the directory of the file that embeds
  it, checked on the file actually opened (its `/proc/self/fd` entry), so no absolute path, `..`,
  link or swapped link leads out. `embed_shader` and shader files are refused (the shader compiler
  would read them in-process; `gfx` is out of scope). `smoke.sh` proves all four.
- **Nothing carried between cases (pass 06b).** Every run, recorded or graded, has new empty
  `HOME` and `TMPDIR` directories besides its new workspace. Before and after every case the
  verifier kills the sandbox user's processes, removes what it left in every world-writable
  directory (found when the evaluation starts) and removes its System V IPC objects. A check runs
  a submission that hides files in all of these and looks for them later.
- **no_new_privs on gVisor (coordinator).** The status file may lack `NoNewPrivs`; a process started
  as submitted code is now prints its status and then `prctl(PR_GET_NO_NEW_PRIVS)`, and either
  source suffices. Neither still fails closed.
- **Cases built for the recorder to vet (passes 02, 05, 06b, 18).** The generator emits, and the
  recorder (`runcases.settle`, `select`) decides at build time, where the original is:
  - run cases carry up to three edits of literals and printed words, never in an assert, a match,
    an array size, a repeat count, an index or a shift, with the unedited program last; the
    recorder keeps the first edit that ends as the unedited program does and prints something
    else, else the unedited program, and drops the case where a program upstream expects to
    complete does not. A check case on a program broken on purpose carries three breaking edits;
    the first the original reports something for is kept;
  - a recording run that ends by a signal, or with an internal-error, JIT, sanitizer or C++ abort
    report on stderr, is a crash: the case is dropped, and more than 2% of them fails the build;
  - then, by id: cases whose comments quote any case's answer (every diagnostic message, every
    output line of 12 characters or more), `format -` input already formatted, any one (stdout,
    exit code) answer beyond 1.2% of cases (the command line aside), check cases answering `[]`
    beyond 5% of checks, and while more than 4.5% of cases can be answered with no compiler, one
    such case at a time;
  - `recording.json` reports each drop by reason, how cases were settled, the run answers equal to
    upstream's expected file, the error cases whose messages are all (or some) upstream's text
    verbatim, and four baselines: print nothing and exit 1, print nothing and exit 0, the
    command-line table plus one constant answer per kind of case, and that plus a perfect formatter.
- **Inputs people write (passes 02, 09).**
  - Names: ordinary words, alone or two together, in the original's case (was `amber42`); never a
    keyword; first the names an error or warning message mentions, so that more messages change;
    in comments too.
  - Format layouts: a style of the file's own (two-space indentation, tabs in about 4% of files,
    operators written tight) or one to three slips (a line or block indented off, an operator or a
    comma without its space, spaces inside brackets, a trailing comma left off, a column out of
    line, a long line wrapped, trailing spaces, an extra blank line). No more random gaps, tabs or
    nested block comments.
  - Comments: the program's own, less those upstream's runner reads (`// error:`, `// warning:`,
    `bce:`, run markers) and those quoting an answer upstream publishes for any program; otherwise
    documentation lines, notes before statements (never before a closing bracket), trailing notes,
    and in one file in ten an argument label (`f(/*count=*/3)`).
  - `format --check` workspaces have files the recorder formats with the original first, next to
    slipped ones: all, some or none formatted.
- **Larger programs, every library module (passes 02, 18).** LangArena's benchmarks
  (`bench/kostya`) join the pools: for each group of the suite's dispatch blocks, a main that runs
  them once and prints the checksums, the harness replaced by a fixed configuration with no clock,
  and the helper's C externs by `std`'s `format_flt`. 27 programs of 137 to 931 lines over csv,
  base64, json, regex, dictionaries and slice pools; untried, so a glue error shows as cases
  dropped for not completing. Programs are drawn by the square root of their size. The split is by
  family (a test's name less its last word, a benchmark's first word, LangArena programs sharing a
  module), adjusted so that three warning programs are visible and every library module has
  programs on both sides.
- **Fewer free answers (pass 05).** Format is 6.5% of cases (74 standard input, 9 `--check`
  workspaces), rejected programs run with `--diagnostics json` but for 4 of 124, and the command
  line has 19 cases, none an argument list the examples show or an alias of one.
- **Instruction (pass 09).** The reason for the sandboxed build is now the product: snippets people
  send, run in a playground, in CI and in an editor plugin. It adds the `embed_file` and
  `embed_shader` limits, the new run conditions and why a run has 2 seconds.
- **Counts (private 1,500; visible 300).** run 493, library 82, modules 130 (81 LangArena), check
  569 (398 on error tests and warning programs, 171 broken on purpose), rejected 124, format 83,
  command line 19; visible: run 88, library 24, modules 29, check 120, rejected 14, format 17,
  command line 8. Programs behind the private cases: median 41 lines (was 18), 90th percentile
  176, largest 931; 442 cases on programs of 80 lines or more. Private library use: base64 4,
  binary 19, csv 5, dictionary 40, exception 35, json 12, mat 20, quat 13, regex 4 (csv and
  base64 were 0). Runner markers in inputs 0, inputs starting with a blank line 0, block
  comments 3 (labels), tab-indented lines 95 (whole tab-indented files); names ending in a number
  are upstream's own (`step1`). Cases with no change at all: 8. Private cases `ed4aa112`, visible
  `86b96475` (sha1 of the bundle's copies).
- Preflight passes on bundle `a296bbd1ed2d`.

### 2026-11-19 (round 3: QA passes 03, 07, 10b, 11, 12, 13)

One regeneration, with a new private seed. Not built: no local Goose build.

- **The original as the artifact (07, 13; must-fix).** `dev` owned `/app`, so `ln -s /opt/goose
  /app/rebuild` handed the root-run collector the original and its TinyCC files, which then scored
  about 1.0. `/app` is now root's and sticky and `/app/rebuild` root's and writable by all (as in
  the backoffice task), so the entry cannot be replaced. Defence in depth: the patch compiles a
  build marker into the original (`GOOSE-BUILD-MARKER-` and 32 hex digits, random, from
  `experiment/seeds.json`, staged by packaging into both images' builds and never the
  solution's, whose marker is zeros); the verifier searches the sealed submission for it and
  gives reward 0 with a note. A submission that cannot be sealed also gets reward 0, not an
  evaluation error.
- **Forced evaluation errors (07, 10b; must-fix, demonstrated).** About 1,000 nested directories
  made `shutil.rmtree` raise `RecursionError` on Python 3.12, which only `except OSError`
  surrounded. Every removal is now `rm -rf` (no depth limit, links not followed), every case
  catches every exception (a setup error, never an evaluation error), `kill_user` reads owners with
  `stat` and states as bytes (a process name need not be UTF-8), orphans are reaped (the verifier
  is a subreaper), `ipcrm` is guarded, and `reward.txt` is written before `metrics.json`.
- **The seed is private (coordinator).** The repository is public and the README printed the seed,
  so anyone could regenerate the hidden programs. `scripts/seeds.py` makes `experiment/seeds.json`
  (Git-ignored, as in the backoffice task) with the case seed and the marker; `make_cases.py` uses
  it unless given `--seed`. The cases were regenerated with a new seed; no committed file holds it.
- **A plain runner (03; must-fix).** The shipped `run_examples.py` explained how answers were
  recorded and filtered. It is now `runcases.py` alone: run a case with the limits, compare,
  `check` mode only. Recording moved to `recorder.py`, run in builder stages only: the agent
  image's builder records the visible examples and renumbers the kept ones `E00001` onwards
  without gaps.
- **gVisor and shared hosts (10b, 13).** A missing `CapAmb` counts as 0 (ambient capabilities are a
  subset of the permitted ones); each limit must be at most the wanted value rather than equal to
  it; each evaluation runs submitted code as a random uid and gid of its own, so the 512-process
  limit counts only its own runs on a shared host; every run, recorded or graded, is held to 4 GB
  of memory in use by a watchdog in the runner (`MEMORY_LIMIT`), which a 2 GB `MAP_NORESERVE` data
  stack reservation does not touch.
- **Determinism (11).** A third recording run, perturbed (the binary and its TinyCC files under
  another path, 4 KB of environment padding, `GLIBC_TUNABLES` without AVX2 and FMA and without the
  malloc cache, a stack 256 KB smaller, one CPU), must print the same, or the case is dropped
  (`dropped_perturbed`; more than 10% fails the build). A case is kept on CPU time (0.4 s) and a
  generous wall time (1 s), so a busy builder hardly changes the kept set; hangs count as slow,
  output over the limit on its own; a JIT failure reported in JSON counts as a crash. Every stage
  starts from `ubuntu:24.04@sha256:73b99939...`. `build.sh` maps the source and build directories,
  fixes the TinyCC fallback directory, relinks the same objects dynamically where the static link
  fails, and writes `build.txt`: the link, the binary's sha256 and its sha256 with the marker
  zeroed. `recording.json` carries it with the host (CPU, kernel, CPUs, glibc), the recording's wall
  time and the sha256 of the kept ids; `solve.sh` keeps its build log, smoke-tests the installed
  `/app/rebuild/goose`, and writes `build.txt` to `/logs/agent/`; `metrics.json` gives the graded
  program's hashes and the host. Where the toolchains match, the oracle's sha256 without the marker
  equals the recording compiler's.
- **Help text (12, coordinator).** The patch removes every removed option from the help and so from
  the completion scripts (`-D`, `--stdlib`, `GOOSE_STDLIB`, `--include`, `-o`, `--standalone`,
  `--header`, `--emit-runtime`, `--unsafe-no-rf-check`, `--gen-runtime-header`, `goose build`); `help
  c` and `help build` say that this build writes no C. `smoke.sh` and `apply.sh` prove it.
- **Instruction (03, 12).** A reason to want our own implementation (own it outright, so the
  lawyers ask for a clean room); why standard error is free; the playground's switches (`--debug`,
  `-O0`, `-O1`, the default level, `--color never`, shell completion); the sidecar refusal as the
  build does it; the internals options and `format --verify` out of scope; "must match", with the
  implementation notes' latitude ruled out; `/tmp/goose-case`; the environment and limits by
  reference to `run_examples.py`; 4 GB beside the 2 seconds.
- **Counts (private 1,500; visible 300).** run 488, library 83, modules 103 (62 LangArena), check
  579 (418 on error tests and warning programs, 161 broken on purpose), rejected 125 (118 with
  JSON), format 103 (85 standard input, 18 `--check` workspaces), command line 19; visible: run
  112, library 14, modules 20, check 105, rejected 25, format 16, command line 8. Programs behind
  the private cases: median 36 lines, 90th percentile 156, largest 931; 437 cases on programs of 80
  lines or more. Private library use: base64 4, binary 9, csv 8, dictionary 53, exception 42, json
  8, mat 19, quat 8, regex 7. Runner markers 0, inputs starting with a blank line 0. No case passes
  arguments after `--`.
- Preflight passes on bundle `2c5b8eacb5a2`.

### 2026-11-19 (round 4: QA pass 07b and the red team, pass 20)

Verifier and patch only; the cases are unchanged.

- **The reward cannot be lost to the submission (07b M1, must-fix).** `identity()` read
  `/app/rebuild/goose` whole, following links, before `reward.txt`: a link to `/dev/zero`, or a 3 GB
  file with a fake marker (3x its size in memory, measured), left no reward. `reward.txt` is now
  written right after grading or a refusal, before any metadata. `identity()` hashes only a regular
  file that is not a link, of at most 512 MB, in 1 MB chunks, with the marker-free hash in the same
  pass, and never raises; the marker search reads each inode once, `goose` first, in overlapping
  chunks; nothing else reads the submission.
- **Time is bounded (07b M2, must-fix).** Cleanup started one `rm` per leftover directory and one
  `ipcrm` per IPC object, outside the 3,300-second budget (1,500 directories ran 4.7 s past it;
  about 10^5 would pass the 3,600-second step limit). One deadline from the start of `main()` now
  covers sealing, the scans, every reset and every case, and no case or reset starts within 120 s of
  it. Each sweep is one `find` per writable directory, handing what the uid owns to as few `rm -rf`
  runs as the names need; IPC objects go in one `ipcrm` per kind. A submission of more than 200,000
  entries or 4 GB of files is not run (reward 0, a note), so sealing and the marker search are
  bounded too, and the search can no longer run out of budget and pass a file it did not read
  (07b S4). A `goose` whose marker-free hash is the recording compiler's is not refused for that:
  the reference solution builds the same compiler, with an all-zero marker, and may match it.
- **Processes and memory (07b S1, S2).** Every pid of the uid is killed whatever its leader's state
  (a leader that exited with threads left reads Z), and the memory watchdog keeps watching after
  standard output closes.
- **Mapped uids (07b S3; red team 3).** A uid of 2^20 or more is unmapped where a user namespace maps
  65,536 ids (rootless Docker, Podman, remapped hosts), which would have made every evaluation an
  error. The id now comes from inside `/proc/self/uid_map` and `gid_map`, drawn from 20000-60000 and
  avoiding the image's ids, 65534 where the map is tight, and a scratch directory must accept it
  before anything is graded.
- **No `/proc` program (red team 1).** `goose run /proc/self/environ`, or a module or link reaching
  `/proc`, `/sys` or `/dev`, went around `embed_file`'s rule and printed the compiler's environment
  and memory map in its messages. The patch (a seventh file, `src/utils.h`) makes `LoadFile`, which
  reads every program, module and formatted file, and `embed_file` refuse a file whose real path,
  taken from the opened file, is under those trees. `smoke.sh` proves it for `run`, `check`, an
  import and `format --check`, by name and by link.
- **Static PIE (red team 2).** `build.sh` links a static PIE first, so the binary's addresses still
  change from run to run, then static, then dynamic, each from the same objects and each checked by
  `smoke.sh`; `build.txt` says which.
- Checks: 36 task checks (new: bounded hashing, cleanup cost with 20,000 leftovers per run, mapped
  ids, oversized submissions). Preflight passes on bundle `e8a22c31ce25`.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-rebuild-compiler` | Implemented: instruction, agent image with the execute-only compiler, separate verifier image, reference solution. |
| Further steps | Not designed. Candidates: the next upstream commits from their changelog; `goose build` with an external C compiler. |
| Hardening | `common/hardening/`: the patch, `apply.sh` (before each build), `build.sh` (the build: static link first, `smoke.sh` on the result, `build.txt`), staged by packaging into both images' build contexts and the solution; the build marker into the images' contexts only. |
| Private inputs | `steps/01-rebuild-compiler/tests/private/cases.json` and `experiment/visible.json`, Git-ignored, from `scripts/make_cases.py`. Outputs are recorded when the images are built; `recording.json` beside them describes the recording and appears in `metrics.json`. |
| Upstream source | Not in Git. Packaging stages the build sources less `stdlib/os.goose` and `stdlib/ffi.goose` (into both images and the solution) and the documentation and samples (into the agent image) from a checkout at the pinned commit. |
| Oracle | The original compiler, built by `solve.sh` from the shipped sources with the images' hardening and `build.sh`; then a non-scoring sandbox probe (`probe.c`) writes `/logs/agent/probe.txt`. |
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
twice from the original, without crashing. Partial progress is the share of cases that match.

### Realism

A clean-room implementation, written from the manual and the released binary by a team that may
not read the source, is how compatible second implementations are made (Wine, Samba, the PC
BIOS). The exact bar has real consumers: golden files recorded from the compiler and editor
tooling that parses its JSON diagnostics. The documentation, samples and standard library are
the upstream's own; cases include programs that do not compile, programs over several files
(LangArena's benchmarks among them), every standard-library module written in Goose, and code to
format laid out the way people leave it.

### Difficulty

A rebuild needs a parser for a new syntax, a type checker with inferred lifetimes and its
exact error messages, an implementation that runs programs with the same output (including
aborts and their exit codes), a formatter that keeps comments, and the command line. The linter
it replaces was 12,000 lines; this target is about 75,000 lines of C++, of which about 35,000 to
50,000 are in scope (MirrorCode's large bucket), and its error messages come from a novel
analysis. The upstream compiler was written with AI in the image of its author's Lobster; that
lends architecture, not the graded behaviour. QA passes 17 and 19 expect 0.25 to 0.55 for a
strong model in one session. Not yet measured with a model.

Floors without an implementation, by design (`recording.json` measures them at each build): a
table of the command line's answers plus one constant answer per kind of case passes at most
4.5%, enforced by the recorder; that plus a perfect formatter about 11% (format is 103 of 1,500
cases); printing nothing and exiting 1 at most 1.2% plus the silent command-line cases. QA pass 05
measured 16 to 19% and 27% for the previous cases.

### Initial feasibility

Solved by construction: the original passes every kept case. For an agent, unknown.

## Workload

A run is one trial of 9.6 hours (one task row per experiment, no continuation tasks). The
instruction states no time budget.

## Verification

1. `/app/rebuild` arrives as the declared artifact.
2. The verifier picks a random uid and gid for submitted code and checks the unprivileged run first
   (no_new_privs from the status file or `prctl`, ids, groups, capabilities, limits, and a set-id
   root copy of `id` that must report that uid); a failure is an evaluation error, before submitted
   code runs. It then seals `/app/rebuild` (root-owned, read-only for anyone else, no set-id bits)
   and searches it for the original's build marker: a submission that cannot be sealed or holds the
   marker gets reward 0 with a note.
3. Before each case it kills every process of that uid, removes what it left in every
   world-writable directory and its System V IPC objects, and writes the case's files into a new
   `/tmp/goose-case`, owned by it, with new empty `HOME` and `TMPDIR` directories.
   `/app/rebuild/goose` runs there with no_new_privs, the case's arguments and standard input, no
   network, the recorder's resource limits, 2 seconds, 4 GB of memory in use and at most 1,000,000
   bytes of output.
4. A case passes when the exit code and the bytes of standard output equal the recorded ones. A
   case that cannot be set up or started, runs too long or prints too much fails; none of that is
   an evaluation error.
5. After 3,300 seconds of runs in all the verifier stops, and the rest count as failed (1,500
   runs at the 2-second limit take about 3,000; every kept case took at most 0.5 seconds when
   recorded). At the end it cleans up again, then writes `reward.txt`, then `metrics.json`.

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
  describes the recording (cases kept by kind, cases left out and why, how each was settled, run
  times, answers still upstream's, the four baselines, the link) for `metrics.json`.
- Floor: see Difficulty; measured in `recording.json` (`baselines`) at each build.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 2, 3, 5, 10, 12).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read, copy, trace or dump the compiler from outside its process, or preload a library into it | File mode and group of the program; its link | QA passes 04 (finding 2) and 04b (findings A, B: a dynamic binary honours `LD_PRELOAD` where an exec is not secure; gVisor unknown) | `/opt/goose/goose` is `root:goose`, mode 2711: execute-only and setgid, so the process is not dumpable; `build.sh` links it static and stripped, so no loader runs at all (dynamic and stripped where the static link fails; `recording.json` says which) | Gid dropped on a traced exec and the sandbox's handling of both, unmeasured; a dynamic fallback | `/logs/agent/probe.txt` of the first oracle trial | 🟡 YELLOW / UNASSESSED |
| 2 | Read the compiler from inside its process: `goose run` compiles the program into the compiler with TinyCC; or have it write its C, or read its own process files as source | Hardened build (`common/hardening/`) | QA pass 04, finding 1 (a 20-line program printed the code through `ffi`, `os` and a user `extern`); four further ways in found by the audit; passes 04b (`embed_file("/proc/self/maps")`), 08 (`--emit-runtime`, `-o`, `goose build` print or leave C) and 20 (`goose run /proc/self/environ`) | No `os` or `ffi` module; `extern` only in the installed standard library; no `-D`, `--include`, `--stdlib`, `GOOSE_STDLIB` or `GOOSE_TCCLIB`; no sidecars; no unsound option; nothing writes C; `embed_file` only under the embedding file's directory, checked on the opened file; no shaders; no program, module, formatted or embedded file under `/proc`, `/sys` or `/dev`; a static PIE. `smoke.sh` proves each refusal at every build of both images and of the solution; the remaining standard-library externs read nothing outside their arguments (audited) | A memory-safety bug in the compiler, its runtime or TinyCC | The first build's smoke test, then pass 04's programs run as `dev` on Oddish | 🟡 YELLOW / UNASSESSED |
| 3 | Run as root, or as a user who can read the program | `[agent] user` on Oddish | Not tested on this task | `user = "dev"` | Depends on each harness | Short trial that prints `id` (the probe prints it) | 🟡 YELLOW / UNASSESSED |
| 4 | Deliver the original, or a wrapper that calls it | Separate verifier image; the agent image's `/app`; the build marker | QA passes 07 and 13 (a link at `/app/rebuild` to `/opt/goose`, followed by the root-run collector, scored about 1.0) | The final verifier image holds no copy of the compiler; `/app` is root's and sticky, so `dev` cannot replace `/app/rebuild`; the verifier refuses (reward 0, a note) any submission holding the original's random build marker (checked: ownership, the marker search, the staging) | A copy the agent cannot read anyway, transformed to hide the marker | First trial as `dev`: `/app/rebuild` cannot be renamed | 🟢 GREEN / LOW |
| 5 | Fetch the public source | Agent network policy | Not probed on this task | `network_mode = "no-network"` for the agent; the source is not in the agent image | The repository is public; a harness with network access would defeat the task | Probe from a trial | 🟡 YELLOW / UNASSESSED |
| 6 | Lookup table over the visible cases or the shipped programs | Private cases | QA pass 06 (229 cases on shipped programs, one private test printed in a design note); by check since | No private case is built on a shipped program or a variant of one; a private program that a shipped file holds or that equals a visible program is left out; the generator and packaging refuse a private case whose input a shipped file or a visible case holds (checked) | Upstream tests that differ from a visible one by a few tokens (pass 06, note 4) | Keep | 🟢 GREEN / LOW |
| 7 | Read expected output or errors out of the case files, across cases | Case generation, recording and the verifier | QA pass 06b, finding 3 (format inputs quoted the exact message of 96 graded cases) | No run or check input has a comment. Format inputs carry the program's own comments only where no other case is built on its family, less runner markers and any comment quoting an answer upstream publishes; the recorder drops any case whose comments quote any recorded answer. Nothing a run writes reaches the next: new workspace, `HOME` and `TMPDIR`, every writable directory swept, IPC removed (checked) | Short numeric output quoted in a program's own comment, harmless where no other case uses the program | Read `dropped` in `recording.json` | 🟢 GREEN / LOW |
| 8 | Recall upstream's published answers (tests beside their expected files) | Case generation and recording | QA passes 19 (39.5% of cases were upstream tests unchanged) and 06b (at least 45 run answers and 314 error messages still upstream's) | Cases are renamed, moved or edited, run cases preferring an edit whose output differs, error tests renaming first the names their messages mention; `recording.json` counts exactly the run answers equal to upstream's file and the error cases whose messages are upstream's text verbatim | Message text stays upstream's where no renamed name is in it: exact wording is the owner's choice (pass 01, F1). Goose was published after the training data of current models; recall becomes a risk for models trained later | Read `recording` in the first baseline's `metrics.json`; re-check before models trained after 2026-08-30 | 🟢 GREEN / LOW |
| 9 | Tamper with the reward files, or suppress them by forcing an evaluation error | Separate verifier container | QA passes 10 (a symlinked workspace), 07 and 10b (a deep tree raised `RecursionError` past `except OSError`; demonstrated), 07b (a link to `/dev/zero` or a 3 GB fake-marker `goose` hashed before the reward; cleanup per entry past the step limit) | Verifier starts fresh with only `/app/rebuild`; submitted code runs as a random mapped uid; the reward is written right after grading; every read of the submission is bounded and refuses links; one deadline covers everything, with one `find` per swept directory and one `ipcrm` per kind; submissions over 200,000 entries or 4 GB are not run; removals are `rm -rf` without a depth limit; every case catches every exception; a case that cannot be set up or started, runs too long, prints too much or uses 4 GB fails that case; the uid's processes are killed and reaped and its files removed before every case and before the results are written; `reward.txt` comes before `metrics.json` (checked: deep trees, cleanup between cases) | Kernel keyrings and IPC where `/proc/sysvipc` is missing survive between cases; they carry no answer | Keep | 🟢 GREEN / LOW |
| 10 | Infer an evaluation from the files and text | Instruction and example files | Lesson from `markdown-linter-rebuild` | Neutral runner text; no reference, grading, session or time wording (checked) | An agent can still guess that more cases exist | Read the first trajectories | 🟡 YELLOW / UNASSESSED |
| 11 | Run as root in the verifier through a set-user-id or capable file in the submission, then read the recorded answers | Privilege drop and sealing | QA pass 10, F6, and the backoffice task's QA (a submitted file can arrive set-user-id root on Oddish's Docker backend) | The submission is sealed root-owned without set-id bits before anything runs; `setpriv --no-new-privs` keeps any file from adding privileges; a process started that way must show no_new_privs (in its status file or by `prctl`), the unprivileged ids, no groups and no capabilities (a missing `CapAmb` counts as 0), and a set-id root copy of `id` must report the sandbox uid, or nothing is graded (checked: sealing and the refusals) | A kernel or runtime that ignores no_new_privs; the run-time probe then refuses to grade | First baseline's verifier log | 🟢 GREEN / LOW |
| 12 | Pass cases with no compiler: the command line's answers, constant answers, a whitespace detector for `format --check`, a formatter clone | Case mix and the recorder's selection | QA pass 05 (16 to 19% with no implementation, about 27% with a formatter clone, on the previous cases) | Rejected programs answer in JSON; edits that leave a check clean or a run silent are passed over; any one answer is capped at 1.2% of cases and `[]` at 5% of checks; the recorder drops cases until a table plus constants passes at most 4.5%; format is 103 of 1,500 cases and `--check` 18 workspaces with formatted and slipped files mixed; `recording.json` measures four baselines (checked: selection and baselines) | A formatter clone is legitimate work, worth about 5.5% | Read `baselines` in the first baseline's `metrics.json` | 🟡 YELLOW / UNASSESSED |
| 13 | A crash of the original graded as an answer no implementation can give | Recording | QA pass 18, F2 | A recording run that ends by a signal or with an internal-error, JIT, sanitizer or C++ abort report is dropped; more than 2% fail the build (checked) | None found | Read `dropped_crashed` | 🟢 GREEN / LOW |

Licence: the upstream is Apache-2.0. Its `LICENSE` is shipped with the documentation in
`/app/docs` and with the reference solution's build.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (36 tests) with `ci_checks` (27), Python 3.13, and `check_repository.py` | working tree, 2026-11-19, round 4 | pass |
| Oddish preflight | bundles `ca4309ce85fc`, `19c1c91c58fc`; `f98273d8a455` (hardened build, new cases); `5cb265da1a10` (verifier round 2); `a296bbd1ed2d` (round 2 continued); `2c5b8eacb5a2` (round 3); `e8a22c31ce25` (round 4) | pass |
| Hardened build | bundle `e8a22c31ce25` | not built yet: `apply.sh` tested on a pristine copy of the seven patched files (applies once, refuses twice), `smoke.sh` tested against stand-ins that do and do not refuse; the static PIE and static links, the marker, the help text, the `/proc` refusals and the LangArena glue are untried |
| Privilege drop | bundle `e8a22c31ce25` | not run as root yet: sealing, the refusal of a weak drop, the `prctl` and `CapAmb` fallbacks, the marker search, bounded hashing, mapped ids, size caps and the cleanup between cases (deep trees and 20,000 leftovers per run included) are checked; the drop itself first runs in the first baseline |
| Recorder | bundle `e8a22c31ce25` | checked against a stand-in compiler (settling, the perturbed run, crashes, drops, renumbering, baselines); first run on the original at the first build |
| Oddish baselines, version 1 | bundle `ca4309ce85fc` (earlier generator), task `...goose-compiler-rebuild-9979b548`, experiment `goose-compiler-rebuild-20261118` (https://www.oddish.app/experiments/4b947cc6), one row | reference 1.0 twice (1,500 of 1,500: the recording kept every case), no-op 0.0 twice. First build of both images and of the solution's compiler; Archil, no fault |
| Oddish baselines, version 2 | bundle `19c1c91c58fc` (current generator), same task, experiment `goose-compiler-rebuild-v2-20261118` (https://www.oddish.app/experiments/f14b3da8), one row | reference 1.0 twice (1,500 of 1,500), no-op 0.0 twice |
| Oddish source audit, version 2 | trial 13 | no must-fix finding. Two should-fix: upstream's `docs/implementation.md` says an equivalent implementation need not reproduce diagnostic wording, while the JSON diagnostics are compared exactly (answered in the instruction since); the example outputs are recorded at build time and cannot be inspected in the package (kept: the original must produce them) |
| `harbor check` | none | not run |

## Build and deliver

```bash
git clone https://github.com/aardappel/goose <checkout> && git -C <checkout> checkout 745901fd48224feb782d707922a20dcd25c669fd
cd tasks/swe-m2-software-engineer/goose-compiler-rebuild
python scripts/make_cases.py <checkout> --count 1800 --visible 300 \
    --out-private steps/01-rebuild-compiler/tests/private/cases.json --out-visible experiment/visible.json
GOOSE_CHECKOUT=<checkout> python scripts/package_step.py        # add --flat for a bundle without steps
```

The case seed and the build marker come from `experiment/seeds.json`, which `scripts/seeds.py`
makes once at random and which is never committed: anyone with the generator, upstream's checkout
and the seed could regenerate the hidden cases.

The hardening lives in `common/hardening/`: packaging stages it into both build contexts and the
solution (the marker into the images' only), and every build runs `apply.sh` before `build.sh`,
which runs `smoke.sh` on the result.

## Remaining work

- Baselines of the current bundle under the task's experiment (one row): the first build of the
  hardened compiler (static or dynamic: `link`), whose smoke test must pass in both images and in
  the solution, and the first run of the privilege checks as root. Read `recording` in the
  reference run's `metrics.json`: drops by reason (LangArena cases dropped for not completing
  mean a glue error), crashes, how cases were settled, answers still upstream's, the four
  baselines; and `limits`. Read `/logs/agent/probe.txt`. Then the platform's source audit. Model
  trials wait for the owner.
- Probe findings 1, 2, 3, 5 and 10 from a trial; run pass 04's programs as `dev`; check that `dev`
  cannot rename `/app/rebuild`. Compare `/logs/agent/build.txt` (the oracle's build) with
  `recording.build` in `metrics.json`: the link, and the sha256 without the marker.
- Two oracle trials on different workers should each score exactly 1.0 with `seconds_max` under
  1 second (pass 11); any failed id goes on a deny-list and the cases are recorded again.
- Not done from pass 02: splitting single-file programs into modules with other root paths (F5),
  comments in run and check inputs (F6), edits that make type errors (F7).
- Open: a deterministic subset of `os` (standard input, arguments, files in the workspace) would
  bring input-reading programs back without `ffi` (pass 01, F4); the exact diagnostics bar is the
  owner's call (pass 01, F1).
- `harbor check` and ratings.
