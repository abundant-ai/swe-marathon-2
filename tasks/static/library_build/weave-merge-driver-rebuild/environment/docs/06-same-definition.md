# 6. Edits by both sides to one definition

## 6.1 The ladder

- **[SAME-1]** A definition both sides changed differently ([CELL-5], [CELL-15]) is merged from its
  three texts by the first of these rungs that answers, keeping OURS' name: [SAME-2]; [SAME-3];
  [DEC-1]; for containers, [SAME-5] to [SAME-8]; the element union (chapter 7); the statement fold,
  [SAME-9] to [SAME-11]; else one box over the three texts, kind *both modified* (chapter 14).
- **[SAME-2] Text merge.** `diffy::merge(base, ours, theirs)` (diffy 0.5.2, default options); a clean
  answer is the result.
- **[SAME-3] Whitespace shortcut.** Not when `PATH`, lower-cased, ends in `.py`. Two texts differ only
  in whitespace when their trimmed non-blank lines are equal. If OURS differs from BASE only in
  whitespace, THEIRS' text is the result; else, if THEIRS does, OURS'.
- **[SAME-4] No loss.** A text *loses a line* when a non-blank line of BASE (trailing whitespace
  removed, indentation kept), stated `n` times in BASE, `o` in OURS and `t` in THEIRS, occurs fewer
  than `min(n,o) + min(n,t) - n` times in it.

## 6.2 Containers

- **[SAME-5] Cutting.** Definitions of kind `class`, `interface`, `enum`, `module`, `variable` or
  `export` merge member by member when all three
  texts, of two lines or more, can be cut. If a line, trimmed, starts with `class `, `def ` or
  `async def ` and ends with `:`, and the first such line has no `{`, the *header* is every line
  through the first whose trimmed text ends with `:`, with no footer; otherwise the header runs
  through the first line containing `{` and the *footer* starts at the last line that, trimmed, is
  `}` followed only by `)`, `]`, `;`, `,`, spaces or tabs (either missing, or a header ending after
  the footer starts: no cut). The body lies between. Its members are the children sem-core reports
  for the definition (entities naming it as parent, by first line) when all lie inside the body,
  each after the previous; otherwise each non-blank body line at the column of the first, not
  starting with `//`, `/*`, `*`, `#`, `@` or `}` and not `,`, starts a member running to the next
  start, less trailing blank lines and lines starting with `@`, `#[`, `//`, `/*`, `* ` or being `*`
  or `*/`; such lines directly above a member, below the previous one, are its own. No member: no
  cut.
- **[SAME-6] Members.** A member's identity is its name and its ordinal among same-named members. A
  child has sem-core's name. An indentation member is named from its first line: after `func (`,
  the run of letters, digits and `_` before the next `(` past the receiver's `)`; else the run
  before the first `(`; else, removing a leading `export `, `public `, `private `, `protected `,
  `static `, `abstract `, `async `, `override `, `readonly `, `pub `, `pub(crate) `, `fn `, `def `,
  `get `, `set ` (each tried once, in this order), then `fn `, the leading run; else its first 20
  characters. A member named `{` or `{}` takes the first non-empty text after a `:` on its later
  lines (each line trimmed, trailing commas removed; the text trimmed, then stripped of `"`s, then
  of `'`s, at both ends). Text between members is the *lead* of the next; the first lead is the
  *prelude*; text after the last is the *tail*. Every line of every piece ends in `\n`.
- **[SAME-7] Order.** Survivors (BASE members a side still has) take THEIRS' order if only THEIRS
  reordered them ([PLACE-1]), OURS' if only OURS did, else BASE's, united with BASE's survivor order
  by [IMP-4], the chosen order leading. Additions are taken from OURS, then THEIRS, each once (a
  member both added is anchored by OURS), each right after the nearest survivor before it on its
  side, written or not, or before all survivors; additions sharing an anchor are ordered as in
  [PLACE-6], by name, then ordinal.
- **[SAME-8] Merge.** A piece all three have: if two are equal, the third (OURS' when OURS equals
  THEIRS); else a clean `diffy::merge`; else `git merge-file -p OURS BASE THEIRS` on temporary
  files (no labels; exit 0 only); else, for members, [DEC-1]; else the element union; else a box
  over the piece (chapter 14, refined by [BOX-4]). A member one side deleted is dropped if the other
  left it as in BASE, else boxed with the deleter's section empty. A member one side added is that
  side's; added by both, OURS' if equal, else boxed with BASE empty. A member's lead merges as a
  piece when both sides have the member (BASE's lead, or OURS' if BASE lacks it), else is that of
  the side that has it. A written member is lead, text, and `\n` if missing. Header, prelude,
  members, tail and footer are concatenated, trailing `\n`s removed if OURS does not end in `\n`. A
  result that loses a line ([SAME-4]) is no answer. A result without a box is the merge; with one,
  the element union of the whole definition comes first, and failing it the definition is a
  conflict written as this result.

