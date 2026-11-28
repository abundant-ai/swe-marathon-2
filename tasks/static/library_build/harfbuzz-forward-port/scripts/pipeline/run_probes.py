"""The egress and transfer probes of fix round 2 (R2-M3, R2-M4), each one simulated trial (simulate_trial.py).

usage: python -I scripts/pipeline/run_probes.py [--only a-late-dropin,...] [--build] [--agent-image TAG]
           [--verifier-image TAG] [--keep]

Each probe takes the shared heavy-job lock for itself (so holds stay short), runs, and is checked against its
expected result (written in its turn script's header and below). WORK/sim/probes-<stamp>.json holds every probe's
result, the checks and whether they held. Development tooling, never shipped.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_trial  # our own modules, found beside this file
import spike

PIPE = spike.PIPE
TASK = spike.TASK
# The reference tree's reward through the same images (--oracle-reward): what a tree the sweep leaves as it was at
# the end of the work must score.
BASELINE = {"oracle": "1.0"}


def record_of(name: str) -> dict:
    """The sweep's record as the trial left it (WORK/sim/NAME/agent/out/record.json); {} without one."""
    path = simulate_trial.SIM / name / "agent" / "out" / "record.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def reference_digests() -> set[str]:
    """The sha256 of every file of the reference's library sources (solution/private/tree)."""
    root = TASK / "solution" / "private" / "tree"
    return {
        hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def fault_of(result: dict) -> object:
    return (result.get("sweep_check") or {}).get("fault")


def check_oracle(result: dict, rec: dict) -> dict:
    return {
        "listed": rec.get("listed"),
        "late entries": rec.get("late_count"),
        "end from": rec.get("end_from"),
        "processes left": rec.get("processes_left"),
        "transfer": result.get("transfer"),
        "reward": result.get("reward"),
        "fault": fault_of(result),
        "held": result.get("reward") == BASELINE["oracle"]
        and fault_of(result) is None
        and not rec.get("late_count"),
    }


def check_dropin(result: dict, rec: dict) -> dict:
    late = rec.get("late") or []
    files = [item for item in late if item.get("type") == "file"]
    reference = reference_digests()
    return {
        "late entries listed": len(late),
        "late files holding the reference's content": sum(
            1 for f in files if f.get("sha256") in reference
        ),
        "every late entry taken out": all(
            str(item.get("action", "")).startswith(("put back", "removed"))
            for item in late
        ),
        "end from": rec.get("end_from"),
        "reward": result.get("reward"),
        "fault": fault_of(result),
        "held": bool(late)
        and all(
            str(item.get("action", "")).startswith(("put back", "removed"))
            for item in late
        )
        and result.get("reward") == "0.0"
        and fault_of(result) is None,
    }


def check_links(result: dict, rec: dict) -> dict:
    links = rec.get("links") or {}
    counts = {key: len(value) for key, value in links.items()}
    return {
        "links": counts,
        "changes": rec.get("changes"),
        "transfer": result.get("transfer"),
        "reward": result.get("reward"),
        "fault": fault_of(result),
        "held": counts.get("copied", 0) >= 2
        and counts.get("removed", 0) >= 3
        and result.get("reward") == BASELINE["oracle"]
        and fault_of(result) is None
        and not (result.get("transfer") or {}).get("tree", {}).get("error"),
    }


def check_raw(result: dict, rec: dict) -> dict:
    tree = (result.get("transfer") or {}).get("tree") or {}
    return {
        "transfer": tree,
        "held": bool(tree.get("error"))
        and (tree.get("arrived_entries") or 0) < (tree.get("members") or 0),
    }


def check_zombie(result: dict, rec: dict) -> dict:
    late = rec.get("late") or []
    after = (result.get("steps") or {}).get("collect", {}).get("dev_threads_after")
    opened = rec.get("netcheck_open") or {}
    return {
        "late entries": [(item.get("path"), item.get("action")) for item in late][:10],
        "processes left at the opening": opened.get("processes_left"),
        "processes left at the sweep": rec.get("processes_left"),
        "dev threads alive after the hook": after,
        "reward": result.get("reward"),
        "fault": fault_of(result),
        "held": after == 0
        and rec.get("processes_left") == 0
        and result.get("reward") == BASELINE["oracle"]
        and fault_of(result) is None,
    }


def check_zombie_legacy(result: dict, rec: dict) -> dict:
    steps = (result.get("steps") or {}).get("collect", {})
    return {
        "dev threads alive after round 1's hook": steps.get("dev_threads_after"),
        "threads": steps.get("dev_threads"),
        "held": (steps.get("dev_threads_after") or 0) >= 1,
    }


def check_capped(result: dict, rec: dict) -> dict:
    late = {item.get("path"): item for item in rec.get("late") or []}
    layout = late.get("src/hb-ot-layout.cc") or {}
    made = late.get("made-after-the-limit.txt") or {}
    return {
        "end from": rec.get("end_from"),
        "src/hb-ot-layout.cc": layout.get("action"),
        "made-after-the-limit.txt": made.get("action"),
        "reward": result.get("reward"),
        "fault": fault_of(result),
        "held": rec.get("end_from") == "limit"
        and layout.get("from") == "copy"
        and str(made.get("action", "")).startswith("removed")
        and result.get("reward") == BASELINE["oracle"]
        and fault_of(result) is None,
    }


def check_processes(result: dict, rec: dict) -> dict:
    return {
        "processes listed": rec.get("process_count"),
        "processes left": rec.get("processes_left"),
        "kill passes": rec.get("kill_passes"),
        "end from": rec.get("end_from"),
        "late entries": rec.get("late_count"),
        "reward": result.get("reward"),
        "fault": fault_of(result),
        "held": (rec.get("process_count") or 0) >= 22
        and rec.get("processes_left") == 0
        and result.get("reward") == BASELINE["oracle"]
        and fault_of(result) is None,
    }


PROBES = {
    "oracle": {
        "expect": "the reference through the whole path: nothing late, a whole transfer, its reward, no fault",
        "params": {"solution": True},
        "check": check_oracle,
    },
    "a-late-dropin": {
        "expect": "every late entry listed and taken out; the shipped tree's 0.0; no fault",
        "params": {
            "turn": PIPE / "probe_late_dropin.sh",
            "payloads": [(TASK / "solution" / "private", "/home/dev/ref")],
        },
        "check": check_dropin,
    },
    "b-links-fifo": {
        "expect": "links made relative or copied, the rest and the FIFO removed; whole transfer; 1.0; no fault",
        "params": {"solution": True, "turn": PIPE / "probe_links_fifo.sh"},
        "check": check_links,
    },
    "b-links-fifo-raw": {
        "expect": "without the sweep, the extraction stops at a link or the FIFO: fewer entries arrive",
        "params": {
            "solution": True,
            "turn": PIPE / "probe_links_fifo.sh",
            "collect": "none",
            "verify": False,
        },
        "check": check_raw,
    },
    "c-zombie-thread": {
        "expect": "the process with a zombie leader killed; nothing written after the end counts; 1.0; no fault",
        "params": {"solution": True, "turn": PIPE / "probe_zombie_thread.sh"},
        "check": check_zombie,
    },
    "c-zombie-thread-legacy": {
        "expect": "round 1's collect hook leaves that process alive",
        "params": {
            "solution": True,
            "turn": PIPE / "probe_zombie_thread.sh",
            "hooks": "none",
            "collect": "legacy",
            "egress": False,
            "verify": False,
        },
        "check": check_zombie_legacy,
    },
    "e-capped-last-edit": {
        "expect": "the end is the limit; the last edit before it kept, the later one and a new file out; 1.0",
        "params": {
            "solution": True,
            "turn": PIPE / "probe_capped_last_edit.sh",
            "limit_in": 9.0,
            "hold": 2.0,
        },
        "check": check_capped,
    },
    "d-hook-processes": {
        "expect": "the sweep alone stops, lists (22 or more) and kills every process; 1.0; no fault",
        "params": {
            "solution": True,
            "turn": PIPE / "probe_hook_processes.sh",
            "egress": False,
        },
        "check": check_processes,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--only", help="comma-separated probe names")
    parser.add_argument(
        "--build",
        action="store_true",
        help="build both images first (one hold of its own)",
    )
    parser.add_argument("--agent-image", default=simulate_trial.AGENT_IMAGE)
    parser.add_argument("--verifier-image")
    parser.add_argument("--platform", default=simulate_trial.VERIFIER_PLATFORM)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument(
        "--no-lock",
        action="store_true",
        help="the caller holds the heavy-job lock (spike.py milestone --after)",
    )
    parser.add_argument(
        "--oracle-reward",
        default="1.0",
        help="the reference's reward through these images, which intact trees must match",
    )
    args = parser.parse_args()
    BASELINE["oracle"] = args.oracle_reward
    verifier_image = args.verifier_image or spike.verifier_tag(args.platform)
    names = args.only.split(",") if args.only else list(PROBES)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    summary_path = simulate_trial.SIM / f"probes-{stamp}.json"
    simulate_trial.SIM.mkdir(parents=True, exist_ok=True)
    if args.build:
        with spike.heavy("probes: images"):
            simulate_trial.build_images(args.agent_image, verifier_image, args.platform)
    summary = {}
    for probe in names:
        spec = PROBES[probe]
        name = f"{probe}-{stamp}"
        hold = (
            contextlib.nullcontext() if args.no_lock else spike.heavy(f"probe {name}")
        )
        try:
            with hold:
                result = simulate_trial.run_trial(
                    name,
                    agent_image=args.agent_image,
                    verifier_image=verifier_image,
                    platform=args.platform,
                    keep=args.keep,
                    **spec["params"],
                )
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - a probe that cannot run is its own record
            summary[probe] = {
                "trial": name,
                "expected": spec["expect"],
                "held": False,
                "error": repr(exc)[:500],
            }
            summary_path.write_text(json.dumps(summary, indent=1, default=str))
            print(f"{probe}: COULD NOT RUN {exc!r}"[:600])
            continue
        checked = spec["check"](result, record_of(name))
        summary[probe] = {"trial": name, "expected": spec["expect"], **checked}
        summary_path.write_text(json.dumps(summary, indent=1, default=str))
        print(
            f"{probe}: {'HELD' if checked['held'] else 'DID NOT HOLD'} {json.dumps(checked, default=str)[:400]}"
        )
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
