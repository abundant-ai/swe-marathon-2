# Reimplement the `goose` compiler

## Goal

Goose is a systems programming language, first published in August 2026, that our tools are
written in. Its compiler, `goose`, also runs Goose programs, checks them and formats them. We
need an implementation of our own, written clean-room: the team that writes it works from the
published documentation, the standard library's sources and the released compiler, which it may
run as often as it likes, and never reads the compiler's source code. Write that implementation.

It has to behave exactly like the released compiler. Our CI keeps the output, the formatting
and the `--diagnostics json` errors recorded from it for thousands of programs, our editor
plugin parses `goose check --diagnostics json` and shows each message at its position, and our
scripts act on its exit codes. A different output, message or position breaks them.

## Context

- The released compiler is installed as `goose` on `PATH`. You can run it as often as you
  like. You cannot read the file, copy it or inspect it; you can only execute it.
- It is our deployment build, which differs from the documentation in a few places: its
  standard library has no `os` and no `ffi` module, it refuses `extern` declarations outside
  the standard library's own files, it reads no sidecar `.build` files, and it has no `-D`,
  `--include`, `--stdlib` or `--unsafe-no-rf-check` option.
- Its documentation is in `/app/docs`: the README, a tutorial, the language reference and
  specification, the standard library, the command line (`docs/command_line.md`), design notes,
  and sample programs (`samples/`). `goose help` and `goose help <command>` describe the
  command line.
- The standard library's sources are in `/usr/local/share/goose/stdlib`, here and on the
  machine where your implementation will run. The released compiler reads them from there.
- `/app/examples/examples.json` holds example runs and `/app/examples/outputs.json` what the
  released compiler prints for each. An example is one or a few files, an argument list and
  sometimes standard input. `python3 /app/examples/run_examples.py check <program>
  /app/examples/examples.json /app/examples/outputs.json -v` runs them against any program and
  lists the ones that differ.
- The examples cover running programs (`goose run`), including programs that do not compile
  and programs split over several files, checking them (`goose check`, with the errors as JSON
  through `--diagnostics json`), formatting (`goose format`) and the rest of the command line:
  help, version, mistyped commands, missing files and wrong options.
- There is no network access. Python 3.12, Go, Rust (`rustc` and `cargo`, standard library
  only) and a C and C++ toolchain (`gcc`, `g++`, `make`, `cmake`) are installed, here and where
  your implementation will run. No Goose library or tool is available apart from the released
  compiler.

## What to deliver

Your implementation in `/app/rebuild`, with an executable `/app/rebuild/goose`.

- Given the same files, arguments and standard input, `/app/rebuild/goose` prints the same
  standard output and ends with the same exit code as the released compiler. Its messages on
  standard error may differ.
- That covers what a program prints under `goose run`, the errors and warnings reported with
  `--diagnostics json`, the output of `goose format` (comments included) and the command line's
  own answers, for everything the released compiler accepts or rejects, not only for the
  examples: programs that do not compile, programs that abort, wrong options and missing files
  included.
- Error and warning messages count word for word: with `--diagnostics json` they are part of
  standard output, whatever the documentation says about other implementations.
- It must not call the released compiler: it will be used where that is not installed.
- Everything it needs at run time is inside `/app/rebuild`, apart from the standard library's
  sources and the tools listed above.
- Where it will be used, it runs as an unprivileged user that cannot write to `/app/rebuild`.
  Each run starts in a new working directory under `/tmp` that holds only that run's files,
  with `HOME` set to `/tmp`, nothing left in `/tmp` from earlier runs, and the same resource
  limits as `run_examples.py` applies (an 8 MB stack among them).
- Each run finishes within 2 seconds; the released compiler takes a fraction of a second.
- Out of scope: `goose build`, `goose fetch` and packages, `goose lsp`, `goose toolchain`,
  writing C with `-o`, the options that report on a compile (`--stats`, `--specs`, `--stacks`,
  `--bce-lines`, `-v`), threads, calling C (`extern` functions and `extern` blocks in a
  program's own files, sidecar `.build` files), and the `os`, `ffi`, `gfx`, `ui`, `audio` and
  `physics` modules.

## Completion

The work is complete when your program cannot be told apart from the released compiler by
running both. Keep `/app/rebuild/goose` runnable at all times.
