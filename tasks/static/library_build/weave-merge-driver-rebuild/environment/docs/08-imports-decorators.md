# 8. Gaps, imports and decorators

## 8.1 Merging a gap

- **[IMP-1] Gaps across versions.** Gaps ([ENT-7]) are matched by identity (header, footer, the
  single piece of a version without definitions, or the sem-core ids of the two definitions a gap
  separates); a version without that gap contributes an empty text. If OURS equals THEIRS, OURS' text is the gap; else if
  BASE equals OURS, THEIRS'; else if BASE equals THEIRS, OURS'; else [IMP-2].
- **[IMP-2] Both changed.** Candidates, in order: (1) if both sides changed only whitespace (the test
  of [SAME-3], for every file type), THEIRS' text; (2) otherwise, if one of the three texts is an
  import region ([IMP-3]), the import union ([IMP-5], [IMP-6]) when it reports no order conflict and
  is licensed ([IMP-7]); (3) unless the union reported an order conflict, the clean `diffy::merge`,
  then the disjoint-form element union ([ELEM-14]); (4) if exactly one side changed only
  whitespace, the other side's text. The first that loses no line ([SAME-4]) and keeps every added
  line (each non-blank line of OURS or THEIRS whose trimmed text no BASE line has occurs, trimmed,
  in it) is the gap; without one, the gap is a box over its three texts, kind *both modified*.

## 8.2 The import union

- **[IMP-3] Import lines.** An *import line* does not start with a space or tab and, trimmed, starts
  with `import `, `from `, `use `, `require(`, `package `, `#include ` or `using `, or starts with
  `const ` and contains `require(`. A *multi-line import* opens on an import line containing `{` but
  no `}`, or starting with `import (` without `)`, or starting with `from ` with `import (` and no
  `)`; it ends at the next line that, trimmed, starts with `}` (opener with `{`) or `)`. A text is an
  *import region* when import lines, plus the lines after a multi-line opener up to and including
  the first starting with `}` or ending with `)`, are more than half of its non-blank lines.
- **[IMP-4] Order-preserving union** of a leading sequence A and a sequence B: until both are used,
  skip a head already written; if A is used up write B's head, if B is, A's; equal heads: write it,
  advance both; else write A's head if B lacks it, else B's head if A lacks it, else A's head, noting
  an *order conflict*.
- **[IMP-5] Single-line imports** (no version has a multi-line import).
  1. Each version's import lines, as written, in order; a BASE import line OURS or THEIRS lacks is
     removed from both sides' lists. A side *reordered* when its remaining BASE lines are out of
     BASE's order. THEIRS leads if only THEIRS reordered, else OURS; the lines are the union [IMP-4]
     of the leader's with the other's, an order conflict counting only if both reordered.
  2. Groups are the leader's: a blank line after an import line starts a new one. A line the leader
     has keeps its group; another takes that of the nearest leader line before it, else after it,
     else the last group, but between leader lines of two groups it takes the later group only if
     it shares more leading module-path segments with that line than with the earlier one. A line's
     *module path*: the word after `from `; for a line starting `}` with `from `, or starting `import `
     with a quote, the text inside the first quotes; else after `import ` the next word less `;` if
     it holds a `.`; after `use `, the text before `::` less `;`; else the trimmed line. Segments
     split the path, trimmed of `.` and `/`, at `.`, `/` and `:`.
  3. The block: the lines joined by `\n`, an empty line where the group changes, but after a
     `package ` line followed by another line, `p` empty lines instead. A *width* of three counts is
     THEIRS' if OURS' equals BASE's, OURS' if THEIRS' does, else the larger; `p` is the width of the
     blank lines after the first `package ` line.
  4. The text: `\n` repeated for the width of the blank lines opening each text; then, if a version
     has a *prefix* (its lines before the first import line, or all of them without one, blank ends
     removed, joined by `\n`) that is not empty, the `diffy::merge` of the prefixes (its conflicted
     text on conflict) and, unless blank, `\n` and as many more as the largest count of blank lines
     just above a version's first import line; then the block; then, if a version has a *suffix*
     (lines after its last import line, read alike), their `diffy::merge` and, unless blank, `\n`, as
     many more as the width of the blank lines after the last import line, and the merge. Last, `\n`s
     are added until it ends in as many as OURS' gap.
