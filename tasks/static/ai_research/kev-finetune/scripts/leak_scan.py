"""Usage: leak_scan.py <shipped-tree> <public-20.jsonl> <held-out.jsonl>...; exits 1 on any hit."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

MIN_CHARS = 40
SEEDS = (
    "v3-legacy-transfer",
    "v3-composition-transfer",
    "v3-locked",
    "20260920-eval",
    "v3-control",
    "v3-composition",
    "v7-composition",
)


def strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


def record_texts(record: dict) -> list[str]:
    texts = strings(record["state"])
    for question in record["questions"].values():
        texts += strings(question.get("instructions", ""))
    return [t.strip() for t in texts if len(t.strip()) >= MIN_CHARS]


def needles(public: pathlib.Path, held_out: list[pathlib.Path]) -> set[str]:
    public_texts = {t for line in public.open() for t in record_texts(json.loads(line))}
    counts: dict[str, int] = {}
    for path in held_out:
        for line in path.open():
            for t in set(record_texts(json.loads(line))):
                counts[t] = counts.get(t, 0) + 1
    found = set(counts)
    # Text shared by many records is a question template, not record material.
    shared = {t for t, n in counts.items() if n > 3}
    raw = found - public_texts - shared
    escaped = {json.dumps(t, ensure_ascii=True)[1:-1] for t in raw} | {
        json.dumps(t, ensure_ascii=False)[1:-1] for t in raw
    }
    return raw | escaped


def grep(tree: pathlib.Path, patterns: set[str]) -> list[str]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write("\n".join(sorted(p.replace("\n", " ") for p in patterns)) + "\n")
    result = subprocess.run(
        ["grep", "-rlF", "-f", handle.name, str(tree)],
        check=False,
        capture_output=True,
        text=True,
    )
    pathlib.Path(handle.name).unlink()
    return result.stdout.split()


def main(argv: list[str]) -> int:
    tree, public, *held_out = (pathlib.Path(a) for a in argv)
    text_needles = needles(public, held_out)
    print(f"text needles: {len(text_needles)}; seed needles: {len(SEEDS)}")
    hits = 0
    for name, patterns in (("text", text_needles), ("seed", set(SEEDS))):
        for file in grep(tree, patterns):
            body = pathlib.Path(file).read_text(errors="replace")
            matched = sorted(p for p in patterns if p in body)
            hits += len(matched)
            print(
                f"{name} hit in {file}: {len(matched)} needles, e.g. {matched[0][:100]!r}"
            )
    print("clean" if hits == 0 else f"{hits} needle hits")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
