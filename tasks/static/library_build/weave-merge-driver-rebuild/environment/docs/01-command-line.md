# 1. Command line, files and exit status

This chapter covers how our merge path calls `weave-driver` 0.7.1 and what it leaves behind.
Rules carry bracketed identifiers that later chapters cite.

## 1.1 Invocation

    weave-driver BASE OURS THEIRS -o OUT -l 7 -p PATH

- **[CLI-1]** `BASE`, `OURS` and `THEIRS` are paths of three files: the common ancestor, our side
  and their side. Only their contents matter; their names never appear in the output.
- **[CLI-2]** `-o OUT` names the file the driver creates or replaces.
- **[CLI-3]** `-l 7` selects standard conflict markers, seven characters wide (chapter 14).
- **[CLI-4]** `-p PATH` is the file's path in the repository: its extension decides how the file is
  read (section 1.3), and `PATH` appears in the hint of [BOX-7] and decides which files are test
  files ([ELEM-9]).
- **[CLI-5]** Every argument other than a flag (`-o`, `-l`, `-p`) and the value after `-o` or `-l` is
  positional, and the value after `-p` is appended to the positional arguments too. The first
  three positional arguments are BASE, OURS and THEIRS. `PATH` is the fifth positional argument if
  there is one, else the fourth, else the path of OURS; in the form above it is the value of `-p`.
  Flags may come in any order after the three paths. Standard error is diagnostic only: nothing on
  our merge path reads it.

## 1.2 Reading the inputs

- **[CLI-6]** Each input is read whole as UTF-8. An input that cannot be read, or that is not valid
  UTF-8, ends the run with status 2 and nothing is written to `OUT`. Fewer than three positional
  arguments, or `-o` with no value, also end with status 2; so does an `OUT` that cannot be
  written.
- **[CLI-7]** An input is binary when one of its first 8,192 bytes is NUL (0x00); a later NUL does
  not count. If any input is binary, the run ends with status 2 and nothing is written.

## 1.3 File types

- **[CLI-8]** Our merge path sends five types, by the extension of `PATH`: `.py` (Python), `.ts`
  (TypeScript), `.go` (Go), `.json` (JSON) and `.toml` (TOML). All five are read with the
  `sem-core` 0.29.0 extractor (chapter 3): Python, TypeScript and Go through its tree-sitter
  grammars, JSON and TOML through its own readers ([DATA-1]). JSON and TOML files are also checked
  as data (chapter 15).

## 1.4 What is written, and the exit status

| Status | Meaning | `OUT` |
| --- | --- | --- |
| 0 | the merge is clean ([CLI-9]) | the merged file |
| 1 | the merge holds at least one conflict | the merged file with conflict boxes (chapter 14), or an input that already carried markers ([ROUTE-2]) |
| 2 | no usable result ([CLI-6], [CLI-7]) | not written |

- **[CLI-9]** A result the driver composes is written as clean (status 0) only after it passes the
  checks of chapter 12, which says which results are checked ([GATE-1]) and what replaces one that
  fails (section 12.2).
- **[CLI-10]** When the status is 1, the written file gets the hint of [BOX-7].
