# 14. Conflict boxes

A conflict is written into the merged file as a box. With `-l 7` every box uses the standard
markers, each on a line of its own:

    <<<<<<< ours
    (ours' lines)
    ||||||| base
    (base's lines)
    =======
    (theirs' lines)
    >>>>>>> theirs

## 14.1 What a box holds

- **[BOX-1]** A box is about one scope: a definition (chapter 5); one member of a class, one
  statement of a definition's body, a block of statements inserted into a body, or the text of a
  body before its first or after its last statement (chapter 6); an interstitial region between
  definitions (chapter 11); or the whole file ([GATE-5]). Its three sections hold that scope's text
  in OURS, BASE and THEIRS. A side that deleted the scope has an empty section, and so does BASE
  when both sides added it.
- **[BOX-2]** Each line of a box is written followed by `\n`; the last line of a section gets a `\n`
  even when the input's last line had none. In a file the entity merge wrote, the whole output,
  boxes included, then takes the line endings and byte-order mark of [LAY-5]. A whole-file box
  ([GATE-5], [GATE-12]) keeps `\n` endings. Git's boxes (section 14.4) keep the inputs' endings.

## 14.2 The frame cut

- **[BOX-3]** The lines with which every present section begins, identically, are written once
  before the box (the frame); likewise the lines with which every present section ends are written
  once after it. Lines are compared whole. The trailing frame never reaches into the leading one.
  For a definition, and for a box inside a body (chapter 6), an empty section leaves no frame. For a class member that one side deleted,
  the frame is cut over the two other sections.

## 14.3 Narrower boxes

- **[BOX-4] Refinement.** A definition's box may be split only when its conflict is of the kind
  *both modified* ([CELL-17]) and all three versions have the definition. Boxes of the other kinds
  are never split. An interstitial box and the whole-file box may be split even when one side
  emptied the region.
  A split is considered only when the cut box holds at least 8 lines over its three sections, and no
  line of the three scope texts starts with 31 copies of `<`, `|`, `=` or `>`. The three scope
  texts (each given a final `\n` if it lacks one) are merged line by line with `diffy` 0.5.2's
  three-way merge in diff3 style. If that merge is clean, the box stays whole. If it conflicts, the
  scope is written as that merge's text: what it merged outside its conflicts as plain lines, and
  each of its conflicts as its own box, cut by [BOX-3]. The split form is used only when its boxes
  hold fewer lines in total than the whole box would.
- **[BOX-5] Coalescing.** In a file the entity merge wrote, two boxes separated by at most 6 lines
  that are outside any box are written as one box. That box's ours section is the first box's ours
  lines, the lines between, then the second box's ours lines; its base and theirs sections are
  built the same way. Coalescing repeats until no two boxes are that close. A box's section ends at
  the next line that starts with `<<<<<<<`, `|||||||`, `=======` or `>>>>>>>`; if any line starting
  with `<<<<<<<` does not open a well-formed box, nothing in the file is coalesced. In a coalesced
  file every base marker line is written `||||||| base`, and if the text before coalescing did not
  end with `\n`, all trailing newlines are removed from the result. The whole-file box is never
  coalesced.

## 14.4 Boxes written by git

- **[BOX-6]** On the line route ([ROUTE-9]) and in the fallback of [GATE-4], conflicts are git's own,
  as git writes them; rules [BOX-2] to [BOX-5] do not apply to them.

## 14.5 The hint

- **[BOX-7]** When the status is 1, one hint is appended to the first line of the file that starts
  with exactly seven `>` (an eighth `>` does not count) and does not already carry it:

      >>>>>>> theirs · weave: run 'weave explain PATH' for per-hunk detail, 'weave check' to verify your resolution

  The separator is a space, U+00B7 (middle dot), and a space; `PATH` is the `-p` argument as given.
  The hint goes before that line's line ending (`\n` or `\r\n`), which is kept. A file with no such
  line gets no hint. A clean result never gets one.

