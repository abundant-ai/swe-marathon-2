"""Sweep agent-visible text for words that frame the work as an exam or reveal the setup.

Usage: python3 -I cue_words.py FILE_OR_DIR [...]
Prints one line per hit (file:line: word: text) and exits 1 when anything is found. A short
whitelist keeps the product's own words (the hint line) and the domain sense of "test file".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = [
    r"evaluat\w*",
    r"benchmark\w*",
    r"\bgrad(?:e|es|er|ers|ed|ing)\b",
    r"\bscor(?:e|es|ed|ing)\b",
    r"test cases?",
    r"\bhidden\b",
    r"held[- ]out",
    r"\breference\b",
    r"\boracle\b",
    r"\bgold(?:en)?\b",
    r"told apart",
    r"indistinguishab\w*",
    r"exactly as",
    r"identical to",
    r"behaves? exactly like",
    r"byte for byte",
    r"\bbudget\b",
    r"\bdeadline\b",
    r"\bsession\b",
    r"\bverifier\b",
    r"\bcorpus\b",
    r"\brubric\b",
    r"\bprobation\b",
    r"\bspike\b",
    r"\bverif(?:y|ies|ied|ication)\b",
    r"\bchecker\b",
]
# Words that are domain terms in the specification (the driver compares lines, a result passes the
# driver's own checks) but read as exam framing in the brief: swept in instruction.md only.
BRIEF_ONLY = [
    r"\bcompar(?:e|es|ed|ing|ison)\b",
    r"\bpass(?:es|ed)? (?:the|all|every)\b",
    r"\bmatch(?:es|ed|ing)?\b",
    r"\bsame as\b",
]
WHITELIST = [
    "'weave check' to verify your resolution",  # the product's own hint line
]
RX = re.compile("|".join(PATTERNS), re.IGNORECASE)
RX_BRIEF = re.compile("|".join(PATTERNS + BRIEF_ONLY), re.IGNORECASE)


def sweep(path: Path) -> list[str]:
    """Hits in one text file."""
    hits = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for n, line in enumerate(text.splitlines(), 1):
        clean = line
        for ok in WHITELIST:
            clean = clean.replace(ok, "")
        rx = RX_BRIEF if path.name == "instruction.md" else RX
        for m in rx.finditer(clean):
            hits.append(f"{path}:{n}: {m.group(0)}: {line.strip()[:120]}")
    return hits


def main() -> int:
    """Sweep every file given, recursing into directories."""
    hits = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
        for f in files:
            hits.extend(sweep(f))
    print("\n".join(hits) if hits else "no hits")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
