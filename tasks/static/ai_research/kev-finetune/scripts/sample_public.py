"""Draw 20 clean transfer-v4 development records, stratified by source (largest remainder, fixed seed)."""

import collections
import json
import pathlib
import random
import sys

SEED = 20261127
TOTAL = 20
TIE_ORDER = ["mmlu", "sciq", "emotion", "qnli", "paws", "tweet_offensive"]

src_path, out_dir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
rows = [json.loads(line) for line in src_path.open()]
clean = [r for r in rows if r["_meta"].get("variant") == "clean"]
by_src = collections.defaultdict(list)
for r in clean:
    (q,) = r["questions"].values()
    by_src[q["src"]].append(r)

exact = {s: len(v) * TOTAL / len(clean) for s, v in by_src.items()}
alloc = {s: int(x) for s, x in exact.items()}
rank = sorted(
    exact,
    key=lambda s: (
        -(exact[s] - alloc[s]),
        TIE_ORDER.index(s) if s in TIE_ORDER else -1,
    ),
)
for s in rank[: TOTAL - sum(alloc.values())]:
    alloc[s] += 1

rng = random.Random(SEED)
picked = []
for s in sorted(by_src):
    picked += rng.sample(sorted(by_src[s], key=lambda r: r["_meta"]["id"]), alloc[s])

out_dir.mkdir(parents=True, exist_ok=True)
with (out_dir / "public-20.jsonl").open("w") as f:
    for r in picked:
        f.write(json.dumps({"state": r["state"], "questions": r["questions"]}) + "\n")
(out_dir / "public-20.ids.json").write_text(
    json.dumps(
        {
            "seed": SEED,
            "source_file": src_path.name,
            "allocation": alloc,
            "ids": [r["_meta"]["id"] for r in picked],
        },
        indent=1,
    )
)
print(json.dumps(alloc, indent=1))
