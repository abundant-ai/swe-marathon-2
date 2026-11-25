"""Record what the original, carve-rs 0.1.14, prints for each private case, and keep the steady cases.

usage: python3 recorder.py record <program> <cases.json> <expected.json> [--keep <kept.json>] [--report <report.json>]

Each case is run twice and a third time perturbed (another binary path, 4 KB of environment
padding, a stack 256 KB smaller and one CPU), and kept if all three print the same and end the
way a rendering ends (`crashed`), the first two used at most KEEP_CPU seconds of CPU and
KEEP_SEC of wall time each, and the answer hashes to the digest the case carries
(`answer_sha256`): a case this build answers otherwise is dropped (`differs`). Last, by rule and by
id, `select` leaves out the cases whose input holds their answer, those beyond PAIR_SHARE with an
answer many others share, and, while a dispatcher with no renderer in it passes more than
FLOOR_SHARE of the cases, one of those. `--keep` writes the cases kept (with only the fields the
runs read), `--report` how every run went and why cases were left out.
"""

from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

try:  # run as a script beside runcases.py, or imported from the verifier package
    from runcases import ENCODING, LIMITS, clear_workspace, limit, run_case
except ImportError:
    from .runcases import ENCODING, LIMITS, clear_workspace, limit, run_case

KEEP_SEC = 1.0  # wall time of each of the two runs, at most: generous, since a busy builder is slow
KEEP_CPU = 0.25  # CPU time of each, at most, which a busy builder hardly changes: an eighth of the run limit
# The original exits 0 having rendered and 2 on a usage or input error; anything else, a signal, or
# one of these on standard error, is no answer an implementation can give.
EXITS = (0, 2)
CRASH_MARKERS = (
    b"panicked at",
    b"RUST_BACKTRACE",
    b"stack overflow",
    b"memory allocation of",
    b"core dumped",
)
PAIR_SHARE = 0.015  # cases kept with any one (stdout, exit code), the command line aside, at most
FLOOR_SHARE = 0.05  # cases a dispatcher with no renderer passes (free_cases), at most
LOOKUP_SHARE = (
    0.05  # cases a program with the public corpus and no renderer passes, at most
)
QUOTE_LEN = 12  # an answer at least this long that the case's own input holds is free
PERTURBED_ENV = {"CARVE_PERTURBED_PADDING": "p" * 4096}
KEPT_FIELDS = (
    "id",
    "kind",
    "area",
    "argv",
    "files",
    "stdin",
    "features",
    "djot_exact",
    "djot_normalized",
)


def digest(exit_code: int, stdout: bytes) -> str:
    """The answer digest make_cases.answer_sha256 stores: the exit status, a newline, stdout's bytes."""
    return hashlib.sha256(f"{exit_code}\n".encode() + stdout).hexdigest()


def crashed(got: dict) -> bool:
    """A finished run of the original that is no answer: an exit status other than 0 or 2, a
    signal, or a panic, overflow or allocation failure reported on standard error."""
    if got["exit"] is None:
        return False
    return got["exit"] not in EXITS or any(
        marker in got.get("stderr", b"") for marker in CRASH_MARKERS
    )


def group(case: dict) -> str:
    """What a case asks, as a dispatcher could tell without reading its document: its kind."""
    return case.get("kind", "?")


