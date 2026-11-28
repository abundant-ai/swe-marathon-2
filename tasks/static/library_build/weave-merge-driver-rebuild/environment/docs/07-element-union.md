# 7. Element union

Every failed condition below means *no union*, and the caller's next rung decides.

## 7.1 Where and how

- **[ELEM-1] Language.** The language is the extension after the last `.` of `PATH`'s file name,
  lower-cased: `go`, `ts` or `py`. Any other, BASE equal to OURS or THEIRS, OURS equal to THEIRS, or
  a blank BASE: no union.
- **[ELEM-2] Framing.** Texts are parsed with the tree-sitter grammar sem-core uses for `PATH`
  (`ParserRegistry::extract_entities_with_tree`; for `.ts` the TypeScript grammar, not TSX); a tree
  whose root reports tree-sitter's `has_error()` (MISSING nodes included) is no parse. Python: the
  leading spaces and tabs of BASE's first non-blank line must begin every non-blank line of all
  three texts; they are removed from those lines (whitespace-only lines become empty) and put back
  on the non-blank lines of the result. Go is tried as is, then after `package weave_fragment\n`;
  TypeScript as is, then between `class WeaveFragment {\n` and `\n}\n`, then between
  `function weaveFragment() {\n` and `\n}\n`. The first framing under which all three parse is
  used; the merged text must parse too, and the frame is then removed.
- **[ELEM-3] Tree merge.** For three texts of one position the *one-sided rule* gives OURS' text when
  OURS equals THEIRS or THEIRS equals BASE, THEIRS' when OURS equals BASE, else nothing. From the
  root down, a node is taken by that rule when it answers. Else the three nodes must have one kind;
  three collections ([ELEM-4]) of one kind merge by 7.2 (of different kinds: no union). Otherwise
  they need the same non-zero number of children, named or not, of the same kinds in order. Each
  child is marked by who changed its text (only OURS, only THEIRS, both differently); children with
  different marks whose BASE line ranges meet mean no union. Children merge recursively; the text
  before, between and after them, and outside the root, must answer to the one-sided rule.

## 7.2 Collections

- **[ELEM-4] Collections**, by tree-sitter node kind, with their delimiters:
  - Go: `literal_value` (`{` `}`), keyed if it has a `keyed_element` child, else a sequence;
    `expression_switch_statement` with a tag value (`{` `}`), a switch; `block` (`{` `}`) and
    `source_file`, statements; `const_declaration` with `(` (`(` `)`), a const block, *iota* if it
    has an `iota` node or identifier (the flag is part of the kind);
  - TypeScript: `object`, `export_clause`, `named_imports` (`{` `}`), keyed; `array` (`[` `]`), a
    sequence; `switch_body` (`{` `}`), a switch; `statement_block` (`{` `}`) and `program`,
    statements;
  - Python: `dictionary` and `set` (`{` `}`) and a `list` assigned to `__all__` (`[` `]`), keyed;
    another `list` (`[` `]`) and a `tuple` with `(` (`(` `)`), sequences; `block` (not of a `match`)
    and `module`, statements.

  Keyed collections and sequences are comma-separated. The elements are the children between the
  first opening and the last closing delimiter (all children where there are none), less comments,
  commas, `;` and newline tokens; any other unnamed child there means the node is not a collection.
