# 10. Where definitions go

The merged file lists the surviving base definitions in one order and puts every added definition
next to the survivor it was written after. Nothing in this chapter asks which side is ours.

## 10.1 The order of the survivors

- **[PLACE-1]** A side's *survivors* are the BASE definitions it still has, however the merge
  later decides them (kept, dropped or boxed). A side **reordered** when its survivors, in its
  order, differ from BASE's order of that same set.
- **[PLACE-2]** If neither side reordered, the order is BASE's. If exactly one side reordered, its
  order is used.
- **[PLACE-3]** If both sides reordered, BASE's order is kept, for all five file types, with no
  conflict about order.
- **[PLACE-4]** The final order of the BASE definitions is the order-preserving union ([IMP-4]) of
  the order chosen above, leading, with BASE's full order. A definition the chosen order leaves
  out is placed by that union. For example, BASE `a, b, c, d` with the chosen order `c, a, d`
  gives `c, a, b, d`.

## 10.2 Additions

- **[PLACE-5]** An addition is anchored, in each version that wrote it, to the nearest definition
  before it in that version that is a survivor the merge writes out. It goes directly after that
  survivor's place in the survivor order; with no such survivor it goes before all survivors. A
  definition both sides added takes the earlier of its two anchors.
- **[PLACE-6]** The additions that share one anchor are written in this order: an addition `u` must
  come before `v` when some version contains both and puts `u` first, except that a pair the two
  versions put in opposite orders constrains nothing. Among the additions whose required
  predecessors are all written, the one with the smallest identity key is written next.
- **[PLACE-7]** Identity keys ([ENT-3]) compare field by field: the parent (an absent one first),
  then the kind, then the name, each compared as text byte by byte, then the ordinal, as a number.
