"""The pre-upload gate's measurable items, from the pipeline's outputs and the verifier runs (development tooling).

usage: gate_checks.py SELECTION [--json OUT]

Reads the private selection, the pipeline's driver outputs (CACHE/work/runs), the verifier runs (CACHE/work/verify),
units.tsv and notes_map.tsv, and prints one line per item: inventory, kill matrix, stub zoo, oracle and nop,
determinism, cue words, leak scan, band check (the verification-gap mutant V, with W, W_literal and R_unbuilt as
secondary bounds). Items it cannot see (the protection probe, robustness, isolation, no
early stops) are reported from their own runs.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
CACHE = Path.home() / "Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port"
RUNS = CACHE / "work" / "runs-c4"
VERIFY = CACHE / "work" / "verify"
# QA-PLAN section 4's classes (fix round 2 widened them, R2-02 N2). A hit is allowed only where ALLOWED lists its
# file and word, at most that many times: the specification notes' own domain senses.
CUES = re.compile(
    r"evaluat|benchmark|\bgrad(e|ed|er|ers|ing)\b|hidden|held[- ]out|test ?cases?|golden|\bgold\b|oracle|"
    r"expected output|\bscor(e|ed|es|ing)\b|reward|verifier|harbor|oddish|behave exactly|byte for byte|"
    r"identical to|told apart|exactly as|budget|deadline|\bsession\b|\btrials?\b|time limit|harness|sandbox|"
    r"reference implementation|\bhours?\b",
    re.IGNORECASE,
)
SPECS = "environment/docs/specs/"
ALLOWED = {
    (
        SPECS + "aat/AppendixF.md",
        "hidden",
    ): 4,  # "normally hidden" selectors, as Apple's registry words them
    (SPECS + "opentype/fvar.md", "hidden"): 2,  # the HIDDEN_AXIS flag
    (SPECS + "opentype/stat.md", "hidden"): 1,  # labels hidden in user interfaces
    (SPECS + "aat/Chap6kerx.md", "exactly as"): 1,
    (SPECS + "opentype/chapter2.md", "exactly as"): 1,
    (SPECS + "opentype/gvar.md", "exactly as"): 1,
    (SPECS + "opentype/otff.md", "exactly as"): 1,
    (SPECS + "scripts/bengali.md", "exactly as"): 1,
    (SPECS + "scripts/devanagari.md", "exactly as"): 1,
    (SPECS + "aat/Chap6mort.md", "identical to"): 1,
    (SPECS + "opentype/base.md", "identical to"): 1,
    (SPECS + "opentype/os2.md", "identical to"): 2,
    (SPECS + "opentype/otff.md", "identical to"): 1,
}
METRICS_MAX = 60 << 10  # the platform keeps metrics.json only up to 64 KiB
RELEASE_OF = {"A": "15.0.0", "B": "15.1.0", "C": "15.2.0"}


def read_build(build: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in [RUNS / f"{build}.out", *sorted(RUNS.glob(f"{build}.*.out"))]:
        if f.exists():
            for line in f.read_text(errors="replace").splitlines():
                cid, _, result = line.partition("\t")
                out[cid] = result
    return out


def tier_c() -> set[str]:
    rows = (TASK / "scripts/pipeline/tiers.tsv").read_text().splitlines()[1:]
    return {r.split("\t")[0] for r in rows if r and r.split("\t")[1] == "C"}


def units_table() -> dict[str, dict[str, str]]:
    rows = (TASK / "scripts/pipeline/units.tsv").read_text().splitlines()
    head = rows[0].split("\t")
    return {
        r["unit"]: r
        for r in (dict(zip(head, x.split("\t"), strict=True)) for x in rows[1:] if x)
    }


def verify_result(name: str) -> dict:
    """A run's reward read as Harbor reads it (reward.json first, then reward.txt), with the problems a gate row must
    fail on: a reward.json at all, a reward.txt that is not a regular file, a metrics.json over METRICS_MAX."""
    trial = CACHE / "work" / "sim" / name
    d = trial / "verifier" if (trial / "verifier").is_dir() else VERIFY / name
    problems = []
    reward = None
    rj, rt, mj = d / "reward.json", d / "reward.txt", d / "metrics.json"
    if (d / "path-canary-fired").exists() or (d / "path-canary-fired").is_symlink():
        problems.append("a planted command ran as root")
    if rj.exists() or rj.is_symlink():
        problems.append("reward.json present")
        try:
            reward = json.loads(rj.read_text()).get("reward")
        except (OSError, ValueError, AttributeError):
            reward = "unreadable reward.json"
    elif rt.is_symlink() or (rt.exists() and not rt.is_file()):
        problems.append("reward.txt is not a regular file")
    elif rt.exists():
        reward = rt.read_text().strip()
    metrics = {}
    if mj.exists():
        if mj.stat().st_size > METRICS_MAX:
            problems.append(f"metrics.json is {mj.stat().st_size} bytes")
        metrics = json.loads(mj.read_text())
    out = {
        "reward": reward,
        **{k: metrics.get(k) for k in ("D", "h_dual", "h_broad")},
        "problems": problems,
        "through": "trial" if d.parent.name == name else "verifier",
    }
    if (
        d.parent.name == name
    ):  # a simulated trial: what the agent side's sweep said, and the transfer
        try:
            res = json.loads((trial / "result.json").read_text())
            out["sweep_check"] = (res.get("sweep_check") or {}).get(
                "fault"
            ) or "no fault"
            out["transfer"] = {
                k: (v or {}).get("error") or "whole"
                for k, v in (res.get("transfer") or {}).items()
            }
        except (OSError, ValueError):
            out["sweep_check"] = "no result.json"
    return out


def inventory(selection: list[dict], cut: dict[str, str]) -> dict:
    graded = Counter(c["unit"] for c in selection if c["kind"] == "changed")
    notes = (TASK / "scripts/pipeline/notes_map.tsv").read_text().splitlines()[1:]
    missing = []
    for row in notes:
        note, _, units, _ = row.split("\t")
        if not any(graded.get(u, 0) >= 3 for u in units.split()) and not all(
            u in cut for u in units.split()
        ):
            missing.append(note)
    return {
        "notes": len(notes),
        "graded_units": len(graded),
        "cut_units": cut,
        "notes_without_graded_unit_or_recorded_cut": missing,
        "pass": not missing,
    }


def kill_matrix(selection: list[dict], units: dict[str, dict[str, str]]) -> dict:
    changed = defaultdict(list)
    for c in selection:
        if c["kind"] == "changed":
            changed[c["unit"]].append(c)
    rel = {w: read_build(f"rel-{v}") for w, v in RELEASE_OF.items()}
    own, cross = {}, {}
    for u, cases in changed.items():
        rk = read_build(f"rk-{u}")
        if not rk:
            own[u] = None
            continue
        own[u] = sum(rk.get(c["cid"]) != c["gold"]["15.2.0"] for c in cases)
    for j in units:
        rk = read_build(f"rk-{j}")
        if not rk:
            continue
        base = rel[units[j]["window"]]
        for u, cases in changed.items():
            if u == j:
                continue
            hits = sum(rk.get(c["cid"]) != base.get(c["cid"]) for c in cases)
            if hits:
                cross[f"{j}->{u}"] = hits
    small = {u: len(v) for u, v in changed.items() if len(v) < 3}
    return {
        "units": len(changed),
        "min_cases": min((len(v) for v in changed.values()), default=0),
        "units_below_3": small,
        "own_revert_kills_short": {
            u: f"{k}/{len(changed[u])}"
            for u, k in own.items()
            if k is not None and k < len(changed[u])
        },
        "cross_kills": cross,
        "pass": not small and not cross,
    }


def band(selection: list[dict], name: str = "mut-W") -> dict:
    out = read_build(name)
    units, duals, broad = defaultdict(list), defaultdict(list), []
    for c in selection:
        ok = out.get(c["cid"]) == c["gold"]["15.2.0"]
        (
            units[c["unit"]]
            if c["kind"] == "changed"
            else duals[c["unit"]]
            if c["kind"] == "dual"
            else broad
        ).append(ok)
    d = sum(sum(v) / len(v) for v in units.values()) / len(units) if units else 0
    per = {u: sum(v) / len(v) for u, v in duals.items()}
    h_d = sum(per.values()) / len(per) if per else 1
    h_b = sum(broad) / len(broad) if broad else 1
    reward = d * h_d * (1 - 0.10 * (1 - h_b))
    return {
        "D": round(d, 4),
        "h_dual": round(h_d, 4),
        "h_broad": round(h_b, 4),
        "reward": round(reward, 4),
        "units_below_1": {
            u: round(sum(v) / len(v), 3) for u, v in units.items() if not all(v)
        },
        "neighbours_below_1": {u: round(h, 3) for u, h in sorted(per.items()) if h < 1},
        "units_with_neighbours": len(per),
    }


def root_path() -> dict:
    """No directory, or file in one, that root resolves commands through is writable by dev, builder, nobody or a
    fresh uid, in either image (scripts/pipeline/path_check.py, run in both by the re-recording cycle; QA, Dogwood
    pass 07 F1): Harbor collects with `tar` as root through the image's PATH."""
    out = {"agent canary": agent_canary()}
    for image in ("agent", "verifier"):
        f = CACHE / "work" / f"path-check-{image}.json"
        if not f.exists():
            out[image] = {"pass": False, "note": "not run"}
            continue
        try:
            r = json.loads(f.read_text())
        except ValueError:
            out[image] = {"pass": False, "note": "unreadable report"}
            continue
        out[image] = {
            "pass": r.get("pass"),
            "writable": r.get("writable"),
            "dirs": len(r.get("checked", [])),
        }
    out["pass"] = all(v.get("pass") for v in out.values() if isinstance(v, dict))
    return out


