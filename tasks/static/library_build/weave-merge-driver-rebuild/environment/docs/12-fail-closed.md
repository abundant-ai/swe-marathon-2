# 12. When a merge may be called clean

A composed result is written as clean only if it passes every check below, made against the three
inputs.

## 12.1 What is checked, and when

- **[GATE-1]** These results are checked: every clean result of the entity merge (chapters 3-11)
  and of routes [ROUTE-6] and [ROUTE-10]; every clean answer of the fallback in section 12.2; every
  text a rule of chapter 13 settles. Not checked: one side's own file ([ROUTE-1], [ROUTE-3], and
  [ROUTE-4] apart from rule [GATE-DATA-1]).
- **[GATE-2]** The checks run in this order, and the first that fails decides: markers (12.3),
  lines (12.4), data (12.5), declarations (12.6: parse, keys, bindings, dangling uses, revived
  imports), then `iota` (12.7).

## 12.2 What is written when a check fails

- **[GATE-3]** The driver runs the line route on the three inputs ([ROUTE-9]). If git's answer is
  clean and passes every check of this chapter, it is the result, clean (status 0).
- **[GATE-4]** If git's answer has conflicts, git's conflicted text is the result. Like every
  conflicted result it is then offered to chapter 13 ([GATE-6]); unless a rule there settles it,
  the status is 1.
- **[GATE-5]** If git's answer is clean but fails a check, the result is one conflict box over the
  whole file: OURS, BASE and THEIRS in full, cut and refined as chapter 14 describes. It too is
  offered to chapter 13; unless a rule there settles it, the status is 1. The whole-file box is
  built from the inputs as given (before the normalisation of [LAY-5]): lines are split at `\n`, a
  `\r` before the `\n` is dropped, a byte-order mark stays part of the first line, and the box
  always ends with `\n`.
- **[GATE-6]** Every conflicted result is offered to the rules of chapter 13, with the exceptions of
  [RULE-ENTRY]; a text a rule settles is checked, and dropped if it fails, as [RULE-NEVER] says.

## 12.3 Markers

- **[GATE-MARK]** A clean result may not contain a line that starts with `<<<<<<<` or `>>>>>>>`.

## 12.4 Lines

A line is compared after removing leading and trailing whitespace, then every trailing comma, then
any whitespace left at its end. A line is **significant** when, so trimmed, it is at least 8 bytes
long and contains at least one letter or digit (in the Unicode sense).
Only significant lines are counted. For each significant line, let `n`, `o`, `t` and `m` be the
number of times BASE, OURS, THEIRS and the result state it.

- **[GATE-LINES-1] Nothing both sides kept is lost.** The result must state the line at least
  `max(0, min(n, o) + min(n, t) - n)` times.
- **[GATE-LINES-2] Nothing is stated too often.** For a line that some input states (`n + o + t > 0`),
  the allowance is `o + t - n` when either side states it more often than BASE, and `min(o, t)`
  otherwise; an import line that the merge kept because a new line uses it is allowed at least
  once. The result may not exceed the allowance for a line that is significant and is not a
  fragment, or for any over-allowance line that stands next to another over-allowance line. A
  **fragment** is a line that ends with one of `, ( [ { : + - * / & | = < > ?` or with `=>` or
  `->`, or that starts with one of `. , ) ] } ? : +` or with `&&` or `||`.
- **[GATE-LINES-3] A block both sides inserted counts once.** If one side's change inserts a run of
  at least 3 significant lines that also appears, contiguously, inside a run the other side
  inserted, the result may not contain that run (contiguous among its significant lines) more
  often than the side that contains it most.
- **[GATE-LINES-4]** When the result keeps a rename the merge carried out ([CELL-16] says which
  renames are kept), the counts are taken after replacing the old name by the new one, at word
  boundaries ([ENT-6]), in BASE, OURS and THEIRS.

## 12.5 Data (JSON, TOML)

