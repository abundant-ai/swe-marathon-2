# Follow the driver to release 0.7.1

## Goal

Our fleet has moved from `weave-driver` 0.6.2 to 0.7.1, and the merge driver you are writing in
`/app/driver` has to follow it. 0.7.0 changed how the driver keeps a file's layout: line endings, a
missing final newline, and definitions that share a line now come through a merge as they were
written. 0.7.1 changed nothing in the merge itself. Bring `/app/driver` up to 0.7.1. Everything
below is the full request as it now stands; it replaces the earlier one.

The tool stays a clean-room rewrite under our legal policy: work only from our written
specification, the release notes and running the installed build, and never read the driver's
source. Everything downstream depends on what the driver writes and how it exits:

- Our merge queue re-runs every merge on a clean machine before it lands a change, and stops the
  queue when a merged file differs by a single byte from the one the change was reviewed with, or
  when the exit status differs.
- Our landing agents land a file without review when the driver exits 0. Where the driver refuses
  to call a merge clean and writes a conflict instead, a clean exit would put code that no longer
  builds, or that silently changed meaning, on our main branch.
- Editors and our review tool find conflicts by their markers (`<<<<<<< ours`, `||||||| base`,
  `=======`, `>>>>>>> theirs`) and show the lines the driver writes around and inside them.

## Context

- `/usr/local/bin/weave-driver` is now the 0.7.1 build, execute-only as before: run it as often
  as you like, but do not read, copy, disassemble, trace or dump it.
- `/app/docs` holds our revised specification for 0.7.1, and `/app/docs/releases/` the
  maintainers' notes for 0.7.0 and 0.7.1, cut to what our setup uses. Where they and the installed
  build disagree, the build is right.
- Our merge configuration still calls it as `weave-driver BASE OURS THEIRS -o OUT -l 7 -p PATH`.
  The features our setup never uses are unchanged: the positional form and its annotated markers,
  the `weave-set` attribute, the `WEAVE_` variables, and the audit, findings and statistics files.
- The merge queue runs each merge in a scratch directory outside any repository, with `git` on
  `PATH`, no git configuration and none of the driver's variables set. The driver runs
  `git merge-file` for part of its work, and yours may do the same.
- 0.7.1 is built on `sem-core` 0.29.0, which the offline registry now holds next to 0.28.0, with
  `tree-sitter` 0.26, `diffy` 0.5.2, `serde_json`, `toml` and `tempfile`. No other crates are
  available, and there is no network access.

## What to deliver

`/app/driver`, a Rust project that `cargo build --release --offline` builds into
`/app/driver/target/release/weave-driver`, using only the toolchain and crates above.

- Called as above on a `.py`, `.ts`, `.go`, `.json` or `.toml` file, it writes `OUT` byte for byte
  as the installed 0.7.1 build writes it, and exits with the same status: 0 for a clean merge, 1
  for a merge written with conflict boxes, 2 when there is no usable result (an input that cannot
  be read, is not UTF-8 or is binary), in which case it writes nothing. Standard error may differ.
- That covers everything the revised specification describes for those file types. A part that
  works on simple merges is a start, not the end: our merges combine all of it.
- Inputs are files of up to 2 MB; each merge must finish within 10 seconds on one CPU core with
  2 GB of memory.
- It must not call the installed build.
- We will maintain this code for years: keep it modular, with the merge rules in focused
  functions, kept apart from reading and writing files, the command line, and the calls to `git`.

## Switching over

When your driver does all of the above, we point our merge configuration at
`/app/driver/target/release/weave-driver` and remove the installed build. Keep `/app/driver`
building at all times.
