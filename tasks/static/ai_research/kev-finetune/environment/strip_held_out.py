"""Remove from the agent's copy of Kev the generators behind transfer-v4's held-out rule and policy questions."""

import ast
import re
import sys
from pathlib import Path

HELD_SHAPES = (
    "held_and_or",
    "held_or_not",
    "held_conditional",
    "final_combination",
    "final_negation",
    "final_exception",
)
HELD_FAMILIES = ("authorization", "deadline")


def swap(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        sys.exit(f"expected one copy of {old!r}")
    return text.replace(old, new)


def strip_composition(path: Path) -> None:
    text = path.read_text()
    for shape in HELD_SHAPES:
        text, n = re.subn(rf'^    "{shape}": .*\n', "", text, flags=re.MULTILINE)
        if n != 1:
            sys.exit(f"shape {shape} not found once")
    text = swap(text, "DEV_SHAPES = tuple(list(SHAPES)[8:11])", "DEV_SHAPES = ()")
    text = swap(text, "TEST_SHAPES = tuple(list(SHAPES)[11:])", "TEST_SHAPES = ()")
    text = swap(
        text,
        "HELD_OUT_KEYS = set().union(*(structure_keys(SHAPES[s]) for s in DEV_SHAPES + TEST_SHAPES))",
        "HELD_OUT_KEYS = frozenset()",
    )
    text, n = re.subn(r'^    2: "Approval requires .*\n', "", text, flags=re.MULTILINE)
    if n != 1:
        sys.exit("locked wrapper not found once")
    text = swap(
        text, "2 = reserved for the\n    locked test, ", "2 = not\n    available, "
    )
    path.write_text(text)


def strip_contrastive(path: Path) -> None:
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    spans = [
        (node.lineno - 1, node.end_lineno)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {f"family_{f}" for f in HELD_FAMILIES}
    ]
    if len(spans) != len(HELD_FAMILIES):
        sys.exit("held-out family functions not found")
    for start, end in sorted(spans, reverse=True):
        del lines[start:end]
    text = "".join(lines)
    for family in HELD_FAMILIES:
        text = swap(text, f' "{family}": family_{family},', "")
    path.write_text(text)


def main(root: str) -> None:
    kev = Path(root) / "kev"
    strip_composition(kev / "composition.py")
    strip_contrastive(kev / "contrastive.py")
    shipped = "".join(
        p.read_text(errors="ignore")
        for p in Path(root).rglob("*")
        if p.is_file() and p.suffix in {".py", ".md"}
    )
    for needle in (
        *HELD_SHAPES,
        "Approval requires the following rule",
        "sole authorization",
        "late but accepted",
        "family_authorization",
        "family_deadline",
    ):
        if needle in shipped:
            sys.exit(f"{needle!r} is still shipped")


if __name__ == "__main__":
    main(sys.argv[1])
