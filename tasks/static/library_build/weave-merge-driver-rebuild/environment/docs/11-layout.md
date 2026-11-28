# 11. Layout: the text between definitions

The merged file is the merged definitions in their planned order (chapter 10), each with the merged
gaps that lead it.

## 11.1 Gaps and the definitions they lead

- **[LAY-1] Attaching gaps.** The gaps of [ENT-7] (a version without definitions is one gap, its
  whole text) are merged by chapter 8. Each merged gap except the header and the footer is then
  attached to one definition. The versions are walked in the order BASE, OURS, THEIRS. In each
  walk, a merged gap not yet attached waits until the walk reaches a definition that the merge
  keeps. That is a definition of any triple not dropped, even one decided with empty text. The
  waiting gaps are then attached to it, in order. Gaps still waiting at the end of a walk are
  *trailing* gaps.
- **[LAY-2] Writing.** The merged header is written first. Then each definition with non-empty
  text (or a conflict box) is written in the planned order of chapter 10, in four steps.
  1. A `\n` is added if the output so far does not end with one.
  2. Its attached gaps that are not yet written are joined by [LAY-3] and written. The gaps are
     found under its BASE, then OURS, then THEIRS definition, each in attachment order. If nothing
     at all has been written yet, the joined text first loses its leading blank lines. If the
     joined text does not end with `\n`, one is added.
  3. If it has no such gap, the separator of [LAY-4] is written instead. This never happens
     before the first definition written.
  4. Its text is written, followed by `\n` if it lacks one (for JSON, see [LAY-7]).

  A definition decided with empty text is not written, and the gaps attached to it are lost.

## 11.2 Several gaps before one definition

- **[LAY-3]** When several gaps lead one definition, every gap that carries text (a comment, an
  import) is kept, in order. Neighbouring blank gaps (only whitespace) are joined into one: the one
  with the most newlines, then the longest, then the greater by text.

## 11.3 The separator

- **[LAY-4]** The separator is BASE's dominant gap. Take BASE's whitespace-only gaps that follow a
  definition, the footer included; two directly adjacent definitions count as the empty gap. The
  most frequent of these wins. Ties go to the shorter gap, then to the one that sorts first as
  text. With no such gap, the separator is one `\n`.

## 11.4 Line endings, byte-order mark, final newline

- **[LAY-5]** Before merging, a UTF-8 byte-order mark is removed from each version and `\r\n` is read
  as `\n` (a carriage return not followed by `\n` is left alone). If all three versions contain
  `\r\n`, every `\n` of the merged text is written as `\r\n`; if all three start with a
  byte-order mark, the merged file starts with one. Otherwise the merged file uses `\n` and has no
  byte-order mark.
- **[LAY-7] The JSON separator.** In `.json` files the separator between definitions is `,`; the
  other four types have none. When a version is read, one `,` at the end of each definition's text
  (looking past trailing whitespace, which is kept) is removed. When the merged definitions are
  written, each one that is followed by another written definition and is not a conflict box gets
  its `,` back: after its text with trailing whitespace trimmed, before that whitespace, unless the
  trimmed text already ends with `,`.
- **[LAY-6] The end of the file.** After the last definition, the trailing gaps that are not yet
  written and carry text (blank ones are dropped) are joined by [LAY-3]. The merged footer and the
  merged whole-text gap of [LAY-1] are joined after them. If the result is not empty, a `\n` is
  added to the output when it does not end with one, and then the joined text is written.
