# Reimplement the `goose` compiler

## Goal

Goose is a systems programming language. Its compiler, `goose`, also runs Goose programs, checks
them and formats them. We run Goose programs that people send us, in a playground, in CI and in
an editor plugin, with a sandboxed build of the compiler. We want to replace that build with an
implementation we own outright and can change and license as we choose, so our lawyers have
asked for it to be written clean-room: the team that writes it works from the published
documentation, the standard library's sources and the sandboxed build, which it may run as
often as it likes, and never reads the compiler's source code. Write that implementation.

It has to behave exactly like the sandboxed build. The playground shows what a program prints
and its exit code, CI keeps the output, the formatting and the `--diagnostics json` errors
recorded from it for thousands of programs, and the editor plugin parses
`goose check --diagnostics json` and shows each message at its position. A different output,
message or position breaks them.

## Context

- The sandboxed build is installed as `goose` on `PATH`. You can run it as often as you like.
  You cannot read the file, copy it or inspect it; you can only execute it.
- It differs from the documentation in a few places: its standard library has no `os` and no
  `ffi` module, it refuses `extern` declarations outside the standard library's own files and
  any program that comes with a sidecar `.build` file, it has no `-D`, `--include`, `--stdlib`
  or `--unsafe-no-rf-check` option, it has no command or option that writes C (no
  `goose build`, and no `-o`, `--standalone`, `--header`, `--emit-runtime` or
  `--gen-runtime-header`), `embed_file` reads only files under the directory of the file that
  calls it, and there is no `embed_shader`. Its own help describes it as it is.
- Its documentation is in `/app/docs`: the README, a tutorial, the language reference and
  specification, the standard library, the command line (`docs/command_line.md`), design notes,
  implementation notes (`docs/implementation.md`) and sample programs (`samples/`).
  `goose help` and `goose help <command>` describe the command line.
- The standard library's sources are in `/usr/local/share/goose/stdlib`, here and on the
  machine where your implementation will run. The sandboxed build reads them from there.
- `/app/examples/examples.json` holds example runs and `/app/examples/outputs.json` what the
  sandboxed build prints for each. An example is one or a few files, an argument list and
  sometimes standard input. `python3 /app/examples/run_examples.py check <program>
  /app/examples/examples.json /app/examples/outputs.json -v` runs them against any program and
  lists the ones that differ.
- The examples cover running programs (`goose run`, with and without `--debug` and at `-O0`,
  `-O1` and the default level, as the playground lets people choose), including programs that
  do not compile and programs split over several files, checking them (`goose check`, with the
  errors as JSON through `--diagnostics json`, sometimes with `--color never`), formatting
  (`goose format`) and the rest of the command line: help, version, shell completion, mistyped
  commands, missing files and wrong options.
- There is no network access. Python 3.12, Go, Rust (`rustc` and `cargo`, standard library
  only) and a C and C++ toolchain (`gcc`, `g++`, `make`, `cmake`) are installed, here and where
  your implementation will run. No Goose library or tool is available apart from the sandboxed
  build.

## What to deliver

Your implementation in `/app/rebuild`, with an executable `/app/rebuild/goose`.

- Given the same files, arguments and standard input, `/app/rebuild/goose` prints the same
  standard output and ends with the same exit code as the sandboxed build. Nothing of ours reads
  standard error (the playground and the plugin show errors from `--diagnostics json`), so its
  messages there may differ.
- That covers what a program prints under `goose run`, the errors and warnings reported with
  `--diagnostics json`, the output of `goose format` (comments included) and the command line's
  own answers, for everything the sandboxed build accepts or rejects, not only for the
  examples: programs that do not compile, programs that abort, wrong options and missing files
  included.
- Error and warning messages must match word for word: with `--diagnostics json` they are part
  of standard output. Where the implementation notes let an equivalent implementation differ
  from the compiler, in wording, in what it accepts or in what a `--debug` run still checks
  after optimization, ours may not: it does what the sandboxed build does.
- It must not call the sandboxed build: it replaces it, and will be used where that is not
  installed.
- Everything it needs at run time is inside `/app/rebuild`, apart from the standard library's
  sources and the tools listed above. When you finish, `/app/rebuild` is copied as it stands to
  where it is used. A link to files of your own anywhere outside the directory is dropped in that
  copy, so an interpreter your program runs on must be one of the machine's own or copied into
  `/app/rebuild`; a link that points outside is replaced by a copy of what it points to only when
  that is part of the machine's installation (owned by root, as a virtual environment's link to
  the system Python is). Pipes, sockets and devices are dropped too. With those copies, keep it
  under 4 GB and 200,000 files, with no path inside it longer than 1,000 bytes, and leave the
  disk that much room to copy it; otherwise it is not copied.
- Where it will be used, it runs as an unprivileged user that cannot write to `/app/rebuild`.
  Each run starts in a new working directory, `/tmp/goose-case`, that holds only that run's
  files, with `HOME` and `TMPDIR` set to new empty directories and nothing left from earlier
  runs anywhere it can write. Its environment variables and resource limits are the ones
  `run_examples.py` gives each example (an 8 MB stack among them, which is also the stack the
  sandboxed build runs a program on).
- Each run finishes within 2 seconds, which is how long the playground and the editor plugin
  wait, uses at most 4 GB of memory, and writes at most 1 GB and 100,000 files; the sandboxed
  build takes a fraction of a second and far less of each on the programs people send.
- Out of scope: `goose build`, `goose fetch` and packages, `goose lsp`, `goose toolchain`,
  the options that report on a compile (`--stats`, `--specs`, `--stacks`, `--bce-lines`, `-v`),
  the options `goose help internals` lists and `goose format --verify` (their help text aside),
  threads, calling C (`extern` functions and `extern` blocks in a program's own files, sidecar
  `.build` files), and the `os`, `ffi`, `gfx`, `ui`, `audio` and `physics` modules.

## Completion

The work is complete when your program cannot be told apart from the sandboxed build by what it
prints on standard output and how it exits. Keep `/app/rebuild/goose` runnable at all times.
