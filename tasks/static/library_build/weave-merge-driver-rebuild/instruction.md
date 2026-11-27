# Replace the merge driver on our merge path

## Goal

Our repositories merge Python, TypeScript and Go source files and JSON and TOML configuration
through `weave-driver` 0.7.1, an entity-level merge driver. Git hands it the base, ours and theirs
versions of a file; it merges functions, classes, keys and imports rather than lines, writes the
merged file, with conflict boxes where it could not merge, and reports which by its exit status.

We are moving every tool on our merge path to code that our own team maintains. For a tool we
will keep for years, our legal policy is a clean-room rewrite: the people who write it work only
from our written specification and from running the installed build, and never read the driver's
source. Write that implementation. It takes over from the installed build everywhere we merge,
and three things downstream depend on what it writes and how it exits:

- Our merge queue re-runs every merge on a clean machine before it lands a change. The changes in
  flight were reviewed with the files the installed driver wrote, so the queue stops whenever a
  re-run merge comes out a single byte different from the reviewed file, or exits differently.
- Our landing agents land a file without review when the driver exits 0. The installed driver
  refuses to call a merge clean when it cannot justify the result, and writes a conflict instead;
  a clean exit where it refuses would put code that no longer builds, or that silently changed
  meaning, on our main branch.
- Editors and our review tool find conflicts by their markers (`<<<<<<< ours`, `||||||| base`,
  `=======`, `>>>>>>> theirs`) and show the lines the driver writes around and inside them,
  including the hint it adds to a closing marker.

## Context

- The installed build is `/usr/local/bin/weave-driver`. It is execute-only, so that nobody in the
  clean room reads its code: you can run it as often as you like, but not read, copy or inspect
  the file. The clean-room rules cover the build too: do not disassemble, trace or dump it; learn
  what it does only from what it writes and how it exits.
- `/app/docs` holds our specification of the driver in sixteen chapters, written by our tooling
  team from its behaviour. Where the specification and the installed build disagree, the
  installed build is what our reviewed merges were made with.
- Our merge configuration calls it as `weave-driver BASE OURS THEIRS -o OUT -l 7 -p PATH`: the
  three versions as files, `OUT` the file to write, `-l 7` for standard conflict markers, and
  `PATH` the file's path in the repository, which decides how the file is read.
- The driver has features our setup never uses: the positional form git uses by default and the
  annotated conflict markers it writes in that form, the `weave-set` attribute, the `WEAVE_`
  environment variables, and the audit, findings and statistics files. The replacement does not
  need them, and it does not need to handle files of other types or files larger than 100 KB.
- The merge queue runs each merge in a scratch directory outside any repository, with `git` (the
  version installed here) on `PATH`, no git configuration (no user or system file) and none of
  the driver's environment variables set. The installed driver runs `git merge-file` for part of
  its work, and yours may do the same.
- The clean room has no network access. Rust (`rustc` and `cargo`) is installed with an offline
  registry that holds the crates the driver itself is built on: `sem-core` 0.29.0 (the entity
  extractor, with its Python, TypeScript and Go grammars), `tree-sitter` 0.26, `diffy` 0.5.2 (the
  in-process line merge), `serde_json`, `serde_yaml`, `toml` and `tempfile`, with their
  dependencies. No other crates are available. Python 3 is installed for your own scripts.

## What to deliver

A Rust project in `/app/driver`. Running `cargo build --release --offline` in that directory
builds the executable `/app/driver/target/release/weave-driver`, using only the toolchain and
crates above.

- Called as above on a `.py`, `.ts`, `.go`, `.json` or `.toml` file, it writes `OUT` and exits 0
  for a clean merge, 1 for a merge written with conflict boxes, and 2 when there is no usable
  result (an input that cannot be read, is not UTF-8 or is binary), in which case it writes
  nothing. The merge queue, the landing agents and the editors above all read what it writes and
  how it exits. Nothing of ours reads standard error, so its messages are up to you.
- The specification describes everything it does for those file types: how definitions are
  paired across the three versions, renames, where added definitions go, edits by both sides to
  one definition, classes and their members, collections inside one definition, imports and
  decorators, the merges the driver refuses and what it writes instead, the rules that settle
  conflicts, the conflict boxes and the hint on their closing marker, the layout of the file
  (blank lines, line endings, byte-order marks and final newlines), and JSON and TOML. A part
  that works on simple merges is a start, not the end: our merges combine all of these.
- Each merge must finish within 10 seconds and 4 GB of memory.
- It must not call the installed build: it replaces it, and it will run where that build is not
  installed.
- We will maintain this code for years: keep it modular, with the merge rules in focused
  functions, kept apart from reading and writing files, the command line, and the calls to `git`.

## Switching over

When your driver does all of the above, we point our merge configuration at
`/app/driver/target/release/weave-driver` and remove the installed build. Keep `/app/driver`
building at all times.
