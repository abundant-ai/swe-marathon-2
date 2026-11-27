"""Draw the 20 public examples: 10 clean records from each development partition, stratified by source, with `src` and `_meta` removed."""

import collections
import json
import pathlib
import random
import sys

SEED = 20261127
PER_SUITE = 10


def source(record: dict) -> str:
    return next(iter(record["questions"].values()))["src"]


def draw(path: pathlib.Path, rng: random.Random) -> list[dict]:
    rows = [json.loads(line) for line in path.open()]
    clean = [r for r in rows if r["_meta"].get("variant", "clean") == "clean"]
    by_src = collections.defaultdict(list)
    for r in clean:
        by_src[source(r)].append(r)
    exact = {s: len(v) * PER_SUITE / len(clean) for s, v in by_src.items()}
    alloc = {s: int(x) for s, x in exact.items()}
    rank = sorted(exact, key=lambda s: (-(exact[s] - alloc[s]), s))
    for s in rank[: PER_SUITE - sum(alloc.values())]:
        alloc[s] += 1
    picked = []
    for s in sorted(by_src):
        picked += rng.sample(
            sorted(by_src[s], key=lambda r: r["_meta"]["id"]), alloc[s]
        )
    return picked


def public_copy(record: dict) -> dict:
    questions = {
        k: {f: v for f, v in q.items() if f != "src"}
        for k, q in record["questions"].items()
    }
    return {"state": record["state"], "questions": questions}


def main(transfer_dev: str, decision_dev: str, out_dir: str) -> None:
    rng = random.Random(SEED)
    picked = draw(pathlib.Path(transfer_dev), rng) + draw(
        pathlib.Path(decision_dev), rng
    )
    random.Random(SEED).shuffle(picked)
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "public-20.jsonl").open("w") as f:
        for r in picked:
            f.write(json.dumps(public_copy(r)) + "\n")
    ids = [{"id": r["_meta"]["id"], "src": source(r)} for r in picked]
    (out / "public-20.ids.json").write_text(
        json.dumps({"seed": SEED, "records": ids}, indent=1)
    )
    print(json.dumps(collections.Counter(i["src"] for i in ids), indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