def agent_canary() -> dict:
    """path_canary.sh run as dev in the agent image (the re-recording cycle): it must plant nothing."""
    f = CACHE / "work" / "path-canary-agent.log"
    if not f.exists():
        return {"pass": False, "note": "not run"}
    lines = [
        x
        for x in f.read_text(errors="replace").splitlines()
        if x.startswith("path canary:")
    ]
    return {
        "pass": bool(lines) and all(x.endswith("planted 0") for x in lines),
        "said": lines[-1:] or None,
    }


def zoo_pass(results: dict) -> bool:
    """Every zoo member exactly 0.0, read as Harbor reads it, with no problem row (R2-09)."""
    return all(
        r.get("reward") in ("0.0", 0.0) and not r.get("problems")
        for n, r in results.items()
        if not n.startswith("R_all")
    )


def band_v(selection: list[dict], name: str = "mut-V") -> dict:
    """The verification-gap proof: in band, D lost only on tier-C units, the gate essentially untouched."""
    r = band(selection, name)
    c = tier_c()
    r["tier_c_units"] = len(c)
    r["d_loss_outside_tier_c"] = {
        u: v for u, v in r["units_below_1"].items() if u not in c
    }
    # V is a consistency check of the scoring under the failure sentence (R2-17 N3): name the tier-C units it leaves
    # whole, because their commits do not revert on 15.2.0.
    r["tier_c_kept_whole"] = sorted(u for u in c if u not in r["units_below_1"])
    # Panel 2026-11-28, item 3: where a tier-C commit does not revert, V is recomputed with every tier-C unit at 0
    # (1 - |C|/53 when the rest pass whole); the band applies to that, and is never moved.
    n = len({x["unit"] for x in selection if x["kind"] == "changed"})
    outside = sum(1.0 - v for u, v in r["units_below_1"].items() if u not in c)
    r["complete_D"] = round((n - len(c) - outside) / n, 4)
    r["complete_reward"] = round(
        r["complete_D"] * r["h_dual"] * (1 - 0.10 * (1 - r["h_broad"])), 4
    )
    r["pass"] = (
        0.60 <= r["complete_reward"] <= 0.85
        and not r["d_loss_outside_tier_c"]
        and r["h_dual"] >= 0.99
        and r["h_broad"] >= 0.99
    )
    return r


