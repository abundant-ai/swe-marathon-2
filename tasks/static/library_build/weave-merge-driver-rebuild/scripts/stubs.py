"""Trivial merge programs with the driver's command line, used to filter and net cases.

Usage: python3 -I stubs.py MODE BASE OURS THEIRS -o OUT -l 7 -p PATH

Modes (none of them merges by entity):
  take_ours, take_theirs, take_base   copy one input, exit 0
  git_plain                           git merge-file -p OURS BASE THEIRS; exit 0 clean, 1 conflict, 2 error
  git_labelled_hint                   git merge-file -p --diff3 -L ours -L base -L theirs, plus the hint line
  git_labelled_clean                  the same text, always exit 0
  git_no_hint                         git labelled diff3 without the hint line
  always_box                          one whole-file box (common edges cut), plus the hint, exit 1
  always_error                        write nothing, exit 2
  routing_only                        exit 2 on a NUL in the first 8192 bytes or invalid UTF-8, else git_labelled_hint
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEACH = "weave: run 'weave explain "


def teach(content: str, path: str, width: int = 7) -> str:
    """The driver's hint on the first closing marker line (same rule as the original's)."""
    close = ">" * width
    out, done = [], False
    for piece in content.splitlines(keepends=True):
        line = piece.rstrip("\n").rstrip("\r")
        is_close = (
            line.startswith(close)
            and not line[len(close) :].startswith(">")
            and TEACH not in line
        )
        if not done and is_close:
            out.append(
                line
                + f" · {TEACH}{path}' for per-hunk detail, 'weave check' to verify your resolution"
                + piece[len(line) :]
            )
            done = True
        else:
            out.append(piece)
    return "".join(out)


def git_merge(base: str, ours: str, theirs: str, labelled: bool) -> tuple[int, bytes]:
    """Run git merge-file on the three paths; return git's exit code and stdout."""
    cmd = ["git", "merge-file", "-p"]
    if labelled:
        cmd += ["--diff3", "-L", "ours", "-L", "base", "-L", "theirs"]
    r = subprocess.run([*cmd, ours, base, theirs], check=False, capture_output=True)
    return r.returncode, r.stdout


def box(base: str, ours: str, theirs: str, path: str) -> str:
    """One box over the whole file, with the lines all three share at the edges left outside."""
    sides = [t.splitlines(keepends=True) for t in (ours, base, theirs)]
    pre = 0
    while (
        all(pre < len(s) for s in sides)
        and sides[0][pre] == sides[1][pre] == sides[2][pre]
    ):
        pre += 1
    suf = 0
    while (
        all(suf < len(s) - pre for s in sides)
        and sides[0][-1 - suf] == sides[1][-1 - suf] == sides[2][-1 - suf]
    ):
        suf += 1
    mid = [s[pre : len(s) - suf] for s in sides]

    def lines(chunk: list[str]) -> str:
        text = "".join(chunk)
        return text if not text or text.endswith("\n") else text + "\n"

    body = (
        "<<<<<<< ours\n"
        + lines(mid[0])
        + "||||||| base\n"
        + lines(mid[1])
        + "=======\n"
        + lines(mid[2])
        + ">>>>>>> theirs\n"
    )
    return teach(
        "".join(sides[0][:pre]) + body + "".join(sides[0][len(sides[0]) - suf :]), path
    )


def main() -> int:
    """Parse the driver's command line and run one mode."""
    mode, base, ours, theirs = sys.argv[1:5]
    rest = sys.argv[5:]
    out = rest[rest.index("-o") + 1]
    path = rest[rest.index("-p") + 1]
    raw = [Path(p).read_bytes() for p in (base, ours, theirs)]

    def write(data: bytes) -> None:
        with open(out, "wb") as fh:
            fh.write(data)

    if mode in ("take_ours", "take_theirs", "take_base"):
        write(raw[{"take_base": 0, "take_ours": 1, "take_theirs": 2}[mode]])
        return 0
    if mode == "always_error":
        return 2
    if mode == "routing_only":
        bad = any(0 in r[:8192] for r in raw)
        try:
            [r.decode("utf-8") for r in raw]
        except UnicodeDecodeError:
            bad = True
        if bad:
            return 2
        mode = "git_labelled_hint"
    if mode == "always_box":
        try:
            texts = [r.decode("utf-8") for r in raw]
        except UnicodeDecodeError:
            return 2
        write(box(texts[0], texts[1], texts[2], path).encode())
        return 1
    labelled = mode != "git_plain"
    code, text = git_merge(base, ours, theirs, labelled)
    if code < 0 or code > 127:
        return 2
    if mode in ("git_labelled_hint", "git_labelled_clean"):
        text = teach(text.decode("utf-8", "replace"), path).encode()
    write(text)
    if mode == "git_labelled_clean":
        return 0
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
