# 13. Rules that settle a conflict

## 13.1 When the rules run

- **[RULE-ENTRY]** Every result that is not clean, whatever wrote it (the entity merge, git's
  conflicted answer of the line route or of [GATE-4], the box of [GATE-5]), is offered to the rules,
  unless an input carries markers ([ROUTE-2]) or is binary, or one of its
  conflicts is of kind *modify/delete* or *two renames* ([CELL-17]). The rules read the inputs as
  given, without the encoding step of [LAY-5].
- **[RULE-NEVER]** A settled text is refused, leaving the conflicted result, when it fails a check
  of chapter 12 (order of [GATE-2], no rename substitution of [GATE-LINES-4]) or [GATE-IOTA], or
  when a declaration one side deleted was changed by the other beyond layout: reading the inputs
  with `ParserRegistry::extract_entities_with_tree` (entities without parent, kind `chunk`
  excepted), grouped by (kind, name) with sem-core's entity texts, some group has fewer entries on
  one side than in BASE while the other side has an entry neither equal nor token-equal to one of
  BASE's. Otherwise the text is clean, still subject to [GATE-12].
- **[RULE-LAYOUT]** Two texts are *layout-equal* when equal, or equal without a leading byte-order
  mark, or: for Python, TypeScript and Go, both parse without error
  and their trees list in preorder the same (node kind, text) pairs, a leaf giving its text split on
  whitespace and rejoined with single spaces (verbatim when the kind contains `string`, `char`,
  `template`, `heredoc` or `raw`), an inner node an empty text followed by each non-blank stretch of
  text before, between or after its children (so rejoined, or verbatim and non-empty for those
  kinds), and, for Python, every non-blank line has the same indentation; for JSON and TOML, both
  have the same *tokens*: a quoted string (`"`, `'` or backquote; `\` escapes a byte; ended by its
  quote or, for `"` and `'`, by a newline it includes) verbatim, a run of ASCII letters, digits,
  `_`, `$` and non-ASCII bytes, or another non-space byte alone. *Token-equal*: the same tokens and, for Python, the same indentation of each line relative to the
  first.

## 13.2 Whole-file rules

- **[RULE-D4]** BASE exactly empty (no bytes) and the sides layout-equal: the byte-wise smaller side.
- **[RULE-D6]** BASE not empty, one side layout-equal to BASE and the other not: the other.
- **[RULE-D1X]** BASE not empty, the sides layout-equal: the side that exactly carries the other,
  else the byte-wise smaller (OURS on a tie). Hunks are `diffy`'s zero-context patch from BASE
  (`DiffOptions::new().set_context_len(0).create_patch`), every line counting. Hunk X carries hunk Y
  when Y's BASE range lies within X's (two pure insertions: at one place), a Y that only deletes is
  matched only by an X that writes nothing, and Y's written lines occur in order among X's. A side
  exactly carries the other when both have hunks, each of the other's hunks is carried by one of its
  own, and not the other way round.
- **[RULE-DATA]** JSON and TOML: then [DATA-5].

## 13.3 Region rules

- **[RULE-REGIONS]** A non-empty input without a final `\n` gets one, and the three go through
  `git merge-file -p --diff3 -L ours -L base -L theirs` (temporary files; output read whatever the
  exit status). A region starts at a line of seven `<` alone or followed by a space; its OURS lines
  run to the like line of `|`, its BASE lines to `=`, its THEIRS lines to `>`. Other lines are
  stable; lines keep their `\n`. No region, or one left open, means no settling. A side *may be
  taken* unless its file fails to parse while the other's parses (files without a grammar always
  may). Each region takes the first answer of [RULE-D0] to [RULE-D6R]; none means no settling.
- **[RULE-D0]** The two sides' lines are equal: those lines.
- **[RULE-D1]** The sides that may be taken and carry the other's change: both, the byte-wise
  smaller (OURS on a tie); one, its lines. X carries Y when Y's change is not empty and, for each
  hunk of the zero-context patch from BASE's region to Y's (lines without trailing whitespace): no
  non-blank BASE line it removes survives in X under the alignment of BASE with X; no removed BASE
  line longer than 3 bytes trimmed and not among Y's written lines is stated by Y less often than by
  BASE while X states it as often; and its non-blank written lines are either none (then, if it
  removed a non-blank line, X has no non-blank line in the window) or all kept by the alignment of Y
  with X and present, trailing whitespace trimmed, as one consecutive run of the window's non-blank
  lines. An *alignment* maps the lines such a patch leaves unchanged; the *window* runs from one
  past the image of the last aligned BASE line before the hunk to the image of the first after it.
