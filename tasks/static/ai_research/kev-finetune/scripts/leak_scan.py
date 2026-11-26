"""Usage: leak_scan.py <shipped-tree> <transfer-v4 dev.jsonl> <transfer-v4 test.jsonl> <public-20.jsonl>; exits 1 on any hit."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

MIN_CHARS = 40
SEEDS = ("v3-legacy-transfer", "v3-composition-transfer", "v3-locked", "20260920-eval")


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
        texts.append(question.get("instructions", ""))
    return [t.strip() for t in texts if len(t.strip()) >= MIN_CHARS]


def needles(dev: pathlib.Path, test: pathlib.Path, public: pathlib.Path) -> set[str]:
    public_texts = {t for line in public.open() for t in record_texts(json.loads(line))}
    found = set()
    for path in (dev, test):
        for line in path.open():
            found.update(record_texts(json.loads(line)))
    shared = {
        t
        for t in found
        if t.startswith(
            ("Which option", "Which emotion", "Is this post", "Apply the policy")
        )
    }
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
    tree, dev, test, public = (pathlib.Path(a) for a in argv)
    text_needles = needles(dev, test, public)
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
