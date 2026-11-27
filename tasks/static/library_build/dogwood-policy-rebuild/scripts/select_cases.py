"""Keep the candidate cases that a trivial program cannot pass, and write the private case set.

Usage: python3 -I select_cases.py --candidates DIR --run RUN.json --out DIR [--seed S] [--cap FAMILY=UNITS]...

RUN.json is `run_cases.py`'s record of the release build over the candidates (several repeats).
A case is kept only when its answer is stable after normalisation, and only in a unit (a single
case, or a pair that counts only when both members pass) that none of these programs passes:
- one that prints nothing, with any exit status (cases whose standard output is empty);
- one that prints, for each command, the output that command gives most often ("constant"
  outputs: the accept line of `validate`, `check-parse`'s plain count, a schema's "valid" line);
- one that prints DENY, or ALLOW with the first rule, for every event of a trace;
- `format` as `cat` (cases whose formatted output is the input file).
A case with an empty, constant, uniform or unchanged output is paired with a case of the same
family and command that has none of these; when none is left, it is dropped. Paired B and K cases
keep their pairs, which are dropped when one program passes both members.

Writes OUT/cases.jsonl, OUT/bundles/ (the bundles the kept cases use), OUT/manifest.json (the
candidates' manifest, plus what selection kept and dropped) and OUT/bundle_tags.json.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

VERDICT = re.compile(r"^@-?\d+ \(time point \d+\): (DENY|ALLOW  \[rules: [0-9, ]+\])$")


HASH_ORDER = re.compile(r"cycle in [^\n]*containing")


def route(c: dict) -> str:
    args = c["args"]
    if c["bundle"] == "cli":
        return "cli"
    if args[0] == "schema":
        return f"schema-{args[1]}"
    if args[0] == "lower":
        emit = args[args.index("--emit") + 1] if "--emit" in args else "both"
        return f"lower-{emit}"
    if args[0] == "explain" and "--policy-schema" not in args:
        return "explain-bare"
    if args[0] == "check-parse" and args[1] == "typo.dw":
        return "check-parse"
    return args[0]


def stub_group(c: dict) -> str:
    """The command a table-driven stub sees (`checks/stubs.py` keys its answers the same way):
    the subcommand, `--emit` form or schema part, and the `--format` value."""
    args = c["args"]
    if args and args[0] == "schema":
        head = f"schema-{args[1] if len(args) > 1 else ''}"
    elif args and args[0] == "lower":
        head = f"lower-{args[args.index('--emit') + 1] if '--emit' in args else 'both'}"
    elif args and args[0] == "explain" and "--policy-schema" not in args:
        head = "explain-bare"
    else:
        head = args[0] if args else ""
    i = args.index("--format") + 1 if "--format" in args else -1
    fmt = args[i] if 0 < i < len(args) else "human"
    return f"{head}/{fmt}"


def uniform_stream(text: str) -> str | None:
    """'DENY' or 'ALLOW <rules>' when every line of a human replay stream is that verdict and
    nothing else is printed; None otherwise."""
    lines = [line for line in text.splitlines() if line.strip()]
    kinds = set()
    for line in lines:
        m = VERDICT.match(line)
        if not m:
            return None
        kinds.add(m.group(1))
    return kinds.pop() if len(kinds) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--keep-prefix",
        action="append",
        default=[],
        help="bundles whose units are never capped",
    )
    ap.add_argument(
        "--cap",
        action="append",
        default=[],
        help="FAMILY=UNITS, at most that many units",
    )
    a = ap.parse_args()
    cand = [
        json.loads(x)
        for x in (a.candidates / "cases.jsonl").read_text().splitlines()
        if x.strip()
    ]
    run = json.loads(a.run.read_text())
    dropped: Counter = Counter()

    # 1. Stable answers only.
    gold = {}
    kept = []
    for c in cand:
        r = run.get(c["id"])
        if r is None:
            dropped["not run"] += 1
            continue
        answers = {(x["rc"], x["norm"]) for x in r["runs"]}
        if len(answers) != 1:
            dropped["unstable"] += 1
            continue
        if any(HASH_ORDER.search(x["norm"]) for x in r["runs"]):
            # The member of a cycle that the message names depends on the build's hash order,
            # which changes from run to run; three equal runs are luck, not one answer.
            dropped["names one member of a cycle"] += 1
            continue
        gold[c["id"]] = answers.pop()
        kept.append(c)

    # 2. What makes a case passable by a trivial program.
    groups: dict[tuple, Counter] = defaultdict(Counter)
    for c in kept:
        groups[stub_group(c)][gold[c["id"]]] += 1
    constant = set()
    for key, counts in groups.items():
        total = sum(counts.values())
        (top, top_n), *_ = counts.most_common(1)
        if (
            top_n >= 2
        ):  # what a program printing each command's most common answer passes
            constant.add((key, top))
        for answer, n in counts.items():
            if n >= max(3, 0.02 * total):
                constant.add((key, answer))
    human = {c["id"]: gold[c["id"]][1] for c in kept if c["fmt"] == "human"}

    def weakness(c: dict) -> str | None:
        rc, out = gold[c["id"]]
        if not out.strip():
            return "empty"
        if (stub_group(c), (rc, out)) in constant:
            return "constant"
        if groups[stub_group(c)][(rc, out)] >= 2:
            return "shared"
        cmd = c["args"][0] if c["args"] else ""
        if cmd == "replay":
            twin = human.get(c["id"].rsplit("/", 1)[0] + "/human")
            if twin is not None and uniform_stream(twin):
                return f"uniform {uniform_stream(twin)}"
        if cmd == "format" and len(c["args"]) > 1:
            # the file `format` reads, when it is one (not `--help` or a folder)
            name = c.get("stdin") if c["args"][1] == "-" else c["args"][1]
            path = a.candidates / "bundles" / c["bundle"] / (name or "")
            if name and path.is_file() and out == path.read_text(errors="replace"):
                return "unchanged"
        return None

    weak = {c["id"]: weakness(c) for c in kept}

    # 3. Declared pairs: drop a pair one program passes whole.
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for c in kept:
        if c.get("pair"):
            by_pair[c["pair"]].append(c)
    for pid, members in by_pair.items():
        reasons = {weak[m["id"]] for m in members}
        if len(reasons) == 1 and None not in reasons:
            for m in members:
                m["drop"] = f"pair passable ({reasons.pop()})"

    # 4. Pair the other weak cases with strong ones of the same family and command.
    rng = random.Random(a.seed)
    strong_pool: dict[tuple, list[dict]] = defaultdict(list)
    needy: dict[tuple, list[dict]] = defaultdict(list)
    for c in kept:
        if c.get("pair") or c.get("drop"):
            continue
        key = (c["family"], route(c), c["fmt"])
        if c["bundle"] == "cli":
            key = (c["family"], "cli", c["fmt"])
        (needy if weak[c["id"]] else strong_pool)[key].append(c)
    made = 0
    unpaired: list[dict] = []
    for key in sorted(needy):
        pool = strong_pool.get(key, [])
        rng.shuffle(pool)
        for c in sorted(needy[key], key=lambda x: x["id"]):
            if not pool:
                unpaired.append(c)
                continue
            partner = pool.pop()
            pid = f"{key[0]}:{key[1]}/{key[2]}:{made}"
            c["pair"] = partner["pair"] = pid
            made += 1
    # F (format, check-parse, schema, the command line) holds commands whose successful answers
    # are mostly the same line; a weak F case with no partner on its own command takes a strong
    # F case of another command in the same format, still unpaired.
    spare: dict[str, list[dict]] = defaultdict(list)
    for key in sorted(strong_pool):
        if key[0] == "F":
            spare[key[2]].extend(strong_pool[key])
    for fmt in sorted(spare):
        rng.shuffle(spare[fmt])
    for c in unpaired:
        pool = spare.get(c["fmt"], []) if c["family"] == "F" else []
        if not pool:
            c["drop"] = f"no partner ({weak[c['id']]})"
            continue
        partner = pool.pop()
        pid = f"F:any/{c['fmt']}:{made}"
        c["pair"] = partner["pair"] = pid
        made += 1

    final = []
    for c in kept:
        if c.get("drop"):
            dropped[c.pop("drop")] += 1
            continue
        final.append(c)

    # 5. Cap the larger families, by whole units, so the grader's run stays short.
    caps = dict(x.split("=", 1) for x in a.cap)
    units_of: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in final:
        units_of[c["family"]][c.get("pair") or c["id"]].append(c)
    capped = []
    for fam in sorted(units_of):
        names = sorted(units_of[fam])
        # Units holding a case of a kept bundle (a restriction template, the command line)
        # are never capped: they may be the only cases of what they check.
        kept_units = [
            n
            for n in names
            if any(
                c["bundle"].startswith(tuple(a.keep_prefix)) for c in units_of[fam][n]
            )
        ]
        rest = [n for n in names if n not in kept_units]
        limit = max(0, int(caps.get(fam, len(names))) - len(kept_units))
        if len(rest) > limit:
            rng.shuffle(rest)
            dropped[f"over the {fam} cap"] += sum(
                len(units_of[fam][n]) for n in rest[limit:]
            )
            rest = rest[:limit]
        for n in sorted(kept_units + rest):
            capped.extend(units_of[fam][n])
    final = capped

    # 6. Capping changes which answer each command gives most often. A program that prints each
    # command's most common answer (one given at least twice) can pass a unit only when every
    # member's answer is given at least twice for its command, so such units are dropped; a unit
    # with one answer of its own is safe whatever that program picks.
    counts: dict[str, Counter] = defaultdict(Counter)
    for c in final:
        counts[stub_group(c)][gold[c["id"]]] += 1
    members: dict[str, list[dict]] = defaultdict(list)
    for c in final:
        members[c.get("pair") or c["id"]].append(c)
    shared = {
        u
        for u, ms in members.items()
        if all(counts[stub_group(m)][gold[m["id"]]] >= 2 for m in ms)
    }
    dropped["answers all given elsewhere too"] += sum(len(members[u]) for u in shared)
    final = [c for c in final if (c.get("pair") or c["id"]) not in shared]

    # 7. Write the case set and the bundles it uses.
    out_bundles = a.out / "bundles"
    if out_bundles.exists():
        raise SystemExit(f"{out_bundles} exists; select into an empty directory")
    out_bundles.mkdir(parents=True)
    used = sorted({c["bundle"] for c in final})
    for name in used:
        shutil.copytree(a.candidates / "bundles" / name, out_bundles / name)
    with (a.out / "cases.jsonl").open("w") as f:
        for c in final:
            f.write(json.dumps(c, sort_keys=True) + "\n")
    tags = json.loads((a.candidates / "bundle_tags.json").read_text())
    (a.out / "bundle_tags.json").write_text(
        json.dumps({k: tags[k] for k in used if k in tags}, indent=0, sort_keys=True)
        + "\n"
    )
    manifest = json.loads((a.candidates / "manifest.json").read_text())
    fams = Counter(c["family"] for c in final)
    units = defaultdict(set)
    for c in final:
        units[c["family"]].add(c.get("pair") or c["id"])
    manifest["selection"] = {
        "candidates": len(cand),
        "kept": len(final),
        "bundles": len(used),
        "dropped": dict(sorted(dropped.items())),
        "paired_here": made,
        "families": dict(sorted(fams.items())),
        "units": {k: len(v) for k, v in sorted(units.items())},
    }
    (a.out / "manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    )
    print(json.dumps(manifest["selection"], sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
