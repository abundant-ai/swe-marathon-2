# Reimplement the `dogwood` policy tool

## Goal

Our AI agents call tools on our customers' behalf, and every one of those calls is authorized
against our policies, which are written in Dogwood. Dogwood is a policy language built on Cedar
whose rules can also look back over what an agent did before: an approval within the last hour, a
running total over a day, a login since the last logout. Our policy authors, our CI and our review
and incident tools all work through Dogwood's command-line tool, `dogwood`, and today we run the
1.1.2 build of it.

Dogwood's own interpreter is published to explain the language, not to run in production, and we
want an implementation we own outright and can change and license as we choose. Our lawyers have
asked for it to be written clean-room: the people who write it work only from the published guide
and from running the 1.1.2 build, and never read Dogwood's source code. Write that implementation.
It takes over from the 1.1.2 build everywhere we use `dogwood`, and everything that uses it depends
on what it prints:

- Every change to a policy goes through `dogwood validate --format json` in our CI. The exit status
  decides whether the change can merge, and the review page shows each finding's message at its
  byte span. Authors also run `dogwood check-parse` before they commit.
- Our replay job runs recorded agent traces through `dogwood replay` against the policies they
  were recorded under and keeps the verdict streams, plain and `--format json`. Our incident tools
  read them decision by decision: the verdict, the rules it lists and the errors of a decision
  that failed closed.
- Our policy store takes what `dogwood lower` emits as it is: the Cedar policies, the augmented
  schema and its Cedar JSON form. It files each version by checksum, so a lowered policy or schema
  that differs by one byte is a new version to it.
- Reviewers read `dogwood explain` next to every policy change, and the review page uses its
  `--format json` phrase tree to link each phrase to its place in the policy. Our editors run
  `dogwood format` when a policy is saved.
- Our schema repository checks every file with `dogwood schema action`, `schema event` and
  `schema providers`.

A different output, report or exit status breaks one of them.

## Context

- The 1.1.2 build is installed as `dogwood` on `PATH`, execute-only, so that nobody in the clean
  room reads its code: you can run it as often as you like, but not read, copy or inspect the
  file. The clean-room rules cover the build too: do not disassemble, trace or dump it; learn what
  it does only from what it prints.
- The build has arithmetic in comparison operands switched on: it is the `experimental-arithmetic`
  build that the guide describes.
- Its documentation is in `/app/docs/1.1.2`. The guide is in `guide/`. We left out the chapters on
  Dogwood's Rust library and its MCP tooling, and moved the trace file format, which upstream
  describes in the library chapter, into the command-line chapter. `examples/` holds the guide's
  example bundles: each has its policy and schemas, what `dogwood explain` printed for it, and,
  where it has a trace, what `dogwood replay` printed. When the guide and the build disagree, the
  build is right.
- There is no network access. Rust is installed with `cargo` and an offline crate registry that
  `cargo` is already set up to use. The registry holds the Cedar crates at 4.11.0, the Cedar
  release that 1.1.2 uses, and the other libraries our team has approved. No Dogwood crate is
  available. We maintain this tool in Rust next to the rest of our authorization code, so write it
  in Rust.

## What to deliver

Your implementation in `/app/dogwood-rebuild`: a Cargo project from which
`cargo build --release --offline` builds a binary named `dogwood`.

- All of the guide is in scope, apart from the list at the end of this section. That means the
  policy language and its Cedar part, event schemas, temporal conditions, aggregations, macros and
  their standard library, information providers, lowering, validation, `explain`, `format` and
  every command and option of the command line. A version that handles the guide's own examples
  is a start, not the end: our policies use these features in every combination, with their
  corner cases and their errors.
- Given the same files, arguments and standard input, your `dogwood` prints the same standard
  output and ends with the same exit status as the 1.1.2 build, with `--format human` and with
  `--format json`. Nothing of ours reads standard error, so what it writes there may differ.
- In JSON output, the order of keys inside an object does not matter. The rules listed for a
  decision are a set to our incident tools, so their order does not matter either. Everything
  else does: the order of lists, every message, every span and every number.
- Our traces always have strictly increasing timestamps. What the build does with a trace whose
  timestamps repeat or go back does not matter to us.
- Our release machines build `/app/dogwood-rebuild` from a clean copy of the directory with the
  same Rust toolchain and registry, without network access, on 4 cores and 8 GB of memory, and
  give the build 20 minutes. The copy leaves out `target/` and any link that points outside the
  directory, and it may hold at most 100,000 files and directories and 1 GB. Everything the build
  and the tool need, apart from the toolchain and the registry, must be inside the directory.
- Your `dogwood` must not call the 1.1.2 build. It replaces it, and will run where that build is
  not installed.
- Our CI starts every `dogwood` the same way. It runs as an unprivileged user that cannot write to
  the project directory. Each run gets a new, empty working directory holding only that run's
  files, and `HOME` and `TMPDIR` set to new empty directories. The environment holds only
  `PATH=/usr/local/bin:/usr/bin:/bin`, `LANG` and `LC_ALL` set to `C.UTF-8`, `TERM=dumb`,
  `NO_COLOR=1`, `HOME` and `TMPDIR`. Standard input and output are pipes, and none of the standard
  streams is a terminal.
- Each run finishes within 5 seconds and uses at most 2 GB of memory; CI stops any `dogwood`
  still running then. The 1.1.2 build finishes each of our runs well within that.
- Out of scope, because nothing of ours uses it:
  - `dogwood schema mcp` and MCP schema generation;
  - Dogwood's Rust library interface;
  - the `net` feature and its `http_get` host function, which our build does not have.

  You need not make any of these work.

Dogwood is young and still changing, and we will move to its newer releases as they come out, so
build it so that it is easy to change.

## Switching over

When your implementation does all of the above, we point our CI, the replay job, the policy store,
the review page and the editors at it and retire the 1.1.2 build. Keep `/app/dogwood-rebuild`
building and runnable at all times.
