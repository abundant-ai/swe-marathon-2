# 5. The cell table

After matching (chapter 4) every definition belongs to exactly one *triple* of BASE, OURS and
THEIRS incarnations, any of which may be missing, decided on its own from each side's action.

## 5.1 Actions

- **[CELL-1]** A side's action on a triple is one of:
  - *absent*: no BASE definition and none on this side (only beside the other side's addition);
  - *added*: no BASE definition, one on this side;
  - *deleted*: a BASE definition, none on this side;
  - *unchanged*: the same name as BASE ([ENT-3]) and the same normalized text ([ENT-6]);
  - *edited*: the same name, a different normalized text;
  - *renamed*: a different name, the same normalized text;
  - *renamed and edited*: a different name and a different normalized text.

## 5.2 Dispositions

A triple is written as a side's definition text ([ENT-4]), as nothing, or as a conflict box
(chapter 14) whose sections hold the three texts, a missing definition giving an empty section. The
actions may come in either order.

- **[CELL-2]** unchanged, unchanged: OURS' text.
- **[CELL-3]** edited, unchanged: the editor's text.
- **[CELL-4]** edited, edited, same normalized text: OURS' text.
- **[CELL-5]** edited, edited, different normalized texts: chapter 6.
- **[CELL-6]** added, absent: the adder's text.
- **[CELL-7]** added, added, same normalized text: OURS' text.
- **[CELL-8]** added, added, different normalized texts: conflict *both added*, BASE section empty.
- **[CELL-9]** deleted, deleted; deleted, unchanged: nothing (see [BIND-2]).
- **[CELL-10]** deleted, and edited, renamed or renamed and edited: conflict *modify/delete*, the
  deleter's section empty.
- **[CELL-11]** renamed or renamed and edited, and unchanged: the renamer's text; a rename is noted.
- **[CELL-12]** renamed or renamed and edited, and edited: conflict *rename against edit*, whatever
  the texts.
- **[CELL-13]** both renamed, renamed and edited, in any combination, to different names: conflict
  *two renames*.
- **[CELL-14]** renamed, renamed, to one name; or renamed and edited, renamed and edited, to one name
  and the same normalized text: OURS' text; a rename is noted.
- **[CELL-15]** renamed and edited, renamed, to one name; or renamed and edited, renamed and edited,
  to one name, different normalized texts: chapter 6, with BASE's text first rewritten (its old name
  replaced by the new one at word boundaries); a rename is noted unless the result is a conflict.

## 5.3 Renames and conflicts

- **[CELL-16] Noted renames.** A rename is (BASE's name, the new name), the new name being OURS' in
  [CELL-14] and [CELL-15]; all are carried to call sites ([BIND-1]). Only those of [CELL-11], and of
  [CELL-14] when neither side edited, also feed [GATE-LINES-4], unless chapter 9 changes their
  triple's decision. A rename from or to an empty name is not noted, and [CELL-11] or [CELL-14] then
  carries an empty name.
- **[CELL-17] Conflict kinds.** Each conflict has a kind: *both added*, *modify/delete*, *rename
  against edit*, *two renames*, or *both modified* (chapters 6, 8, 9 and 12), used by [RULE-ENTRY]
  and [BOX-4] and never written with `-l 7`.
- **[CELL-18] Names.** A triple written as text carries, for chapter 9, the new name in [CELL-11],
  [CELL-14] and [CELL-15], else the name of the definition written; one written as a conflict carries
  OURS' and THEIRS' names, where they exist.
