# Reimplement the `bpl` interpreter

## Goal

BasedPL (BPL) is an array language in the APL family. Our analytics team writes its reports and
data checks in it, and because those scripts run on shared machines, we run them with a sandboxed
build of its interpreter, `bpl`, version 0.1.95. Upstream changes the language in patch releases
and will not support an old release, while our reports have to reproduce exactly for years, so we
are keeping 0.1.95's behaviour ourselves. Our legal policy is that anything we embed for that long
is written clean-room, with a record of where every part came from: the people who write it work
only from the published documentation and from running the sandboxed build, and never read the
interpreter's source code. Write that implementation.

It has to behave exactly like the sandboxed build:

- CI runs our BPL scripts and compares what they print with golden files recorded from it.
- Our notebook service drives `bpl --worker`: it shows the values and displays in the worker's
  JSON replies and highlights the source spans of errors. Saved notebooks keep those replies as
  text, and re-running a saved notebook in one worker session has to reproduce them byte for
  byte, down to the spacing and the way each number is written.
- Shell jobs pipe data into BPL programs and act on the exit status, and our wrapper scripts show
  `bpl --help` in their own usage text.
- Analysts also use `bpl` straight from their shells, piping lines into it, and between the
  notebooks and the scripts they use the whole language, derivatives with `∂` included: there is
  no part of it we can do without.

A different output, message or exit status breaks one of them.

## Context

- The sandboxed build is installed as `bpl` on `PATH`, execute-only, so that nobody in the clean
  room reads its code: you can run it as often as you like, but not read, copy or inspect the
  file. The clean-room rules cover the build too: do not disassemble, trace or dump it; learn what
  it does only from what it prints.
- Its documentation is in `/app/docs`: the guides, the reference for every glyph
  (`/app/docs/glyphs`) and system function (`/app/docs/system`), the study notes, and `llms.txt`,
  the index. Pages that upstream publishes as notebooks are there as their text and code; we left
  out the results stored in them, which came from upstream's build rather than ours. Inside `bpl`,
  `]help` shows the same pages.
- Our scripts and their golden files hold client data and never leave CI, and upstream's
  repository is off limits to the clean room, so we have no programs or recorded runs to give
  you. What the sandboxed build prints is the specification: when the documentation and the build
  disagree, the build is right.
- The sandboxed build differs from the documentation in a few places, and its own `--help`
  describes it as it is:
  - it reads files (a program file, `•nget`, `•load`) only where the file lies under the
    directory it was started in, and never under `/proc`, `/sys` or `/dev`;
  - it writes no file: `•nput` to a path is refused, while `"-" •nput` still writes to standard
    output; `•readdir`, `•metadata`, `•copy`, `•rename`, `•remove` and `•mkdir` are refused, and
    `•fetch` has no network;
  - it has no `--kernel` and no `--costs` mode, and `--worker` serves only `code`, `call` and
    `bindings` requests, apart from `interrupt`;
  - it never compiles BPL to machine code, and the interactive REPL keeps no history file.
- The clean room has no network access. Python 3.12, Go, Rust (`rustc` and `cargo`, standard
  library only) and a C and C++ toolchain (`gcc`, `g++`, `make`, `cmake`) are installed, here and
  where your implementation will run; write it in whichever of them you prefer, since our team
  maintains all of them. No BPL library or tool is available apart from the sandboxed build.

## What to deliver

Your implementation in `/app/rebuild`, with an executable `/app/rebuild/bpl`.

- Given the same files, arguments and standard input, `/app/rebuild/bpl` prints the same standard
  output and ends with the same exit status as the sandboxed build. Nothing reads standard error
  (CI keeps standard output and the status, and the notebook service reads errors from the
  worker's JSON), so the messages it writes there may differ.
- That covers every way in: `bpl -e EXPR [ARG...]`, `bpl FILE [ARG...]`, a program on standard
  input with `bpl -`, lines piped into `bpl` with no arguments, `bpl --worker` sessions, and what
  the command line itself prints (`--help`, `--version`, wrong arguments, missing files). It
  covers everything those print:
  - values as `bpl` displays them, under every `•prefs` display setting and with `⎕←`, `⍕`,
    `]display` and `]dissect`, and functions and trains as they are shown;
  - exact integers, rationals, complex numbers and floats, keyed arrays and records, strings, and
    derivatives;
  - text read from standard input with `⎕` and `•nget "-"`, and modules loaded with `•load`;
  - errors, whether a program catches them (`::` and `$e`, with their kind, message, line and
    column), the worker reports them, or they end a run with its exit status and the output
    printed before them.
- Error messages must match word for word wherever they reach standard output, and so must the
  positions and spans that come with them. Where the sandboxed build crashes, do what is sensible;
  nothing of ours depends on that.
- It must not call the sandboxed build: it replaces it, and will be used where that is not
  installed. Everything it needs at run time is inside `/app/rebuild`, apart from the tools listed
  above.
- When you finish, `/app/rebuild` is copied as it stands to the machines it will run on. A link
  that points outside the directory is replaced there by a copy of what it points to, and pipes,
  sockets and devices are left out. With those copies it may hold at most 100,000 files and
  directories and 1 GB, with no path inside it longer than 1,000 bytes, and the disk needs that
  much room left to copy it; otherwise it is not copied.
- Our job runner starts every `bpl` the same way, and it will start yours like this: as an
  unprivileged user that cannot write to `/app/rebuild`, in a new, empty working directory into
  which only that run's files are put, with `HOME` and `TMPDIR` set to new empty directories. Runs
  share nothing: whatever one run writes is gone before the next starts. The environment holds
  only `PATH=/usr/local/bin:/usr/bin:/bin`, `LANG` and `LC_ALL` set to `C.UTF-8`, `TERM=dumb`,
  `NO_COLOR=1`, `HOME` and `TMPDIR`. Standard input and output are pipes, and none of the standard
  streams is a terminal. Each run gets an 8 MB stack, at most 512 processes and threads, and files
  of at most 256 MB.
- Each run finishes within 2 seconds, a whole worker session included: the job runner stops any
  `bpl` still running then. A run uses at most 4 GB of memory and holds at most 1 GB and 100,000
  files and directories of its own on disk. The sandboxed build finishes each of our programs in a
  small fraction of that time.
- We will maintain this code for years: keep it modular, with reading source, evaluation, the
  primitives and operators, numbers, display, and the command line and worker in separate parts.
- Out of scope: what our scripts never rely on. Golden files cannot hold anything that changes
  from run to run, so random numbers (`¿`, `•rand`, `•distribution`, the random `•uuid` versions)
  and the clock (`•time`, `•date`, `•delay`) are out. Our reports are text, so drawing (`•plot`,
  `•svg`, `•image`, `•canvas`) is out. We use none of `•fetch`, the refused file functions,
  `•hash`, `•deflate`, `•mime`, `•js` or `⇄`. The interpreter's reports on itself (`•storage`,
  `•memory`, `•explain`, `•index`, and the `fusion`, `threads` and `seed` settings) describe
  upstream's engine, not yours, and of `•host` we need only `"args"` and `"version"`. Our
  notebook service enforces its own deadlines by restarting the worker, so the worker's
  `timeout_ms` and `interrupt` are out, as are `]help`, `]clear` and the interactive REPL's line
  editing. You need not make any of these work, but a program or module that mentions them in
  code it never runs must still load and run.

## Completion

The work is complete when your program cannot be told apart from the sandboxed build by what it
prints on standard output and how it exits. Keep `/app/rebuild/bpl` runnable at all times.
