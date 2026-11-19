# Reimplement the `bpl` interpreter

## Goal

BasedPL (BPL) is an array language in the APL family. Our analytics team writes its reports
and data checks in it, and we run them with a sandboxed build of its interpreter, `bpl`,
version 0.1.95. Upstream changes the language in patch releases, and we have to keep 0.1.95's
behaviour for years, inside a product we license under our own terms. So we want an
implementation of our own, written clean-room: the people who write it work from the published
documentation and from the sandboxed build, which they may run as often as they like, and never
read the interpreter's source code. Write that implementation.

It has to behave exactly like the sandboxed build. CI runs our BPL scripts and compares what
they print with golden files recorded from it. Our notebook service drives
`bpl --worker` and parses its JSON replies: values, displays, and errors with their messages and
source spans, which the notebook highlights. Shell jobs pipe data into BPL programs and act on
the exit status. Different output, a different message or a different exit status breaks one of
them.

## Context

- The sandboxed build is installed as `bpl` on `PATH`. You can run it as often as you like. You
  cannot read the file, copy it or inspect it; you can only execute it.
- Its documentation is in `/app/docs`: the guides, the reference for every glyph
  (`/app/docs/glyphs`) and system function (`/app/docs/system`), the study notes, and
  `llms.txt`, the index. Pages that upstream publishes as notebooks are there as their text and
  code, without the notebooks' stored results. Inside `bpl`, `]help` shows the same pages.
- Nobody has a test suite or a collection of recorded runs to give you. What the sandboxed build
  prints is the specification: when the documentation and the build disagree, the build is right.
- The sandboxed build differs from the documentation in a few places, and its own `--help`
  describes it as it is:
  - it reads files (a program file, `•nget`, `•load`) only where the file lies under the
    directory it was started in, and never under `/proc`, `/sys` or `/dev`;
  - it writes no file: `•nput` to a path is refused, while `"-" •nput` still writes to standard
    output; `•readdir`, `•metadata`, `•copy`, `•rename`, `•remove` and `•mkdir` are refused, and
    `•fetch` has no network;
  - it has no `--kernel` and no `--costs` mode, and `--worker` serves only `code`, `call` and
    `bindings` requests;
  - it never compiles BPL to machine code, and the interactive REPL keeps no history file.
- There is no network access. Python 3.12, Go, Rust (`rustc` and `cargo`, standard library only)
  and a C and C++ toolchain (`gcc`, `g++`, `make`, `cmake`) are installed, here and where your
  implementation will run. No BPL library or tool is available apart from the sandboxed build.

## What to deliver

Your implementation in `/app/rebuild`, with an executable `/app/rebuild/bpl`.

- Given the same files, arguments and standard input, `/app/rebuild/bpl` prints the same standard
  output and ends with the same exit status as the sandboxed build. Nothing of ours reads standard
  error (CI keeps standard output and the status, and the notebook service reads errors from the
  worker's JSON), so the messages it writes there may differ.
- That covers every way in: `bpl -e EXPR [ARG...]`, `bpl FILE [ARG...]`, a program on standard
  input with `bpl -`, lines piped into `bpl` with no arguments, `bpl --worker` sessions, and the
  command line's own answers (`--help`, `--version`, wrong arguments, missing files). It covers
  everything those print: values as `bpl` displays them, under every `•prefs` display setting,
  with `⎕←`, `⍕`, `]display` and `]dissect`; functions and trains as they are shown; exact
  integers, rationals, complex numbers and floats; keyed arrays and records; strings and text
  read from standard input with `⎕` and `•nget "-"`; modules loaded with `•load`; and errors,
  whether a program catches them (`::` and `$e`, with their kind, message, line and column), the
  worker reports them, or they end a run with its exit status and the output printed before them.
- Error messages count word for word wherever they reach standard output, and so do the positions
  and spans that come with them.
- It must not call the sandboxed build: it replaces it, and will be used where that is not
  installed. Everything it needs at run time is inside `/app/rebuild`, apart from the tools listed
  above.
- Where it will be used, it runs as an unprivileged user that cannot write to `/app/rebuild`.
  Each run starts in a new working directory, `/tmp/bpl-case`, that holds only that run's files,
  with `HOME` and `TMPDIR` set to new empty directories and nothing left from earlier runs anywhere
  it can write. Its environment holds only `PATH=/usr/local/bin:/usr/bin:/bin`, `LANG` and
  `LC_ALL` set to `C.UTF-8`, `TERM=dumb`, `NO_COLOR=1`, `HOME` and `TMPDIR`; its standard input,
  output and error are pipes, never a terminal. It gets an 8 MB stack, at most 512 processes,
  files of at most 256 MB and no core files.
- Each run finishes within 2 seconds, which is how long CI and the notebook service wait for one
  call, uses at most 4 GB of memory, and adds at most 1 GB and 100,000 files and directories to
  the disk; the sandboxed build takes a fraction of a second and far less on our programs.
- We will maintain this code for years: keep it modular, with reading source, evaluation, the
  primitives and operators, numbers, display, and the command line and worker in separate parts.
- Out of scope: random numbers (`¿`, `•rand`, `•distribution`, the random `•uuid` versions), the
  clock (`•time`, `•date`, `•delay`), drawing (`•plot`, `•svg`, `•image`, `•canvas`), `•fetch`
  and the refused file functions, `•hash`, `•deflate`, `•mime`, `•js`, `⇄`, the interpreter's
  reports on itself (`•storage`, `•memory`, `•explain`, `•index`, and the `fusion`, `threads` and
  `seed` settings), `•host` facts other than `"args"` and `"version"`, the worker's `timeout_ms`
  and `interrupt`, `]help` and `]clear`, and the interactive REPL's line editing.

## Completion

The work is complete when your program cannot be told apart from the sandboxed build by what it
prints on standard output and how it exits. Keep `/app/rebuild/bpl` runnable at all times.