- **[RULE-D3]** *Import set union*. Every non-blank line of the region in all three is an import
  item, judged on the trimmed line cut at its first `//` (in Python also `#`): Python `import X` or
  `from M import N` (X, M of letters, digits, `_`, `.`, `*`, `,`, `=`, spaces; N without `(`, `)`,
  `\`); TypeScript `import ` with ` from ` or a quote next, ending (before `;`) in a quote, or
  `const`/`let`/`var` with `require(` ending in `)`; Go, a line whose last word, after an optional
  `import `, is a double-quoted string. An item with a name list (`from M import a, b` without `*`,
  `import {a, b} from …`) is keyed by the text around the list, others by the line. No version
  states a key twice; some side has an item. Per key: equal on both sides, OURS' line; one side as
  BASE, the other's; a name list both changed keeps BASE's names neither dropped, in order, then the
  added names sorted, once each, written as the model line's indentation, the text before the list,
  the names joined by `, ` (padded inside the braces if the model has `{ `), the text after it and
  the model's line ending, the model being BASE's line, else the byte-wise smaller new one; with no
  name left it is dropped; another item both changed means no union. A one-sided addition already
  among the stable lines is dropped. No name may be bound by two different import lines among items
  and stable lines (Python and TypeScript as [GATE-BIND]; Go: the alias of a two-word line, nothing
  for `_` or `.`; the last `/` segment of a one-word line). Output: BASE's lines in order, items
  replaced by their merged value; each addition after the nearest BASE item before it on its side
  (the earlier place if both added it); per place each side's additions form a run, the run whose
  lines joined sort first going first. A one-sided addition binding a name of a BASE item both sides
  removed is removed again at the end unless a non-import line of the answer contains that name as
  an identifier.
- **[RULE-DATA-UNION]** JSON and TOML: [DATA-6].
- **[RULE-D3C]** *Container insertion union* (Python, TypeScript; BASE not empty). Both sides kept
  every BASE line of the region in order, exactly or with a comma added, at the same indentation,
  and both inserted lines. Each inserted run, read in its side's whole file with every region as
  that side wrote it (which must parse, like BASE), must be whole elements, at most one per line, of
  the nearest container a recogniser knows (starting above the run, or a Python block or module, or
  a TypeScript program), and that container must be a set: a Python dict (keyed by a string constant
  without escapes or prefix other than `u`, as `s:` and its content, or a decimal integer, `i:` and
  its digits), set or `__all__` (elements keyed alike), or `from m import (…)` (name or alias); a
  TypeScript object (a property name, escape-free string or decimal number, as plain text, not
  `__proto__`; a shorthand property; a method not `get`, `set` or `static`), or export or import
  list (alias, else name). No side inserts a key twice or one the container holds elsewhere. Two
  runs at one point must sit in one container and leave the same lines after them; with no comment
  or blank line above any inserted element they merge by key (equal keys with equal text once, the
  smaller spelling; else the smaller key first), else whole, smaller keys then lines first; one key
  with two texts means no union. With commas, both runs' last elements must agree on having one;
  every element but the last then gets one, the last too if both had one; a line holding `#` in
  Python or `//` in TypeScript, or ending in `*/`, cannot take one. BASE lines take OURS' spelling
  if it has a trailing comma, else THEIRS'. The answer must parse, each container holding exactly
  the inserted keys at the inserted rows, none twice, none held by BASE's container of the same kind
  and enclosing names, which must exist.
- **[RULE-D6R]** Each region in context: the file with every other region as OURS wrote it. If OURS'
  context is layout-equal to BASE's and THEIRS' is not, THEIRS' lines (if THEIRS may be taken), and
  conversely. Otherwise, if the two sides' contexts are layout-equal: the side that exactly carries
  the other ([RULE-D1X], on the region texts) if it may be taken, else the byte-wise smaller (OURS
  on a tie).

## 13.4 The answer

- **[RULE-ANSWER]** Stable lines and region answers, in order; the certificates of [DATA-6] and
  [RULE-D3C] must hold where used. Whether it ends in `\n` is merged as one bit: BASE empty, two
  non-empty sides that disagree mean no settling, else no final `\n` if either side lacks one;
  otherwise OURS' bit if it differs from BASE's, else THEIRS'. Without, the final `\n` is removed.
