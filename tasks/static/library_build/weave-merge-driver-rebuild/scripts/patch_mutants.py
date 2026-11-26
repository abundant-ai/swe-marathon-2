"""Apply one feature-removal mutant to an extracted weave source tree (v0.7.1).

Usage: python3 -I patch_mutants.py SRC_ROOT MUTANT
MUTANT is one of:
  gate   every fail-closed check passes: verify::verify, verify::structured_data,
         verify::duplicate_keys (the keys backstop) and merge::iota_refusal return None
  elem   the element-union rung refuses every collection (elements::union returns None)
  place  additions sharing one anchor are ordered ours first, in ours' order, instead of by key
Each edit must match exactly once, or the script stops without writing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def early_none(src: str, signature: str) -> str:
    """Insert `return None;` as the first statement of the function whose signature starts here."""
    start = src.index(signature)
    if src.count(signature) != 1:
        raise SystemExit(f"signature not unique: {signature}")
    brace = src.index("{\n", start)
    return src[: brace + 2] + "    return None;\n" + src[brace + 2 :]


PLACE_OLD = "ready.sort_by(|a, b| key_of[a].cmp(key_of[b]));"
PLACE_REST_OLD = "rest.sort_by(|a, b| key_of[a].cmp(key_of[b]));"
OURS_FIRST = (
    "|i: &usize| (triples[*i].side_idx(Side::Ours).is_none(), "
    "triples[*i].side_idx(Side::Ours).or(triples[*i].side_idx(Side::Theirs))"
    ".map(|x| arena.get(x).position).unwrap_or(0))"
)


def main() -> None:
    """Patch the tree in place."""
    root, mutant = Path(sys.argv[1]), sys.argv[2]
    core = root / "crates/weave-core/src"
    edits: dict[Path, str] = {}

    def load(p: Path) -> str:
        return edits.get(p, p.read_text())

    if mutant == "gate":
        v = core / "verify.rs"
        text = load(v)
        for sig in (
            "pub fn verify(",
            "pub fn structured_data(",
            "pub fn duplicate_keys(",
        ):
            text = early_none(text, sig)
        edits[v] = text
        m = core / "merge.rs"
        edits[m] = early_none(load(m), "fn iota_refusal(")
    elif mutant == "elem":
        e = core / "elements.rs"
        edits[e] = early_none(load(e), "pub(crate) fn union(")
    elif mutant == "place":
        p = core / "v2/plan.rs"
        text = load(p)
        for old in (PLACE_OLD, PLACE_REST_OLD):
            if text.count(old) != 1:
                raise SystemExit(f"not found once: {old}")
        text = text.replace(PLACE_OLD, f"ready.sort_by_key({OURS_FIRST});")
        text = text.replace(PLACE_REST_OLD, f"rest.sort_by_key({OURS_FIRST});")
        edits[p] = text
    else:
        raise SystemExit(f"unknown mutant {mutant}")
    for path, text in edits.items():
        path.write_text(text)
        print(f"patched {path.relative_to(root)}")
    if not re.match(r"^(gate|elem|place)$", mutant):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
