# 4. Matching definitions across the three versions

Every top-level definition (chapter 3) of BASE, OURS and THEIRS is matched once. First come the
identity matches ([MATCH-1]). Then, for each side, re-homes are noted ([MATCH-8]) and renames are
inferred ([MATCH-2] to [MATCH-7]). Definitions both sides added under one key are then paired
([MATCH-10]), and everything left stands alone.

## 4.1 Identity

- **[MATCH-1]** Two definitions in different versions are the same definition when their identity
  keys ([ENT-3]) are equal.

## 4.2 Renames

Renames are inferred for each side on its own, from the base definitions without an identity match
on that side (the *unmatched* ones) and that side's definitions without one (its *additions*).

- **[MATCH-2] Equal bodies.** An addition and an unmatched base definition that say the same thing
  ([ENT-6]) form a candidate pair. All the definitions that say one same thing are handled
  together. The base ones and the additions are each sorted by identity key and paired in order:
  first with first, and so on. A pair whose kinds differ is dropped, and its
  members are not paired again with anything in that group. The parents may differ. A base
  definition or an addition that is in any candidate pair of this rule takes no part in
  [MATCH-3] to [MATCH-5].
- **[MATCH-3] Similar bodies.** A remaining addition and a remaining unmatched base definition of
  the same kind and parent form a candidate pair when the Jaccard similarity of their token sets
  ([MATCH-9]) is at least **0.7**.
- **[MATCH-4] Corroborated renames.** Call sites that moved are read from the identity matches of
  the side, one matched definition at a time. Within one such definition, each name its BASE text
  calls and its side's text no longer calls (an *old* name), taken with each name its side's text
  calls and its BASE text did not (a *new* name), is a move. Here a text *calls* a name as
  [BIND-1] says, and the name must start with a letter or `_`. For each move, a remaining
  unmatched base definition named *old* and a remaining addition named *new* form a candidate pair
  when they have the same kind and parent, no BASE definition has the name *new*, and either the
  Jaccard similarity of their token sets is at least **0.3** or both token sets have at most **12**
  tokens.
- **[MATCH-5] Short bodies.** When the token sets of a remaining unmatched base definition and a
  remaining addition both have at most **12** tokens, the two form a candidate pair when they
  have the same kind and parent; no BASE definition has the addition's name;
  their body token sets ([MATCH-9]) share a token that occurs in the body token sets of at most
  **4** of the side's short additions; and the shared tokens number at least **0.7** times the
  size of the smaller body token set (a size of 0 counts as 1).
- **[MATCH-6] Choosing among candidates.** Each candidate pair has a confidence:
  - 0.95 for an equal body;
  - 0.6 + 0.3 × similarity for a similar body;
  - 0.45 + 0.1 × the shared fraction for a short body;
  - 0.55 + 0.1 × similarity for a corroborated rename.

  Candidates are taken greedily, the most confident first. Ties go to the smaller identity key of
  the base definition, then of the addition. A candidate is skipped when its base definition or
  its addition is already matched.
- **[MATCH-7] Names outrank bodies.** After renames are inferred for both sides, some additions
  have an identity key that both sides added. Each such pair of additions is checked once. If
  OURS' addition and THEIRS' addition were not both taken as a rename of the same base definition
  (or both left untaken), the two additions are withheld from rename inference. The renames of
  both sides are then inferred once more without them. That second inference is not checked
  again.
- **[MATCH-8] Re-homes.** This rule uses the identity matches of each side only. A base definition
  with no identity match on a side is noted as moved into that side's definitions without an
  identity match when at least **0.6** of its signature lines appear among the signature lines of
  all those definitions taken together. Every such definition that holds one of the covered lines
  counts as a home; homes are listed in the side's definition order. A definition's *signature lines* are its lines that do not start, after
  indentation, with a keyword of [MATCH-9], each with its whitespace runs collapsed to one space
  and its ends trimmed, keeping those longer than 8 bytes, as a set. A definition with no
  signature lines is never re-homed.

## 4.3 Tokens

- **[MATCH-9]** A token is a word separated by whitespace. A definition's *token set* holds the
  tokens of its whole text. Its *body token set* holds the tokens of its text without its
  definition lines. A definition line is a line that starts, after indentation, with one of
  `def `, `function `, `fn `, `class `, `func `, `interface `, `struct `, `trait `, `impl `,
  `export `, `public `, `private `, `async `, `pub `. In both sets, duplicates count once.

## 4.4 Both-added and the rest

- **[MATCH-10]** A definition both sides added under one identity key is one definition both sides
  created; chapter 5 decides whether the two bodies agree. Every definition still unmatched is an
  addition or a deletion on its own.