## 6.3 The statement fold

- **[SAME-9] Partition.** A text of two or more lines takes its header and footer as in [SAME-5];
  failing that, if its first non-blank line ends (trailing whitespace aside) with `:` or `{` and is
  followed by a more indented non-blank line, the body is every later line after a `:`, or, after a
  `{`, the lines before its last non-blank line if that comes after the next one, closes as in
  [SAME-5] and is indented no deeper; else all is body. Bracket depth counts `(`, `[`, `{` and
  closers before each body line, skipping strings in `"`, `'` or backticks closed on their line
  (`\` skips a character), `//` and `#` to the line's end, `/* */` and triple-quoted strings; an
  unterminated `/* */` or triple-quoted string means no partition, unbalanced brackets do not. A
  *statement* starts at each non-blank line not starting with `@`, `#`, `//`, `/*` or `* `, not `*`
  or `*/`, at the depth of the first non-blank body line and at most its indentation, not starting
  with `}`, `)`, `]`, `,`, `.`, `?`, `:`, `;`, `+`, `*`, `/`, `|`, `&`, `=`, `<`, nor with `else`,
  `elif`, `except`, `finally`, `catch`, `when` or `rescue` (alone or before `:`, space, `(` or
  `{`), nor with `case` or `default` when the previous non-blank, non-comment line ends with `:`.
  It runs to the next start; trailing blank and comment lines (those barred from starting) lead the
  next statement, and such lines directly above it are its own. Its *key* is its non-blank lines,
  trimmed, each followed by `\n`. No statement, no partition; at depth 3 or more there is no fold
  when every version has fewer than two statements.
- **[SAME-10] Alignment.** Each side matches BASE by the longest common subsequence of keys, read from
  the front (equal keys pair; else BASE advances unless advancing the side keeps a longer one);
  above 250,000 cells there is no fold. Between pairs, unmatched statements pair by the order-keeping
  matching of greatest total similarity over pairs of similarity `s` at least 0.4 (`s` is the larger
  Jaccard similarity, 1 for two empty sets, of the keys' identifier runs or of their non-space
  character bigrams; a pair's value is `trunc(s × 1,000,000)`; ties take a pair, then advance BASE;
  above 20,000 cells nothing pairs). These pairs, and exact pairs whose bytes differ, are edits.
  Unpaired BASE statements are deleted; an unpaired side statement is inserted before BASE
  statement `g + k`: `g` the first BASE index of its stretch, `k` the number of pairs in it whose
  side statement comes first.
- **[SAME-11] Fold.** Header, prelude, tail and footer: two equal, the third (OURS' when OURS equals
  THEIRS); else `diffy::merge`; else a box. Before each BASE statement and at the end come the
  insertions: one side's; identical ones once; two blocks of declarations both, the smaller
  concatenated keys first (OURS' on a tie); else a box, BASE empty. A block is of declarations when
  in each statement the first non-blank line that is not a comment line of [SAME-9] has a first `=`
  not followed by `=` nor preceded by `=`, `!`, `<`, `>`, `+`, `-`, `*`, `/`, `%`, `&`, `|`, `^` or
  `:`, with no `(`, `[` or `.` before it, and its name, the last identifier run before it once cut
  at its first `:` (`const { a } = b` names `a`), is not numeric-led nor `if`, `while`, `for`,
  `return`, `match`, `switch`, `case`, `else`, `elif`, `yield`, `assert`, `with`, `do` or `try`; the
  blocks' names are disjoint and neither block holds an identifier run the other names. Each BASE
  statement: unchanged by both, BASE; edited by one, that edit; edited by both, the edit once if
  equal, else the bytewise smaller of two with equal line counts and, line by line, equal
  indentation widths and whitespace-split tokens, else `diffy::merge`, else (while the depth is
  below 3) the statement's own fold if it has no box and passes the line checks below, else a box;
  deleted and unchanged, or deleted by both, dropped; deleted and edited, a box with the deleter's
  section empty. A statement's lead merges as a piece from BASE's and each side's (a side that did
  not edit it counting BASE's); if one side deleted it, the other's edited lead or BASE's.
  Statements are written as members are, trailing `\n`s as in [SAME-8]. The fold is used, as the
  definition's conflict text, only if it holds a box, loses no line and writes no non-blank line
  that no version has (lines compared without trailing whitespace; lines starting, after
  indentation, with `<`, `=`, `>` or `|` exempt).