def free_cases(cases: list[dict], outputs: dict) -> dict[str, list[str]]:
    """The cases a program with no renderer in it answers, by group (`group`): every command-line
    case (a table of the original's answers), and in each other group the cases that answer its
    most common (stdout, exit code) where two or more share it."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        groups[group(case)].append(case)
    free = {}
    for name, members in groups.items():
        if name == "cli":
            free[name] = [case["id"] for case in members]
            continue
        answer = lambda case: (
            outputs[case["id"]]["stdout"],
            outputs[case["id"]]["exit"],
        )
        common, shared = max(
            Counter(map(answer, members)).items(),
            key=lambda item: (item[1], repr(item[0])),
        )
        free[name] = (
            [case["id"] for case in members if answer(case) == common]
            if shared > 1
            else []
        )
    return free


def quoted(case: dict, answer: str) -> bool:
    """Whether the case's own input holds its whole answer (at least QUOTE_LEN characters of it):
    a program could print it without rendering anything."""
    text = answer.strip()
    if len(text) < QUOTE_LEN:
        return False
    held = "\n".join(
        list(case["files"].values()) + [case.get("stdin") or ""] + case["argv"]
    )
    return text in held


def select(cases: list[dict], outputs: dict) -> tuple[list[dict], dict[str, list[str]]]:
    """The recorded cases less, in this order and each time by id: those whose input holds their
    answer (`quoted`); beyond PAIR_SHARE of the cases, those with an answer that many others share
    (the command line aside, whose cases take their share first); and while more than FLOOR_SHARE of
    them can be answered without a renderer (`free_cases`), one of those in the largest group. Also
    the ids left out, by reason."""
    dropped: dict[str, list[str]] = defaultdict(list)
    kept = []
    for case in cases:
        if group(case) != "cli" and quoted(case, outputs[case["id"]]["stdout"]):
            dropped["input holds the answer"].append(case["id"])
        else:
            kept.append(case)
    limit_, cases = max(1, int(PAIR_SHARE * len(kept))), kept
    seen = Counter(
        (outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"])
        for case in cases
        if group(case) == "cli"
    )
    kept = []
    for case in cases:
        answer = (outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"])
        if group(case) != "cli":
            seen[answer] += 1
            if seen[answer] > limit_:
                dropped["answer shared by many cases"].append(case["id"])
                continue
        kept.append(case)
    while True:
        free = free_cases(kept, outputs)
        groups = [name for name in free if name != "cli" and free[name]]
        if sum(map(len, free.values())) <= FLOOR_SHARE * len(kept) or not groups:
            break
        victim = max(free[max(groups, key=lambda name: (len(free[name]), name))])
        dropped["passed with no renderer"].append(victim)
        kept = [case for case in kept if case["id"] != victim]
    return kept, dict(dropped)


def perturbed_limits() -> None:
    """`limit`, then a stack 256 KB smaller (another stack placement) and one CPU."""
    limit()
    try:
        resource.setrlimit(
            resource.RLIMIT_STACK, (LIMITS[resource.RLIMIT_STACK] - (256 << 10),) * 2
        )
    except (ValueError, OSError):
        pass
    try:
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    except (AttributeError, OSError, IndexError):
        pass


def relocated(program: str) -> str:
    """A copy of the program under a longer path of its own."""
    place = Path(tempfile.mkdtemp(prefix="carve-perturbed-location-")) / "bin"
    place.mkdir()
    shutil.copy2(program, place / Path(program).name)
    return str(place / Path(program).name)


def host() -> dict:
    """What of the machine could change an answer: CPU, kernel and CPUs usable."""
    info = {
        "machine": os.uname().machine,
        "cpus": len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
    }
    try:
        cpu = Path("/proc/cpuinfo").read_text(errors="replace")
        info["cpu"] = next(
            (
                line.split(":", 1)[1].strip()
                for line in cpu.splitlines()
                if line.startswith("model name")
            ),
            "",
        )
        info["kernel"] = Path("/proc/version").read_text(errors="replace").strip()
    except OSError:
        pass
    return info


def record(program: str, cases: list[dict]) -> tuple[list[dict], dict, dict]:
    """The cases kept (with KEPT_FIELDS only), what the program printed for them, and a report:
    how long and how much CPU every run took, and why the others were left out."""
    finished, outputs = [], {}
    started = time.monotonic()
    report = {
        "keep_seconds": KEEP_SEC,
        "keep_cpu": KEEP_CPU,
        "seconds": {},
        "cpu": {},
        "slow": [],
        "unsteady": [],
        "crashed": [],
        "differs": [],
        "lookup": [],
        "output_limit": [],
        "memory_limit": [],
        "disk_limit": [],
        "perturbed": [],
        "dropped": {},
        "host": host(),
    }
    elsewhere = relocated(program)
    for case in cases:
        first, second = (run_case([program], case, keep_stderr=True) for _ in range(2))
        report["seconds"][case["id"]] = [first["seconds"], second["seconds"]]
        report["cpu"][case["id"]] = [first["cpu"], second["cpu"]]
        errors = {first.get("error"), second.get("error")} - {None}
        if errors:
            report[
                "slow"
                if "timeout" in errors
                else "output_limit"
                if "output limit" in errors
                else "memory_limit"
                if "memory limit" in errors
                else "disk_limit"
                if errors & {"disk limit", "file limit"}
                else "unsteady"
            ].append(case["id"])
        elif (first["exit"], first["stdout"]) != (second["exit"], second["stdout"]):
            report["unsteady"].append(case["id"])
        elif crashed(first) or crashed(second):
            report["crashed"].append(case["id"])
        elif (
            case.get("answer_sha256")
            and digest(first["exit"], first["stdout"]) != case["answer_sha256"]
        ):
            report["differs"].append(case["id"])
        elif digest(first["exit"], first["stdout"]) in set(
            case.get("lookup_sha256", [])
        ):
            report["lookup"].append(
                case["id"]
            )  # the corpus-lookup program would give this answer
        elif (
            max(first["seconds"], second["seconds"]) > KEEP_SEC
            or max(first["cpu"], second["cpu"]) > KEEP_CPU
        ):
            report["slow"].append(case["id"])
        else:
            third = run_case(
                [elsewhere],
                case,
                keep_stderr=True,
                env=PERTURBED_ENV,
                preexec=perturbed_limits,
            )
            if (third["exit"], third["stdout"]) != (first["exit"], first["stdout"]):
                report["perturbed"].append(case["id"])
                continue
            finished.append(case)
            outputs[case["id"]] = {
                "exit": first["exit"],
                "stdout": first["stdout"].decode(*ENCODING),
            }
    shutil.rmtree(Path(elsewhere).parent.parent, ignore_errors=True)
    kept, dropped = select(finished, outputs)
    for reason, ids in dropped.items():
        report["dropped"].setdefault(reason, []).extend(ids)
    report["wall_seconds"] = round(time.monotonic() - started, 1)
    kept_fields = [
        {key: case[key] for key in KEPT_FIELDS if key in case} for case in kept
    ]
    return kept_fields, {case["id"]: outputs[case["id"]] for case in kept}, report


def record_probes(program: str, probes: list[dict]) -> dict:
    """What the original prints for each fingerprint probe, run once (the probes are the original's
    own disagreements and commands, never counted)."""
    answers = {}
    for probe in probes:
        got = run_case([program], probe)
        if got["exit"] is not None:
            answers[probe["id"]] = {
                "exit": got["exit"],
                "stdout": got["stdout"].decode(*ENCODING),
            }
    clear_workspace()
    return answers


def main() -> None:
    """Record what a program prints for every case and keep the steady cases."""
    if len(sys.argv) < 5 or sys.argv[1] != "record":
        raise SystemExit(__doc__)
    program, cases_path, expected_path = sys.argv[2:5]
    option = lambda name: (
        sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None
    )
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))["cases"]
    if option("--probes") and option("--probes-out"):
        probes = json.loads(Path(option("--probes")).read_text(encoding="utf-8"))[
            "probes"
        ]
        Path(option("--probes-out")).write_text(
            json.dumps(record_probes(program, probes), sort_keys=True)
        )
    kept, outputs, report = record(program, cases)
    clear_workspace()
    report["kept_ids_sha256"] = hashlib.sha256(
        "\n".join(case["id"] for case in kept).encode()
    ).hexdigest()
    lookup_share = len(report["lookup"]) / (len(kept) + len(report["lookup"]) or 1)
    if (
        len(report["unsteady"]) > 0.02 * len(cases)
        or len(report["crashed"]) > 0.02 * len(cases)
        or len(report["perturbed"]) > 0.02 * len(cases)
        or len(report["differs"]) > 0.02 * len(cases)
        or lookup_share > LOOKUP_SHARE
        or len(kept) < 0.88 * len(cases)
    ):
        raise SystemExit(
            f"kept {len(kept)} of {len(cases)} cases: {len(report['unsteady'])} did not finish the same "
            f"way twice, {len(report['crashed'])} crashed, {len(report['perturbed'])} changed when "
            f"perturbed, {len(report['differs'])} answered otherwise than the checked answer, "
            f"{len(report['lookup'])} ({lookup_share:.1%}) the corpus lookup gives, {len(report['slow'])} were slow"
        )
    if option("--expect-kept-ids") and report["kept_ids_sha256"] != option(
        "--expect-kept-ids"
    ):
        raise SystemExit(
            f"kept-ids sha256 {report['kept_ids_sha256']} is not the accepted {option('--expect-kept-ids')}"
        )
    Path(expected_path).write_text(json.dumps(outputs, sort_keys=True))
    if option("--keep"):
        Path(option("--keep")).write_text(json.dumps({"cases": kept}, sort_keys=True))
    if option("--report"):
        Path(option("--report")).write_text(json.dumps(report, sort_keys=True))
    print(
        f"recorded {len(kept)} of {len(cases)} cases in {report['wall_seconds']} s ({len(report['slow'])} slow, "
        f"{len(report['unsteady'])} unsteady, {len(report['crashed'])} crashed, {len(report['differs'])} differ, "
        f"{len(report['perturbed'])} perturbed, "
        + ", ".join(f"{len(ids)} {why}" for why, ids in report["dropped"].items())
        + ")"
    )


if __name__ == "__main__":
    main()
