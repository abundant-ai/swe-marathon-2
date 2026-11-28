"""Keep the candidate cases that a trivial program cannot pass, and write the private case set.

Usage: python3 -I select_cases.py --candidates DIR --run RUN.json --shadow-run SHADOW.json --out DIR
       [--seed S] [--keep-prefix P]... [--cap FAMILY=UNITS]... [--exclude IDS] [--keep IDS]
       [--fates FILE]

RUN.json is `run_cases.py`'s record of the release build over the candidates (several repeats);
SHADOW.json its record over the candidates' history-free shadows (DIR/shadow, `make_cases.py`). A
case is kept only when its answer is stable after normalisation, and only in a unit (a single
case, or a pair that counts only when all its members pass) that no one of these programs passes
whole:
- `empty`: prints nothing, with any exit status;
- `table`: prints, for each command, an answer that command gives at least twice (its constant
  outputs: the accept line of `validate`, `check-parse`'s plain count, a schema's "valid" line);
- `cli-shell`: knows the command line's own texts (help, version, usage and I/O errors), which
  depend on the arguments alone;
- `uniform:<verdict>`: prints that verdict (DENY, DENY with rules, or ALLOW with rules) for every
  decision of a trace; `last-allow`: DENY for every decision but the last, ALLOW with rule 0;
- `history-free:drop` and `history-free:false`: the release build's own answer over the policy
  with its temporal conditions dropped, or read as false (`history_free.py`), which is what an
  engine without history prints; a policy with no temporal condition is passed by both;
- `cat`: `format` printing its input.
A case that some program passes is paired with a case of the same family and command that none
passes (rarest first: a case that evidences an id of `checks/features.json` few cases evidence
takes a partner before the others); when none is left, it is dropped. Declared B and K pairs keep
their members, and are dropped when one program passes them whole. `--cap` limits a family's
units, but never drops a unit of a `--keep-prefix` bundle or a standard-input case, nor the units
that give each id its minimum number of cases (as `checks/coverage.py` counts them) plus two.

Writes OUT/cases.jsonl, OUT/bundles/ (the bundles the kept cases use), OUT/manifest.json (the
candidates' manifest, plus what selection kept and dropped) and OUT/bundle_tags.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import history_free

CHECKS = Path(__file__).resolve().parent.parent / "checks"
_spec = importlib.util.spec_from_file_location(
    "dogwood_coverage", CHECKS / "coverage.py"
)
cov = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cov)
MARGIN = 2  # cases beyond an id's minimum, against the units step 6 drops after the cap
UNIT_MAX = 4  # cases in a unit that a weak case joins (step 4b)


def evidence(cases: list[dict], gold: dict, candidates: Path, tags: dict) -> dict:
    """For each counted feature and restriction id of `checks/features.json`, its minimum number
    of cases and the cases that evidence it the way `checks/coverage.py` counts them (a
    feature's use, a restriction's refusal)."""
    out = {}
    inp: dict[str, dict] = {}
    for f in json.loads((CHECKS / "features.json").read_text()):
        if f["kind"] == "out_of_scope" or f.get("unchecked"):
            continue
        routes = set(f.get("routes") or [])
        detect = cov.alternatives(f)
        errs = [alt["error"] for alt in detect if alt.get("error")]
        has_shape = any(k != "error" for alt in detect for k in alt)
        found = []
        for c in cases:
            if routes and cov.route(c["args"]) not in routes:
                continue
            rc, norm = gold[c["id"]]
            msg = any(
                e.get("message_substring") and e["message_substring"] in norm
                for e in errs
            )
            t = tags.get(c["bundle"]) or {}
            targeted = t.get("kind") == f["id"]
            if has_shape and not targeted and c["id"] not in inp:
                inp[c["id"]] = cov.inputs(candidates, c)
            hit = targeted or (
                has_shape and cov.matches(detect, inp[c["id"]], t.get("tags") or [])
            )
            if f["kind"] == "restriction":
                ok = (
                    msg
                    if targeted and errs
                    else (hit and (msg or rc != 0)) or (not has_shape and msg)
                )
            else:
                ok = (hit and rc == 0) or msg
            if ok:
                found.append(c["id"])
        need = 1 if f["kind"] == "restriction" else f.get("min_cases", 3)
        out[f["id"]] = (need, found)
    return out


VERDICT = re.compile(
    r"^@-?\d+ \(time point \d+\): (DENY(?:  \[rules: [0-9, ]+\])?|ALLOW  \[rules: [0-9, ]+\])$"
)
LINE = re.compile(r"^@-?\d+ \(time point \d+\): ")


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


def last_allow(text: str) -> bool:
    """Whether a human replay stream is DENY for every decision but the last, which is ALLOW with
    rule 0, and nothing else is printed."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or not all(LINE.match(line) for line in lines):
        return False
    verdicts = [LINE.sub("", line) for line in lines]
    return verdicts[-1] == "ALLOW  [rules: 0]" and all(
        v == "DENY" for v in verdicts[:-1]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--shadow-run", required=True, type=Path)
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
    ap.add_argument(
        "--fates", type=Path, help="write each candidate's fate (kept, or why not)"
    )
    ap.add_argument(
        "--exclude",
        type=Path,
        help="case ids to leave out, one a line (the leak scan's findings on the candidates)",
    )
    ap.add_argument(
        "--keep",
        type=Path,
        help="case ids to keep when they can be (a mutant's only killers), one a line",
    )
    a = ap.parse_args()
    cand = [
        json.loads(x)
        for x in (a.candidates / "cases.jsonl").read_text().splitlines()
        if x.strip()
    ]
    run = json.loads(a.run.read_text())
    dropped: Counter = Counter()
    fate: dict[str, str] = {}
    excluded = set(a.exclude.read_text().split()) if a.exclude else set()
    keep = set(a.keep.read_text().split()) if a.keep else set()

    # 1. Stable answers only.
    gold = {}
    kept = []
    for c in cand:
        if c["id"] in excluded:
            dropped["excluded"] += 1
            fate[c["id"]] = "excluded"
            continue
        r = run.get(c["id"])
        if r is None:
            dropped["not run"] += 1
            fate[c["id"]] = "not run"
            continue
        answers = {(x["rc"], x["norm"]) for x in r["runs"]}
        if len(answers) != 1:
            dropped["unstable"] += 1
            fate[c["id"]] = "unstable"
            continue
        if any(HASH_ORDER.search(x["norm"]) for x in r["runs"]):
            # The member of a cycle that the message names depends on the build's hash order,
            # which changes from run to run; three equal runs are luck, not one answer.
            dropped["names one member of a cycle"] += 1
            fate[c["id"]] = "names one member of a cycle"
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
    shadow = json.loads(a.shadow_run.read_text())
    temporal_free: dict[str, bool] = {}

    def no_history(bundle: str) -> bool:
        """Whether the bundle's policy has no temporal condition at all."""
        if bundle not in temporal_free:
            policy = a.candidates / "bundles" / bundle / "policy.dw"
            text = policy.read_text(encoding="utf-8") if policy.is_file() else ""
            temporal_free[bundle] = history_free.rewrite(text, "drop") is None
        return temporal_free[bundle]

    def programs(c: dict) -> set[str]:
        """The trivial programs that pass `c`, read off its recorded answer."""
        rc, out = gold[c["id"]]
        passed: set[str] = set()
        if not out.strip():
            passed.add("empty")
        if (stub_group(c), (rc, out)) in constant or groups[stub_group(c)][
            (rc, out)
        ] >= 2:
            passed.add("table")
        if c["bundle"] == "cli":
            passed.add("cli-shell")
        cmd = c["args"][0] if c["args"] else ""
        if cmd == "replay":
            twin = human.get(c["id"].rsplit("/", 1)[0] + "/human")
            if twin is not None:
                if uniform_stream(twin):
                    passed.add(f"uniform:{uniform_stream(twin)}")
                if last_allow(twin):
                    passed.add("last-allow")
            if no_history(c["bundle"]):
                passed |= {f"history-free:{v}" for v in history_free.VARIANTS}
            for v in history_free.VARIANTS:
                r = shadow.get(f"{c['id']}#hf-{v}")
                if r and {(x["rc"], x["norm"]) for x in r["runs"]} == {(rc, out)}:
                    passed.add(f"history-free:{v}")
        if cmd == "format" and len(c["args"]) > 1:
            # the file `format` reads, when it is one (not `--help` or a folder)
            name = c.get("stdin") if c["args"][1] == "-" else c["args"][1]
            path = a.candidates / "bundles" / c["bundle"] / (name or "")
            if name and path.is_file() and out == path.read_text(errors="replace"):
                passed.add("cat")
        return passed

    passers = {c["id"]: programs(c) for c in kept}
    weak = {cid: (", ".join(sorted(p)) if p else None) for cid, p in passers.items()}

    def passable(members: list[dict]) -> set[str]:
        common = set(passers[members[0]["id"]])
        for m in members[1:]:
            common &= passers[m["id"]]
        return common

    # 3. Declared pairs: drop a pair one program passes whole.
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for c in kept:
        if c.get("pair"):
            by_pair[c["pair"]].append(c)
    for pid, members in by_pair.items():
        common = passable(members)
        if common:
            for m in members:
                m["drop"] = f"pair passable ({min(common)})"

    # 4. Pair the other weak cases with strong ones of the same family and command. Partners are
    # handed out rarest first: a case that evidences an id few cases evidence (as the coverage
    # inventory counts them) takes one before a case whose ids many others cover.
    tags = json.loads((a.candidates / "bundle_tags.json").read_text())
    ev = evidence([c for c in kept if not c.get("drop")], gold, a.candidates, tags)
    rarity: dict[str, int] = {}
    for _need, found in ev.values():
        for cid in found:
            rarity[cid] = min(rarity.get(cid, len(found)), len(found))

    def rarest(c: dict) -> tuple:
        if c["id"] in keep:  # the only cases that kill a mutant go first
            return (-1, c["id"])
        return (rarity.get(c["id"], len(kept)), c["id"])

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
        for c in sorted(needy[key], key=rarest):
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
    leftover: list[dict] = []
    for c in sorted(unpaired, key=rarest):
        pool = spare.get(c["fmt"], []) if c["family"] == "F" else []
        if not pool:
            leftover.append(c)
            continue
        partner = pool.pop()
        pid = f"F:any/{c['fmt']}:{made}"
        c["pair"] = partner["pair"] = pid
        made += 1

    # 4b. A weak case still without a partner joins a unit of its family that holds a strong case,
    # when the coverage inventory needs it (an id it evidences has fewer than its minimum plus
    # MARGIN cases so far): rarest first, at most UNIT_MAX cases a unit, the unit of its own
    # command and format first. The unit still counts only when every member passes, so a program
    # that fails its strong case gets none of it. Declared B and K pairs take no one.
    def pkey(c: dict) -> tuple:
        if c["bundle"] == "cli":
            return (c["family"], "cli", c["fmt"])
        return (c["family"], route(c), c["fmt"])

    declared = set(by_pair)
    size: Counter = Counter(
        c["pair"] for c in kept if c.get("pair") and not c.get("drop")
    )
    anchors: dict[tuple, list[dict]] = defaultdict(list)  # key -> strong cases
    for c in kept:
        if c.get("drop") or weak[c["id"]] or c.get("pair") in declared:
            continue
        anchors[pkey(c)].append(c)
    out_ids = {c["id"] for c in leftover}
    kept_ids = {c["id"] for c in kept if not c.get("drop")} - out_ids
    count = {
        fid: sum(1 for cid in found if cid in kept_ids)
        for fid, (_need, found) in ev.items()
    }
    ids_of: dict[str, list[str]] = defaultdict(list)
    for fid, (_need, found) in ev.items():
        for cid in found:
            ids_of[cid].append(fid)
    joined = 0
    for c in leftover:  # already rarest first
        wanted = [f for f in ids_of.get(c["id"], []) if count[f] < ev[f][0] + MARGIN]
        if c["id"] in keep:
            wanted.append("--keep")
        same = anchors.get(pkey(c), [])
        rest = [s for k, v in sorted(anchors.items()) if k[0] == c["family"] for s in v]
        room = [
            s
            for s in same + rest
            if (size[s["pair"]] if s.get("pair") else 1) < UNIT_MAX
        ]
        if not wanted or not room:
            c["drop"] = f"no partner ({weak[c['id']]})"
            continue
        strong = min(
            room, key=lambda s: size[s["pair"]] if s.get("pair") else 1
        )  # the emptiest; same-command units come first among equals
        if not strong.get("pair"):
            strong["pair"] = f"{c['family']}:anchor:{made}"
            size[strong["pair"]] = 1
            made += 1
        c["pair"] = strong["pair"]
        size[strong["pair"]] += 1
        joined += 1
        for f in ids_of.get(c["id"], []):
            count[f] += 1

    final = []
    for c in kept:
        if c.get("drop"):
            fate[c["id"]] = c["drop"]
            dropped[c.pop("drop")] += 1
            continue
        final.append(c)

    # 5. Cap the larger families, by whole units, so the grader's run stays short.
    caps = dict(x.split("=", 1) for x in a.cap)
    units_of: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in final:
        units_of[c["family"]][c.get("pair") or c["id"]].append(c)
    # Units holding a case of a kept bundle (a restriction template, the command line) are never
    # capped: they may be the only cases of what they check. Nor are enough units to give every
    # id of the coverage inventory its minimum number of cases, plus a margin.
    never = {
        u
        for fam in units_of
        for u, ms in units_of[fam].items()
        if any(
            c["bundle"].startswith(tuple(a.keep_prefix)) or c.get("stdin") for c in ms
        )
    }
    unit_of = {c["id"]: c.get("pair") or c["id"] for c in final}
    pick = random.Random(a.seed + 1)
    protected = set()
    for _fid, (need, found) in sorted(ev.items()):
        units = Counter(unit_of[cid] for cid in found if cid in unit_of)
        have = sum(n for u, n in units.items() if u in never or u in protected)
        rest = sorted(u for u in units if u not in never and u not in protected)
        pick.shuffle(rest)
        for u in rest:
            if have >= need + MARGIN:
                break
            protected.add(u)
            have += units[u]
    never |= protected
    capped = []
    for fam in sorted(units_of):
        names = sorted(units_of[fam])
        kept_units = [n for n in names if n in never]
        rest = [n for n in names if n not in kept_units]
        limit = max(0, int(caps.get(fam, len(names))) - len(kept_units))
        if len(rest) > limit:
            rng.shuffle(rest)
            dropped[f"over the {fam} cap"] += sum(
                len(units_of[fam][n]) for n in rest[limit:]
            )
            for n in rest[limit:]:
                for c in units_of[fam][n]:
                    fate[c["id"]] = f"over the {fam} cap"
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
    for u in shared:
        for m in members[u]:
            fate[m["id"]] = "answers all given elsewhere too"
    final = [c for c in final if (c.get("pair") or c["id"]) not in shared]
    for c in final:
        fate[c["id"]] = "kept"
    if a.fates:
        a.fates.write_text(json.dumps(fate, indent=0, sort_keys=True) + "\n")

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
        "joined_a_unit": joined,
        "kept_for_coverage": len(protected),
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