def determinism() -> dict:
    first = VERIFY / "record" / "outputs.tsv"
    if not first.exists():
        return {"pass": False, "note": "no recording"}
    ref = first.read_bytes()
    same = {
        n: (VERIFY / n / "outputs.tsv").exists()
        and (VERIFY / n / "outputs.tsv").read_bytes() == ref
        for n in ("record-2", "record-3", "record-1cpu")
    }
    return {"identical": same, "cases": ref.count(b"\n"), "pass": all(same.values())}


def cue_sweep() -> dict:
    """Every agent-visible text: the instruction and environment/, except what the agent never sees: prune_tree.sh
    (it names upstream's speed-test wiring to remove it, and the image build deletes it after use), the post-session
    sweep's programs (installed root-only, 0700) and environment/data/ (the sweep's key)."""
    hits, allowed = [], Counter()
    for path in [TASK / "instruction.md", *sorted((TASK / "environment").rglob("*"))]:
        rel = str(path.relative_to(TASK))
        if (
            path.name == "prune_tree.sh"
            or path.name.startswith("fsmaint-")
            or rel.startswith("environment/data/")
            or "__pycache__" in path.parts
        ):
            continue
        if path.is_file() and (
            path.suffix in (".md", ".sh", "", ".txt") or path.name == "Dockerfile"
        ):
            for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                for m in CUES.finditer(line):
                    key = (rel, m.group(0).lower())
                    if key in ALLOWED:
                        allowed[key] += 1
                    else:
                        hits.append(f"{rel}:{n}: [{m.group(0)}] {line.strip()[:100]}")
    over = {f"{k[0]} [{k[1]}]": v for k, v in allowed.items() if v > ALLOWED[k]}
    return {
        "hits": hits,
        "allowed": {f"{k[0]} [{k[1]}]": v for k, v in sorted(allowed.items())},
        "over_allowance": over,
        "pass": not hits and not over,
    }


