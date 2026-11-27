# 9. Renames carried to call sites, and other name checks

After chapters 5 to 8 and before chapter 10, [BIND-1] to [BIND-7] run in order. *Additions* are
the texts, as matched, of definitions a side added ([CELL-6] to [CELL-8]), with that side;
*surviving names* are the names decisions carry ([CELL-18]).

- **[BIND-1] Rename repair.** A *definition line* of a name, after its indentation and any leading
  `export `, `public `, `private `, `protected `, `static `, `pub `, `async `, `default `,
  `abstract `, `final ` and `override ` (removed repeatedly), starts with `def `, `function `,
  `fn `, `class `, `func `, `interface `, `struct `, `trait `, `impl `, `type ` or `enum `, then
  spaces and the name, not followed by an identifier character. A text *calls* a name when, on a
  line that is not a definition line of it, the name follows neither an identifier character nor
  `.` and is followed, after optional spaces, by `(`. For each noted rename (old, new) ([CELL-16]),
  in BASE order, unless `old` is a surviving name or does not start with a letter or `_`: every
  other triple decided as text that called `old` before this pass, and still does, has each
  occurrence of `old` at word boundaries ([ENT-6]) replaced by `new`.
- **[BIND-2] A deletion new code calls.** With surviving names taken afresh, a triple decided as
  nothing ([CELL-9]) whose BASE name does not survive becomes a *modify/delete* conflict when an
  addition by a side that did not delete it calls that name: BASE's text against that side's, the
  other section empty.
- **[BIND-3] A new definition new code calls.** A one-sided addition ([CELL-6]) decided as text, named
  as no BASE definition is, becomes a *both added* conflict over the adder's text alone when an
  addition by the other side calls that name.
- **[BIND-4] A local no longer assigned.** Asked of each triple with a BASE definition whose text the
  merge composed ([SAME-2], [DEC-1], the member merge, the element union). A text *assigns* a name on a
  line not blank, not starting with `#` or `//`, not inside a `(` or `[` left open by earlier lines,
  not ending in `,`, that, after an optional `let `, `const ` and `var ` (each tried once, in order),
  has a first `=` not starting `==` nor preceded by `!`, `<`, `>`, `+`, `-`, with just that name
  (ASCII letters, digits, `_`, not digit-led) before it. A text *binds* what it assigns, lines in
  brackets or ending in `,` included and the name being the last space-separated word before `=`,
  and every such word of its lines through the one where its first `(` or `[` closes (at most 12
  lines). A text *uses* a name on a line that is not its definition line, nor one whose text before
  its first `=` is the name, holding the name at word boundaries not preceded, spaces aside, by `.`.
  A result using a name BASE assigns and the result does not bind becomes a *both modified*
  conflict over the three texts. For a container kind ([SAME-5]) this is asked per member: both
  texts cut by indentation (no sem-core children; either uncuttable, no check), each BASE member
  named by ASCII letters, digits, `_` and not `class`, `interface`, `enum`, `record`, `struct`,
  `impl`, `trait`, `namespace`, `module`, `static`, `new`, `return`, `if`, `for`, `while`, `switch`
  or `try` paired with the result's member of the same name and ordinal, names the whole result
  binds or that name its members exempt.
- **[BIND-5] A body moved twice.** A BASE definition is *re-homed* on a side, into its *homes*, as
  [MATCH-8] notes. Homes that are the triple's own OURS or THEIRS definition do not count, nor a
  side left with none. If the triple is decided as text, or both sides re-homed it into differing
  sets of home texts, and it is not a conflict, it becomes a *both modified* conflict: BASE's text,
  and per side its definition's text or, lacking one, its homes' texts joined by `\n`.
- **[BIND-6] Extracted lines the other side edited.** A BASE definition with an identity match on side
  X is *extracted* when signature lines of it that X's version lacks are signature lines of X's
  definitions without identity match (its *moved lines*; those definitions, its *homes*). Unless
  the other side Y extracted it too or deleted it: *removed* are its signature lines Y's version
  lacks, *added* those Y's version has and BASE lacks, both sorted. No removed line moved: nothing.
  A removed line not moved, lists of different lengths, or a removed line (paired in order) found
  in not exactly one home, or in a home not decided as text: the triple becomes a *both modified*
  conflict over its three texts (an existing conflict is rewritten as one box over its texts).
  Otherwise every line of that home whose collapsed form is the removed line becomes the paired
  added line, keeping its indentation, and the triple is decided as X's text.
- **[BIND-7] Both sides extracted.** A BASE definition both sides extracted into differing sets of home
  texts, whose triple is a conflict, with every home decided as text in a triple of its own, and
  which both sides still have: its conflict is rebuilt over BASE's text and, per side, its homes
  (each followed by `\n` if it lacks one, then an empty line) and its own text; the homes' triples
  are written as nothing.