- **[ELEM-5] Slots.** An element's slot holds its *lead* (text since the previous slot or the opening
  delimiter), its *body*, the comma after it, a comment starting on its last row, and its *rest*
  (text after the body to the slot's end, first comma removed). Text after the last slot up to the
  closing delimiter is the *tail*. Two slots are *the same* when their leads are equal and their
  bodies and rests are equal after trailing whitespace is trimmed. A slot is *bare* when its lead,
  less spaces and tabs at both ends, is exactly `\n`.
- **[ELEM-6] Keys.** A *label* is: a string literal (Go: interpreted, raw or rune) that begins and
  ends with one quote character and contains no `\` and no `${` (in Python, none with an `f`, `b`
  or `r` prefix), as `s:` and the text inside the quotes; a decimal integer (no leading zero but
  `0`), as `i:` and its digits (in TypeScript as `s:`); a name whose dot-separated parts are each a
  letter, `_` or `$` followed by letters, digits, `_` or `$` (Go identifier or selector, TypeScript
  identifier or member expression, Python identifier or attribute other than `True`, `False`,
  `None`), as `n:` and its text; a TypeScript property identifier other than `__proto__`, as `s:`
  and its text; a Go `literal_element`, as the label of its first named child. A keyed element's
  key is the label of its key (Go `keyed_element`, else its first named child; `pair`), of itself
  (TypeScript shorthand property; a string or integer element of a Python set or `__all__`), or of
  the name of a TypeScript method not marked `get`, `set` or `static`; for an import or export
  specifier, `s:` and its alias, else its name. A switch case is keyed `case:` and its labels (all
  must exist) sorted and joined by `|`; a default case has the one label `default`. A const spec is
  keyed `const:` and its names joined by `,`. Sequence and statement elements are keyed `t:` and
  their text with whitespace runs collapsed to one space. A statement may declare a name: `fn:` and
  the name of a TypeScript function or generator declaration, a Go top-level `func` or `type`, or a
  Python function, decorated or not; for a Go top-level method, `fn:`, the receiver's last word
  without `(`, `)`, `*`, a `.` and the name.
- **[ELEM-7] Alignment.** Keyed, switch and const collections align with BASE by key (`#` and the
  collapsed text where there is none), the n-th occurrence of a key with the n-th; a key a side
  states twice or more must occur as often in BASE, and a key BASE states twice or more as often on
  the side or not at all. Sequences and statements align by the longest common subsequence of
  collapsed texts, read as in [SAME-10]; between pairs, a lone BASE element and a lone side element
  pair, otherwise each BASE element pairs, in order, with the side element of the same signature
  (first declared name, else collapsed first line), signatures unique on both sides; one matched
  out of order means no union. Pairs must keep BASE's order. Unpaired side elements are insertions,
  anchored after the nearest paired BASE element before them, or before all.
- **[ELEM-8] BASE elements.** An element is *gone* on a side that deleted it or wrote it not the
  same. Elements gone on different single sides, or on one side and on both, whose line ranges meet,
  mean no union. Kept by both: its comma by the one-sided rule over the three flags; its slot is
  BASE's if both are the same as BASE, THEIRS' if only THEIRS differs, else OURS' when THEIRS is
  the same as BASE or as OURS (THEIRS' if the same as OURS and rendered smaller); if both differ,
  their leads and rests must be equal and the body merges by [ELEM-3], the slot keeping BASE's key,
  names and node. Deleted by one side, it must be the same as BASE on the other, and is dropped;
  deleted by both, dropped.
- **[ELEM-9] Insertions.** Every inserted element needs a key. Except in keyed collections, const
  blocks without iota and test-table sequences, an insertion is refused where the other side changed
  the BASE element facing it (deleted it, or changed the last line of the one before or the lead or
  first line of the one after), unless every element inserted there declares a name. One side's run
  stands. Two sides' runs at one point unite only in a keyed collection, a const block without
  iota, after the last spec of one with iota, in a switch, in a test-table sequence, or in
  statements all declaring names. A *test table* is a sequence in a test file whose nearest
  ancestor other than `composite_literal`, `expression_list` and `parenthesized_expression` is a
  `short_var_declaration`, `var_spec`, `assignment_statement`, `assignment`, `variable_declarator`
  or `assignment_expression`. A *test file*'s name ends in `_test.go` or `_test.py`, or starts with
  `test_` and ends in `.py`, or contains `.test.` or `.spec.`, or a directory of `PATH` is `test`,
  `tests`, `__tests__` or `testdata`.
- **[ELEM-10] Two runs.** If every slot of both runs is bare, they merge by key: equal heads must have
  equal collapsed texts and give one element; else the smaller key goes first, each run keeping its
  order. Otherwise the run whose keys, then renderings, are smaller goes first, whole. Either way a
  key met twice is one element when the collapsed texts agree (the one met first, OURS' in the key
  merge, unless the other renders strictly smaller), else no union.
- **[ELEM-11] Guards.** No inserted key (in keyed, switch and const collections) or name (switch
  label, constant name, declared name) may equal a key or name of a kept BASE element or of another
  insertion; a key both sides inserted at different points means no union. Switch elements are
  judged in the node they were taken from: in Go none may contain `fallthrough`; in TypeScript each
  inserted case, and the case before it, must end in `break`, `return`, `throw` or `continue`, or a
  block so ending.
- **[ELEM-12] Writing.** Insertions before all elements, then for each BASE element in order the
  element if kept and the runs anchored to it. An element is lead, body, comma if wanted, rest; in
  a comma-separated collection all elements but the last get a comma and the last keeps its own
  flag. The text before the opening delimiter's end, the tail, and the text from the closing
  delimiter each follow the one-sided rule.
- **[ELEM-13] Certificate.** The result (frame removed) must not lose a line ([SAME-4]), and over
  non-blank lines trimmed, every comma deleted, then trimmed at the end, with counts `b`, `o`, `t`,
  `x` in BASE, OURS, THEIRS and result: `x >= o - max(0, b - t)`, `x >= t - max(0, b - o)`,
  `x <= max(o, t, o + t - b)`.
- **[ELEM-14] Disjoint form.** For gaps and files without definitions the three texts must parse
  unframed, their roots must have the same non-zero number of children (comments included), of the same kind position by
  position, and no child may differ in all three; then the union applies as above.