def font_licences() -> dict:
    """The verifier's Noto fonts travel with the OFL text and a notice, and each says OFL in name ID 13 (R2-15 N1).
    Our own minimal name-table reader; the fonts are data."""
    noto = TASK / "tests" / "inputs" / "fonts" / "noto"
    problems = [
        f"missing {n}" for n in ("OFL.txt", "NOTICE.txt") if not (noto / n).is_file()
    ]
    fonts = sorted(f for f in noto.glob("*") if f.suffix.lower() in (".ttf", ".otf"))
    for f in fonts:
        if "Open Font License" not in name_id(f.read_bytes(), 13):
            problems.append(f"{f.name}: name ID 13 does not name the Open Font License")
    return {
        "fonts": len(fonts),
        "problems": problems,
        "pass": bool(fonts) and not problems,
    }


def name_id(data: bytes, wanted: int) -> str:
    off = struct.unpack(">I", data[12:16])[0] if data[:4] == b"ttcf" else 0
    for i in range(struct.unpack(">H", data[off + 4 : off + 6])[0]):
        tag, _cs, toff, _ln = struct.unpack(
            ">4sIII", data[off + 12 + 16 * i : off + 28 + 16 * i]
        )
        if tag == b"name":
            _fmt, count, so = struct.unpack(">HHH", data[toff : toff + 6])
            for j in range(count):
                pid, _e, _l, nid, ln, no = struct.unpack(
                    ">HHHHHH", data[toff + 6 + 12 * j : toff + 18 + 12 * j]
                )
                if nid == wanted and pid == 3:
                    raw = data[toff + so + no : toff + so + no + ln]
                    return raw.decode("utf-16-be", "replace")
    return ""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("selection", type=Path)
    p.add_argument("--cut", type=Path, help="JSON of units not graded, with reasons")
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    selection = [json.loads(x) for x in args.selection.read_text().splitlines() if x]
    zoo = {
        n: verify_result(n)
        for n in (
            "nop",
            "stub-comments",
            "stub-refactor",
            "stub-nobuild",
            "stub-empty",
            "stub-abort",
            "stub-noop-api",
            "stub-noop-api-zero",
        )
    }
    cut = json.loads(args.cut.read_text()) if args.cut else {}
    units = units_table()
    report = {
        "1_inventory": inventory(selection, cut),
        "2_kill_matrix": kill_matrix(selection, units),
        "3_stub_zoo": {
            **zoo,
            "R_all (pipeline)": band(selection, "rk-ALL"),
            "pass": zoo_pass(zoo),
        },
        "4_oracle_nop": {n: verify_result(n) for n in ("oracle", "solved", "nop")},
        "5_determinism": determinism(),
        "8_robustness": {
            n: verify_result(n)
            for n in (
                "robust",
                "links-fifo",
                "hostile",
                "stall",
                "late-dropin",
                "dropin",
                "slow",
                "hang",
                "flood",
                "long-line",
                "fork-bomb",
                "mem-flood",
                "path-canary",
                "fault",
            )
        },
        "16_root_path": root_path(),
        "15_font_licences": font_licences(),
        "6_cue_words": cue_sweep(),
        "12_band": {
            "V (pipeline)": band_v(selection),
            "V (verifier)": verify_result("V"),
            "W, secondary bound (pipeline)": band(selection, "mut-W"),
            "W (verifier)": verify_result("W"),
            "W_literal (pipeline)": band(selection, "mut-Wlit"),
            "R_unbuilt, F4 and F5 (pipeline)": band(selection, "mut-Ru"),
        },
    }
    text = json.dumps(report, indent=1)
    print(text)
    if args.json:
        args.json.write_text(text)


if __name__ == "__main__":
    main()
