# Move our `dogwood` implementation to Dogwood 1.2.0

## Goal

Our AI agents call tools on our customers' behalf, and every one of those calls is authorized
against our policies, which are written in Dogwood, a policy language built on Cedar whose rules can
also look back over what an agent did before. Our policy authors, our CI and our review and
incident tools work through the command-line tool `dogwood`. They run our own clean-room
implementation of it, in `/app/dogwood-rebuild`, which was written to do what Dogwood 1.1.2's
`dogwood` does.

Dogwood 1.2.0 is out, and we are moving every policy, schema and trace we have to it. Its release
notes list breaking changes that reach us:
- requests, events and provider outputs must now match their declarations;
- some decisions change, with no error, for input that 1.1.2 also accepted;
- validation rejects policies that 1.1.2 let through;
- Dogwood now requires Cedar 4.14.0, which changes the Cedar that `dogwood lower` writes.

Bring the implementation in `/app/dogwood-rebuild` to 1.2.0. Once we switch, nothing of ours needs
1.1.2's behaviour any more.

The clean-room rule still holds. Our lawyers asked for an implementation we own outright, written
only from Dogwood's published documentation and from running its builds. So whoever works on it
never reads Dogwood's source code, and never disassembles, traces or dumps a build: learn what a
build does only from what it prints.

Everything that uses `dogwood` depends on what it prints:

- Every change to a policy goes through `dogwood validate --format json` in our CI. The exit status
  decides whether the change can merge, and the review page shows each finding's message at its
  byte span. Authors also run `dogwood check-parse` before they commit.
- Our replay job runs recorded agent traces through `dogwood replay` against the policies they
  were recorded under and keeps the verdict streams, plain and `--format json`. Our incident tools
  read them decision by decision: the verdict, the rules it lists, the errors of a decision that
  failed closed, and the events of the trace that were not taken into the history.
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

- The 1.2.0 build is now installed as `dogwood` on `PATH`. The 1.1.2 build stays installed as
  `dogwood-1.1.2` until we switch. Both are execute-only, so that nobody in the clean room reads
  their code: you can run them as often as you like, but not read, copy or inspect the files.
- Like the 1.1.2 build, the 1.2.0 build has arithmetic in comparison operands switched on: it is
  the `experimental-arithmetic` build that the guide describes.
- 1.2.0's documentation is in `/app/docs/1.2.0`:
  - The guide is in `guide/`. As before, we left out the chapters on Dogwood's Rust library and
    its MCP tooling, and the trace file format is in the command-line chapter.
  - `examples/` holds the guide's example bundles with what `dogwood explain` and
    `dogwood replay` printed for them.
  - `RELEASE_NOTES.md` has the 1.2.0 release notes and upgrade notes, without the items about the
    Rust library and the build.
  - When the guide and the build disagree, the build is right.
- 1.1.2's documentation is still in `/app/docs/1.1.2`.
- There is no network access. Rust is installed with `cargo` and an offline crate registry that
  `cargo` is already set up to use. The registry now also holds the Cedar crates at 4.14.0. No
  Dogwood crate is available. Keep the implementation in Rust.

## What to deliver

The implementation in `/app/dogwood-rebuild`, brought to 1.2.0: a Cargo project from which
`cargo build --release --offline` builds a binary named `dogwood`.

- All of 1.2.0's guide is in scope, apart from the list at the end of this section. That means:
  - the policy language and its Cedar part, event schemas, temporal conditions and aggregations;
  - macros and their standard library, and information providers;
  - lowering, validation, `explain` and `format`;
  - every command and option of the command line.

  Our policies use these features in every combination, with their corner cases and their
  errors.
- Given the same files, arguments and standard input, your `dogwood` prints the same standard
  output and ends with the same exit status as the 1.2.0 build, with `--format human` and with
  `--format json`. Nothing of ours reads standard error, so what it writes there may differ.
- In JSON output, the order of keys inside an object does not matter. The rules listed for a
  decision are a set to our incident tools, so their order does not matter either. Everything
  else does: the order of lists, every message, every span and every number.
- Our traces always have strictly increasing timestamps. What the build does with a trace whose
  timestamps repeat or go back does not matter to us.
- Our release machines build `/app/dogwood-rebuild` from a clean copy of the directory:
  - they use the same Rust toolchain and registry, without network access, on 4 cores and 8 GB of
    memory, and give the build 20 minutes;
  - the copy leaves out `target/` and any link that points outside the directory, and it may hold
    at most 100,000 files and directories and 1 GB;
  - everything the build and the tool need, apart from the toolchain and the registry, must be
    inside the directory.
- Your `dogwood` must not call either build. It replaces them, and will run where neither is
  installed.
- Our CI starts every `dogwood` the same way:
  - it runs as an unprivileged user that cannot write to the project directory;
  - each run gets a new, empty working directory holding only that run's files, with `HOME` and
    `TMPDIR` set to new empty directories;
  - the environment holds only `PATH=/usr/local/bin:/usr/bin:/bin`, `LANG` and `LC_ALL` set to
    `C.UTF-8`, `TERM=dumb`, `NO_COLOR=1`, `HOME` and `TMPDIR`;
  - standard input and output are pipes, and none of the standard streams is a terminal.
- Each run finishes within 5 seconds and uses at most 2 GB of memory; CI stops any `dogwood`
  still running then. The 1.2.0 build finishes each of our runs well within that.
- Out of scope, because nothing of ours uses it:
  - MCP schema generation (1.2.0's default build has no `schema mcp`, and neither does ours);
  - Dogwood's Rust library interface;
  - the `net` feature and its `http_get` host function.

  You need not make any of these work.

## Switching over

When your implementation does all of the above for 1.2.0, we point our CI, the replay job, the
policy store, the review page and the editors at it and retire both builds. Keep
`/app/dogwood-rebuild` building and runnable at all times.
