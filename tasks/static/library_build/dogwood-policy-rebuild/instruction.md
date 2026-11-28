# Reimplement the `dogwood` policy tool

## Goal

Our AI agents call tools on our customers' behalf, and every one of those calls is authorized
against our policies, which are written in Dogwood. Dogwood is a policy language built on Cedar
whose rules can also look back over what an agent did before: an approval within the last hour, a
running total over a day, no logout since the last login. Our policy authors, our CI and our review
and incident tools all work through Dogwood's command-line tool, `dogwood`, and we run the 1.2.0
build of it.

Dogwood's own interpreter is published to explain the language, not to run in production, and our
security review lets only code we wrote ourselves into the path that authorizes our agents' calls.
Our security reviewers have also asked for it to be written clean-room, so that we can show where
every line came from: the people who write it work only from the published guide and from running
the 1.2.0 build, and never read Dogwood's source code. Write that implementation. It takes over
from the 1.2.0 build everywhere we use `dogwood`, and everything that uses it depends on what it
prints:

- Every change to a policy goes through `dogwood validate --format json` in our CI. The exit status
  decides whether the change can merge, and the review page shows each finding's message at its
  byte span. Authors also run `dogwood check-parse` before they commit.
- Our replay job runs recorded agent traces through `dogwood replay` against the policies they
  were recorded under and keeps the decision streams, plain and `--format json`. Our incident
  tools read them decision by decision: ALLOW or DENY, the rules listed for it, the errors of a
  decision that failed closed, and the events of the trace that were not taken into the history.
- Our policy store takes what `dogwood lower` emits as it is: the Cedar policies, the augmented
  schema and its Cedar JSON form. It files each version by checksum, so a lowered policy or schema
  that differs by one byte is a new version to it.
- Reviewers read `dogwood explain` next to every policy change, and the review page uses its
  `--format json` phrase tree to link each phrase to its place in the policy. Our editors run
  `dogwood format` when a policy is saved.
- Our schema repository checks every file with `dogwood schema action`, `schema event` and
  `schema providers`.

## Context

- The 1.2.0 build is installed as `dogwood` on `PATH`, execute-only, because the same rule covers
  it: you can run it as often as you like, but not read, copy or inspect the file, and you must not
  disassemble, trace or dump it. Learn what it does only from what it prints.
- The build has arithmetic in comparison operands switched on: it is the `experimental-arithmetic`
  build that the guide describes.
- Its documentation is in `/app/docs`:
  - The guide is in `guide/`. We left out the chapters on Dogwood's Rust library and its MCP
    tooling, and moved the trace file format, which the library chapter described, into the
    command-line chapter.
  - `examples/` holds the guide's example bundles: each has its policy and schemas, what
    `dogwood explain` printed for it, and, where it has a trace, what `dogwood replay` printed.
  - If the guide and the build differ, follow the build: it is what our tools run today.
- There is no network access. Rust is installed with `cargo` and an offline crate registry that
  `cargo` is already set up to use. The registry holds the Cedar crates at 4.14.0, the Cedar
  release that 1.2.0 uses, and the other libraries our team has approved. No Dogwood crate is
  available. We maintain this tool in Rust next to the rest of our authorization code, so write it
  in Rust. Python 3 is installed as well, for any scripts of your own.

## What to deliver

Your implementation in `/app/dogwood-rebuild`: a Cargo project from which
`cargo build --release --offline` builds a binary named `dogwood`.

- All of the guide is in scope, apart from the list at the end of this section. That means:
  - the policy language and its Cedar part, event schemas, temporal conditions and aggregations;
  - macros and their standard library, and information providers;
  - lowering, validation, `explain` and `format`;
  - every command and option of the command line.

  A version that handles the guide's own examples is a start, not the end: our policies use these
  features in every combination, with their corner cases and their errors.
- Our tools read standard output, with `--format human` and with `--format json`, and the exit
  status. Nothing of ours reads standard error, so what yours writes there is up to you.
- In `--format json` output, layout and the order of keys inside an object do not matter. The
  rules listed for a decision are a set to our incident tools, so their order does not matter
  either. Everything else reaches our tools as it is printed: the order of lists, every field name,
  every message, every span and every number. The Cedar texts `lower` emits, its Cedar JSON form
  included, are filed byte for byte.
- Our traces always have strictly increasing timestamps. What the build does with a trace whose
  timestamps repeat or go back does not matter to us.
- When you finish, anything you left running is stopped, and a copy of `/app/dogwood-rebuild` goes
  to our release machines, which build it:
  - the copy takes ordinary files and directories, and a link to a file inside the directory as
    that file. It leaves out `target/` and any other directory of cargo's build output, links to
    directories, links that lead out of the directory or nowhere, pipes, sockets and devices,
    names that are not UTF-8, and anything nested more than 32 directories deep or with a path in
    the directory longer than 1,000 bytes. What it takes may hold at most 100,000 files and 1 GB;
    nothing of a larger project is copied;
  - the release machines use the same Rust toolchain and registry, without network access, on 4
    cores and 8 GB of memory, and give the build 20 minutes;
  - everything the build needs, apart from the toolchain and the registry, must be inside the
    directory. The built `dogwood` is then installed on its own, so it must not read anything from
    the project when it runs: build what it needs into it.
- Your `dogwood` must not call the 1.2.0 build. It replaces it, and will run where that build is
  not installed.
- Our CI starts every `dogwood` the same way:
  - it runs as an unprivileged user, in a new, empty working directory holding only the files its
    command line names, with `HOME` and `TMPDIR` set to new empty directories;
  - the environment holds only `PATH=/usr/local/bin:/usr/bin:/bin`, `LANG` and `LC_ALL` set to
    `C.UTF-8`, `TERM=dumb`, `NO_COLOR=1`, `HOME` and `TMPDIR`;
  - standard input holds what a command reads from `-` and is empty otherwise, standard output is
    a pipe, and none of the standard streams is a terminal;
  - runs share nothing: whatever one run leaves is gone before the next starts.
- Each run finishes within 1 second and uses at most 2 GB of memory; CI stops any `dogwood` still
  running then. The 1.2.0 build finishes each of our runs well within that.
- Out of scope, because nothing of ours uses it:
  - MCP schema generation (the 1.2.0 build has no `schema mcp`, and neither does ours);
  - Dogwood's Rust library interface;
  - the `net` feature and its `http_get` host function, which our build does not have.

  You need not make any of these work.

## Switching over

When your implementation does all of the above, we point our CI, the replay job, the policy store,
the review page and the editors at it and retire the 1.2.0 build. Keep `/app/dogwood-rebuild`
building and runnable at all times.
