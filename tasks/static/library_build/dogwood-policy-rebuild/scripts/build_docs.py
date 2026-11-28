"""Build the documentation the working machine ships in /app/docs from Dogwood 1.2.0's own docs.

Usage: python3 -I build_docs.py --src DOGWOOD_DOCS --edits docs_edits.json --out OUT

DOGWOOD_DOCS is `dogwood-docs/` of the 1.2.0 source (tag commit 8ffd2106). OUT receives
`guide/` (the kept chapters), `examples/` (the example bundles) and the source's `LICENSE`
(Apache-2.0), then the edits in
docs_edits.json are applied in order. Each edit names the file it changes, relative to OUT, and
fails the build if it does not apply exactly as written, so the result is a function of the pinned
source and the edit list alone.

Edit kinds:
- replace: `old` occurs exactly `count` times (default 1) in `file` and becomes `new`.
- delete_section: the section whose heading line is exactly `heading` is removed, from that line
  to the next heading of the same or a higher level (headings inside fenced code do not count).
- move_section: the section headed `heading` in `from` (a path under DOGWOOD_DOCS) is inserted
  into `file`, either before the line `before` or at the end. `shift` adds that many `#` to every
  heading of the moved text, and `edits` (replace edits without `file`) apply to the moved text
  first.
- delete_file: `file` is removed. delete_dir: the directory `dir` is removed.
- write_file: `file` is written with `text`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

KEEP_CHAPTERS = (
    "README.md",
    "00-introduction.md",
    "01-getting-started.md",
    "02-policy-language.md",
    "03-event-schema.md",
    "04-temporal-expressions.md",
    "05-information-providers.md",
    "06-macros.md",
    "08-formal-specification.md",
    "09-calling-macros.md",
    "10-provider-schema.md",
    "12-cli.md",
)
HEADING = re.compile(r"^(#{1,6})\s")
FENCE = re.compile(r"^\s*(```|~~~)")


def heading_level(line: str) -> int:
    m = HEADING.match(line)
    return len(m.group(1)) if m else 0


def section_bounds(lines: list[str], heading: str) -> tuple[int, int]:
    """[start, end) of the section headed exactly `heading`; the heading must occur once."""
    fenced = False
    starts = []
    marks = []
    for i, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
        if not fenced and heading_level(line):
            marks.append((i, heading_level(line)))
            if line.rstrip("\n") == heading:
                starts.append(i)
    if len(starts) != 1:
        raise ValueError(f"heading {heading!r} found {len(starts)} times")
    start = starts[0]
    level = heading_level(lines[start])
    end = len(lines)
    for i, lvl in marks:
        if i > start and lvl <= level:
            end = i
            break
    return start, end


def replace(text: str, edit: dict, where: str) -> str:
    count = edit.get("count", 1)
    found = text.count(edit["old"])
    if found != count:
        raise ValueError(
            f"{where}: expected {count} of {edit['old'][:80]!r}, found {found}"
        )
    return text.replace(edit["old"], edit["new"])


def apply(out: Path, src: Path, edit: dict) -> None:
    op = edit["op"]
    if op == "delete_dir":
        shutil.rmtree(out / edit["dir"])
        return
    path = out / edit["file"]
    if op == "write_file":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(edit["text"], encoding="utf-8")
        return
    if op == "delete_file":
        path.unlink()
        return
    text = path.read_text(encoding="utf-8")
    if op == "replace":
        text = replace(text, edit, edit["file"])
    elif op == "delete_section":
        lines = text.splitlines(keepends=True)
        start, end = section_bounds(lines, edit["heading"])
        text = "".join(lines[:start] + lines[end:])
    elif op == "move_section":
        source = (
            (src / edit["from"]).read_text(encoding="utf-8").splitlines(keepends=True)
        )
        start, end = section_bounds(source, edit["heading"])
        moved = "".join(source[start:end])
        for inner in edit.get("edits", []):
            moved = replace(moved, inner, f"{edit['from']} (moved)")
        shift = edit.get("shift", 0)
        if shift:
            moved = "".join(
                ("#" * shift + line) if heading_level(line) else line
                for line in moved.splitlines(keepends=True)
            )
        if not moved.endswith("\n"):
            moved += "\n"
        if "before" in edit:
            lines = text.splitlines(keepends=True)
            hits = [
                i for i, line in enumerate(lines) if line.rstrip("\n") == edit["before"]
            ]
            if len(hits) != 1:
                raise ValueError(
                    f"{edit['file']}: anchor {edit['before']!r} found {len(hits)} times"
                )
            text = "".join(lines[: hits[0]]) + moved + "\n" + "".join(lines[hits[0] :])
        else:
            text = text.rstrip("\n") + "\n\n" + moved
    else:
        raise ValueError(f"unknown edit kind {op!r}")
    path.write_text(text, encoding="utf-8")


def build(src: Path, edits: list[dict], out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / "guide").mkdir(parents=True)
    for name in KEEP_CHAPTERS:
        shutil.copyfile(src / "guide" / name, out / "guide" / name)
    shutil.copytree(
        src / "examples",
        out / "examples",
        symlinks=False,
        ignore=shutil.ignore_patterns("regenerate-explain.sh"),
    )
    shutil.copyfile(src.parent / "LICENSE", out / "LICENSE")
    for n, edit in enumerate(edits):
        try:
            apply(out, src, edit)
        except (ValueError, OSError) as exc:
            raise SystemExit(
                f"edit {n} ({edit.get('op')} {edit.get('file', edit.get('dir'))}): {exc}"
            ) from exc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--edits", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    edits = json.loads(a.edits.read_text(encoding="utf-8"))
    build(a.src, edits, a.out)
    files = sorted(p for p in a.out.rglob("*") if p.is_file())
    print(
        json.dumps({"files": len(files), "bytes": sum(p.stat().st_size for p in files)})
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
