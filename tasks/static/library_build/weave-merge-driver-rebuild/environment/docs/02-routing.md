# 2. Routing before the entity merge

Before any definition is matched, the driver takes the first of these routes that applies. The
entity merge (chapters 3-11) runs only when none of [ROUTE-1] to [ROUTE-6] applies.

- **[ROUTE-1] Identical sides.** If OURS and THEIRS are byte-identical, the result is that text,
  clean (status 0), even when they carry conflict markers.
- **[ROUTE-2] Markers in an input.** An input carries markers when its text contains both
  `<<<<<<<` and `>>>>>>>`, anywhere (not only at the start of a line). If any input carries
  markers, the driver does not merge: it writes OURS if OURS carries markers, else THEIRS if THEIRS
  does, else BASE, and exits 1.
- **[ROUTE-3] One side unchanged.** If BASE equals OURS, the result is THEIRS; if BASE equals
  THEIRS, OURS; both clean, unchecked.
- **[ROUTE-4] One side already holds both edits.** If one side holds the other's edits
  (section 2.1), its file is the result, clean.
- **[ROUTE-5] Large files.** No such route; every input is at most 100,000 bytes ([OUT-8]).
- **[ROUTE-6] Files the entity model does not describe.** These checks see the three texts after
  the normalisation of [LAY-5] and are made in this order. (a) No grammar: only `sem-core`'s
  fallback reader handles the path; the line route is taken. (b) Both sides created the file: BASE
  is empty or only whitespace, and OURS and THEIRS are not; the line route is taken. (c) No
  definitions: the extractor finds no top-level definition in BASE although BASE is not blank, or
  finds none in OURS and none in THEIRS although neither is blank; the file is merged by section
  2.3. A blank side next to a side without definitions does not count: such a file goes on to the
  entity merge. (d) Too many equal names ([ENT-8]); the line route is taken.

## 2.1 The superset side

- **[ROUTE-7]** Each text is first reduced to key lines: every line loses its trailing whitespace
  and then, in `.json` files only, one trailing `,`; lines left empty are dropped. A side's change
  is the list of hunks of the `diffy` 0.5.2 patch from BASE's key lines to its own, made with a
  context length of 0 (`DiffOptions::new().set_context_len(0).create_patch`); each hunk replaces a
  range of BASE lines (possibly none) with the lines it inserts (possibly none). A hunk *h* of side
  Y is carried by a hunk *g* of side X when: if either of them replaces BASE lines, *g*'s range
  contains *h*'s, and if both only insert, they insert at the same point; if *h* deletes BASE lines
  and inserts nothing, *g* inserts nothing either; and *h*'s inserted lines appear, in order, among
  *g*'s (not necessarily together). A hunk *h* of Y is a move when one of the BASE lines it
  replaces, trimmed at both ends, is longer than 3 bytes, is not among the lines *h* inserts, and is
  stated fewer times in Y than in BASE but at least as often in X as in BASE (lines counted trimmed,
  over key lines). X holds Y's edits when every hunk of Y is carried by some hunk of X and no hunk
  of Y is a move. The rule does not apply when OURS and THEIRS disagree on whether they contain
  `\r\n`, when either side has no hunk, or when each side holds the other's edits.
- **[ROUTE-8]** The superset side X is taken only if (a) X parses whenever the other side Y parses
  (files with a syntax tree only), and (b) no top-level definition, counted by its kind and name,
  is stated fewer times in Y than in BASE while X still states it at least as often as BASE.
  Definitions of the kind `chunk` are not counted. When BASE is empty or only whitespace, X is also
  refused when one hunk of the zero-context `diffy` patch from Y's text to X's text inserts lines
  whose significant lines (section 12.4; compared trimmed, with trailing commas removed), at least 3
  of them, appear contiguously and in the same order among Y's significant lines. For JSON and
  TOML, X must also pass the data checks of section 12.5 against OURS and THEIRS; if it does not,
  it goes through chapter 12 like any composition.

## 2.2 The line route

- **[ROUTE-9]** The line route is git's own merge: `git merge-file -p --diff3 -L ours -L base -L theirs`
  over the three texts (written to temporary files and passed as OURS, BASE, THEIRS), with the
  `git` on our merge path and no `--marker-size`. Exit status 0 means clean; any other status, an
  error included, means a conflict, and git's standard output (invalid UTF-8 replaced by U+FFFD) is
  the text. For the files of [ROUTE-6], git's answer is then treated like any composition: a clean
  answer goes through chapter 12, and a conflicted one through chapter 13.

## 2.3 Files without definitions

- **[ROUTE-10]** A file with no definitions is merged by the line route first. If git conflicts,
  the element union is tried on the whole file in its disjoint form ([ELEM-14]); without a union,
  git's conflict stands, and the rules of chapter 13 may still settle it.