- **[IMP-6] Multi-line imports.** Each version is read as statements: a multi-line import or one import
  line. *Names*: a multi-line statement's inner non-blank lines, trimmed, without trailing commas;
  one line's comma-separated parts after ` import `, trimmed, less a trailing `;` (none if they
  start with `*` or `(`), else those between `{` and `}` of an `import ` line, trimmed. *Source*:
  the module path of its first line that has one, else its whole text trimmed.
  1. If a side has no statement with a source BASE has while the other side has it with names
     differing from BASE's for it, the union reports an order conflict.
  2. OURS' text is walked by lines. Blank and non-import lines are copied. A multi-line statement
     becomes its first line, `INDENT NAME,` per name (INDENT: its second line's leading whitespace,
     5 spaces without one), and its last line; its names are OURS' less those BASE has and THEIRS
     lacks for that source, then THEIRS' names BASE lacks, in THEIRS' order, once each. A one-line
     statement whose source THEIRS has with names BASE lacks, and with non-empty comma-separated
     parts after its first ` import ` (trimmed, less a trailing `;`), takes those parts, then
     THEIRS' new names not among them: in THEIRS' layout, as above (4 spaces without a second
     line), if THEIRS' first statement of that source is multi-line, else as the trimmed line up
     to and including ` import ` and the names joined by `, `. Another import line is copied
     unless BASE has it as a one-line statement and THEIRS not.
  3. THEIRS' statements whose source OURS has nowhere are appended; the lines are joined by `\n`.
  4. Each version's *other* lines (non-blank, not import lines, not ending in `,` without `=`, not
     `)` or `}`, not starting with `)`, nor with `}` when containing `from `), joined by `\n`, go
     through `diffy::merge` (conflicted text on conflict); unless blank, `\n\n` and it are appended.
     Trailing `\n`s are completed as in [IMP-5].
- **[IMP-7] Licence.** The union is a candidate only if the three texts have the same non-import lines
  (outside [IMP-6] statements, trimmed, non-blank, sorted) and it binds no name, nor states
  `package`, more often than the more of OURS' and THEIRS' gaps does, counted as [GATE-BIND] counts
  imports and `package` clauses.
- **[IMP-8] Imports kept for new uses.** For each side as *deleter*, the other as *keeper*: the
  keeper's new lines are those whose trimmed text no BASE line has. A BASE line, trimmed, the
  deleter lacks and the keeper has is kept if, read as one Python or TypeScript import line as
  [GATE-BIND] reads it (indentation ignored; a Go line binds nothing), it binds a name the keeper's
  new lines use as a value and the deleter's whole text neither imports nor declares. A *value use*:
  the name not after an identifier character, `.` or `$`, followed by `(` (spaces allowed), `<`, or
  `.` but not `..`, after an even number of quotes on its line, on a line that is not a comment,
  decorator, import or definition line ([BIND-1]) of it. A *declaration*: a definition line, or
  `const`, `let` or `var` after modifiers, then the name or a `{`/`[` pattern naming it. Every gap not boxed regains each kept line its BASE text has and it lacks
  (trimmed comparison), in BASE's spelling, after the first gap line matching (trimmed) the nearest
  earlier non-blank BASE line it has, else before the nearest later one, else at the top, and is
  rejoined with `\n`, ending in `\n` if it did or was empty.

## 8.3 Decorators

- **[DEC-1] Decorator merge.** A text's *decorators* are the non-blank lines of its leading run of
  blank lines and lines that, trimmed, start with `@` (not `@param`, `@return`, `@type`, `@see`); the
  run's trailing blank lines belong to the *body*, the rest. No decorator on OURS or THEIRS: no
  answer. When `PATH`, lower-cased, ends in `.py` or `.ts` and both sides added decorators BASE
  lacks (exact lines), OURS adding one THEIRS did not means no answer. Bodies: all equal, BASE's;
  one side as BASE, the other's; else the clean `diffy::merge`, or no answer. The answer: BASE's
  decorators less any a side removed, OURS' new ones, THEIRS' new ones, each once and followed by
  `\n`, then the body.
