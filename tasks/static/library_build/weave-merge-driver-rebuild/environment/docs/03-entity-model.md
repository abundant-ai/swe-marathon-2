# 3. The entity model

The entity merge reads each version as top-level definitions and the text between them.

## 3.1 Definitions

- **[ENT-1] Extraction.** A version's definitions are the entities `sem-core` 0.29.0 returns for its
  text after the encoding step of [LAY-5]: the plugin `create_default_registry().get_plugin(PATH)`,
  chosen by extension, called as `extract_entities(text, PATH)` with `PATH` exactly as given to `-p`
  (sem-core's ids contain it). None is added; only [ENT-2] removes any.
- **[ENT-2] Top level only.** Sort the entities by first line ascending, then last line descending,
  ties in sem-core's order. Keep one that starts after the last line of the most recently kept
  entity (initially 0), or whose first and last lines equal that entity's; drop the rest. The kept
  entities, in this order, are the version's definitions; methods, nested keys and locals belong to
  their container's text.
- **[ENT-3] Identity key.** (parent, kind, name, ordinal):
  - *parent*: sem-core's parent id, absent for nearly every definition; a Go method's is its
    receiver type;
  - *kind*: sem-core's entity type;
  - *name*: sem-core's name, adjusted: (a) if it contains `'`, each `'` is deleted together with the
    letters, digits and `_` after it, the commas and spaces after those, and the commas and spaces
    before it; then every `<>` is deleted and the result trimmed; (b) the name `_` (Go's
    `var _ = ...`) becomes `_#` and 16 lowercase hexadecimal digits of the 64-bit hash of the
    definition's text ([ENT-4]), trimmed, as Rust's `std::collections::hash_map::DefaultHasher::new()`
    hashes that `str`;
  - *ordinal*: the number of earlier definitions of the version with the same parent, kind and
    adjusted name.

  Keys compare as in [PLACE-7].

## 3.2 The text of a definition

- **[ENT-4] Its lines.** The whole lines from its first line, moved up by [ENT-5], through its last,
  with that line's `\n` if any, cut from the version's text (not sem-core's entity content); lines the
  definition before it already took are left out, possibly all. In JSON the separator after a member
  is excluded ([LAY-7]).
- **[ENT-5] Leading comments.** Walk up from the line above the definition, never into lines an
  earlier piece holds. A blank line directly above is stepped over once, before anything is taken.
  A line that, trimmed, ends with `*/` and does not start with `/*` (a lone `*/` too) is taken,
  inside a block or not, and opens a block, where other lines are passed until one starting with
  `/*`, which is taken and closes it. Otherwise a line is taken when, trimmed, it starts with
  `///`, `//!`, `/**` or `* `, or is `*`. Any other line, and any blank line not stepped over, ends
  the walk. The text starts at the highest line taken.
- **[ENT-6] Normalized text.** Two definitions *say the same thing* when their texts are equal after
  each one's own adjusted name is replaced by `__ENTITY__` at word boundaries. Replacing *at word
  boundaries* scans left to right and replaces an occurrence when neither neighbouring character is
  an identifier character (ASCII letter, digit, `_`, `$`, or a non-ASCII alphanumeric), resuming
  after it, or one character on after a refusal. An empty name replaces nothing.

## 3.3 Pieces

- **[ENT-7] The pieces tile the file.** In order of first line (a stable sort of the [ENT-2] list),
  each definition is preceded by its gap. The gap before the first is the *header*, present only if
  not empty; a gap between two definitions always exists, even empty, and is known by the sem-core
  ids of those two; text after the last is the *footer*. A version without definitions is one piece.
  The pieces concatenate to the version exactly.
- **[ENT-8] Too many equal names.** The entity model is not used when one name, counted by name
  alone and before the adjustments of [ENT-3], occurs 10 or more times among a version's
  definitions ([ROUTE-6]).