- **[GATE-DATA-1]** If OURS or THEIRS loads, the result must load.
- **[GATE-DATA-2]** At any one table path of a JSON document, read as [DATA-2] says, no key may be
  stated more often in the result than in the side that states it most (and a key stated once is
  always allowed).

## 12.6 Declarations

[GATE-PARSE], [GATE-KEYS], [GATE-DANGLING] and [GATE-REVIVED] read a syntax tree, so they apply to
Python, TypeScript and Go only. [GATE-BIND] applies to all five types: for JSON and TOML it counts
the definitions `sem-core` extracts (chapter 3).

- **[GATE-PARSE]** If OURS and THEIRS both parse without errors, the result must parse without
  errors.
- **[GATE-KEYS]** Keyed elements are read from the parse tree:
  - Go: each expression of a `case` (so `case a, b:` is two keys), the types of a type-switch case,
    `default`; each keyed element of a composite literal (map keys, struct fields);
  - TypeScript: each `case` value of a `switch`, `default`; each non-computed key of an object
    literal, shorthand properties and methods in an object literal;
  - Python: each `case` clause of a `match`, whose whole pattern (all its alternatives, with its
    guard, if any) is one key; each non-computed key of a dict literal.

  A key is compared with its whitespace collapsed. In Python and TypeScript, a dict or object key
  and a TypeScript `case` value that start and end with a quote character (`'`, `"` or backquote)
  are compared without those two characters; Python `case` patterns and every Go key are compared
  as written, so `case "a":` and `case 'a':` are different Python keys. For each kind (case, key) and key, take the most
  times any single container of OURS states it, and the same for THEIRS. A container of the result
  may not state that key twice or more when that is more than both of those numbers.
- **[GATE-BIND]** Names are counted per version:
  - imports: Python `import a.b` binds `a` and `import a.b as c` binds `c`; `from m import x, y as
    z` binds `x` and `z`; TypeScript default, named (`as` gives the local name) and namespace
    imports bind their local names; a Go import binds its alias, else the last segment of its path
    (a `/vN` version suffix is skipped, and `-` or `.` in it becomes `_`); `_` and `.` bind nothing;
    an indented import binds nothing at file scope;
  - a Go `package` clause counts as one `(package)`;
  - each top-level definition counts by its bare name (without generic arguments), so it collides
    with an import of that name; a nested definition counts as `Parent::kind name`, and in
    TypeScript also with its parameter list (read from the first three lines of the definition,
    from the first `(` to its matching `)`, whitespace removed);
  - kinds that declare no name are not counted: `impl`, `extension`, `instance`, `module`,
    `internal_module`, `namespace`, `interface`, `test`, `test_suite`, `export`, `import`,
    `package`, `use`, `chunk`.

  The result may not count a name more often than the side that counts it most.
- **[GATE-DANGLING]** A name of at least 3 characters that some input binds at file scope (an
  import, a top-level definition, or a top-level declaration line), that the result mentions in any
  use position (a call, an argument, a type argument, an operand), and that the result no
  longer binds, makes the result dangling, unless one of the inputs also mentions the name without
  binding or declaring it.
- **[GATE-REVIVED]** (Python and TypeScript import statements; Go import blocks are not read here.)
  An import of a name of at least 3 characters that BASE has and the result has,
  that one side no longer binds, and that no non-import line of the result uses, is refused.

## 12.7 Go `iota` blocks

- **[GATE-IOTA]** In a Go `const` block that uses `iota`, a constant may not take a value that
  neither side gives it. Both sides inserting constants ahead of an existing constant gives it such
  a value (it shifts by both insertions); one side inserting, or either side appending after the
  last constant, does not.

## 12.8 The key backstop

- **[GATE-12]** Every clean result that differs from both OURS and THEIRS, whichever route
  wrote it, is also checked by [GATE-KEYS]. It runs after chapter 13, so a failure is final: one
  whole-file box ([GATE-5]), status 1. It is skipped when one of the four texts has a NUL byte
  among its first 8,192 bytes.
