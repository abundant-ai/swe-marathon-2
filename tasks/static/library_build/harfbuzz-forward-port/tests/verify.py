"""Build the delivered tree with the product's commands, run every case batch, and publish the reward.

The release to check comes from the step's verifier environment (`RELEASE`), never from the tree. The tree's own
build scripts and library code run only as the unprivileged `builder` user, which cannot read the recorded outputs
in /tests/private; a root process compares the outputs after the driver has exited. An evaluation fault leaves no
reward file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

TESTS = Path("/tests")
PRIVATE = TESTS / "private"
FONTS = TESTS / "inputs" / "fonts"
DRIVER = TESTS / "driver" / "hbdrv.c"
TREE = Path("/app/harfbuzz")
WORK = Path("/tmp/hbv")
LOGS = Path("/logs/verifier")
WINDOWS = {"15.0.0": {"A"}, "15.1.0": {"A", "B"}, "15.2.0": {"A", "B", "C"}}
W_DUAL, W_BROAD = 0.25, 0.10
MESON = [
    "meson", "setup", "/tmp/hbv/b", "--buildtype=release", "-Ddefault_library=static",
    "-Dglib=disabled", "-Dgobject=disabled", "-Dcairo=disabled", "-Dchafa=disabled", "-Dicu=disabled",
    "-Dfreetype=disabled", "-Dpng=disabled", "-Dzlib=disabled", "-Dgraphite2=disabled",
    "-Draster=disabled", "-Dvector=disabled", "-Dgpu=disabled", "-Dsubset=disabled",
    "-Dtests=disabled", "-Dintrospection=disabled", "-Ddocs=disabled", "-Dutilities=disabled",
]  # fmt: skip
ENV = {
    "PATH": "/opt/py/bin:/usr/local/bin:/usr/bin:/bin",
    "HOME": str(WORK),
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
}


class EvaluationError(Exception):
    """The check itself could not be carried out; no reward may be published."""


def as_builder(
    cmd: list[str], *, cwd: Path, timeout: int, stdin=None, stdout=None
) -> subprocess.CompletedProcess:
    """Run a command as the unprivileged builder user, with a clean environment and process limits."""
    wrapped = [
        "prlimit", "--nproc=1024", "--fsize=4294967296", "--core=0", "--",
        "setpriv", "--reuid=builder", "--regid=builder", "--clear-groups", "--",
        "timeout", "--kill-after=10", str(timeout), *cmd,
    ]  # fmt: skip
    return subprocess.run(
        wrapped,
        cwd=cwd,
        env=ENV,
        stdin=stdin,
        stdout=stdout or subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def prepare() -> tuple[list[dict], dict[str, str]]:
    release = os.environ.get("RELEASE", "")
    if release not in WINDOWS:
        raise EvaluationError(f"unknown RELEASE {release!r}")
    for tool in ("setpriv", "prlimit", "meson", "ninja", "cc", "c++"):
        if shutil.which(tool, path=ENV["PATH"]) is None:
            raise EvaluationError(f"{tool} is missing")
    try:
        cases = [
            json.loads(line)
            for line in (PRIVATE / "cases.jsonl").read_text().splitlines()
            if line
        ]
        expected = json.loads((PRIVATE / "expected.json").read_text())[release]
    except (OSError, ValueError, KeyError) as exc:
        raise EvaluationError(f"private inputs unreadable: {exc}") from exc
    windows = WINDOWS[release]
    cases = [c for c in cases if c["kind"] != "changed" or c["window"] in windows]
    if not DRIVER.is_file():
        raise EvaluationError("driver source missing")
    return cases, expected


def skip_build_dirs(directory: str, names: list[str]) -> set[str]:
    """copytree filter: subdirectories that are meson build directories are not copied."""
    return {n for n in names if (Path(directory) / n / "meson-private").is_dir()}


def build(notes: list[str]) -> Path | None:
    """Copy and build the delivered tree as builder; return the linked driver, or None for a candidate failure."""
    WORK.mkdir(
        parents=True
    )  # a fresh container each time; an existing one fails loudly
    if not TREE.is_dir():
        notes.append("/app/harfbuzz is missing")
        return None
    # Build out of tree, and leave out any build directory the tree carries (meson marks them).
    shutil.copytree(TREE, WORK / "tree", symlinks=True, ignore=skip_build_dirs)
    subprocess.run(["chown", "-R", "builder:builder", str(WORK)], check=True)
    tree = WORK / "tree"
    for step, cmd, limit in (
        ("setup", MESON, 900),
        ("build", ["ninja", "-C", str(WORK / "b"), "-j", "4"], 1800),
        (
            "driver",
            [
                "cc",
                "-O2",
                "-c",
                "-Isrc",
                f"-I{WORK / 'b' / 'src'}",
                "-o",
                str(WORK / "hbdrv.o"),
                str(DRIVER),
            ],
            300,
        ),
        (
            "link",
            [
                "c++",
                "-o",
                str(WORK / "hbdrv"),
                str(WORK / "hbdrv.o"),
                str(WORK / "b" / "src" / "libharfbuzz.a"),
                "-lm",
            ],
            300,
        ),
    ):
        started = time.time()
        result = as_builder(cmd, cwd=tree, timeout=limit)
        notes.append(
            f"{step}: exit {result.returncode} in {time.time() - started:.0f}s"
        )
        if result.returncode:
            (WORK / f"{step}.log").write_bytes(result.stdout or b"")
            return None
    return WORK / "hbdrv"


def run_batches(driver: Path, cases: list[dict]) -> dict[str, str]:
    """One driver process per font, so a hang or crash costs only that font's cases."""
    batches: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        batches[c["font"]].append(c)
    outputs: dict[str, str] = {}
    for n, (font, items) in enumerate(sorted(batches.items())):
        batch = WORK / f"batch-{n}.tsv"
        batch.write_text(
            "".join(
                f"{c['id']}\t{FONTS / font}\t{c['idx']}\t{c['opts']}\t{c['text']}\n"
                for c in items
            )
        )
        os.chmod(batch, 0o644)
        out = WORK / f"batch-{n}.out"
        with batch.open() as fin, out.open("wb") as fout:
            as_builder([str(driver)], cwd=WORK, timeout=300, stdin=fin, stdout=fout)
        for line in out.read_text(errors="replace").splitlines():
            cid, _, result = line.partition("\t")
            outputs[cid] = result
    return outputs


def score(cases: list[dict], expected: dict[str, str], outputs: dict[str, str]) -> dict:
    units: dict[str, list[bool]] = defaultdict(list)
    held: dict[str, list[bool]] = {"dual": [], "broad": []}
    families: dict[str, list[bool]] = defaultdict(list)
    for c in cases:
        ok = outputs.get(c["id"]) == expected[c["id"]]
        if c["kind"] == "changed":
            units[c["unit"]].append(ok)
            families[c["family"]].append(ok)
        else:
            held[c["kind"]].append(ok)
    per_unit = {u: sum(v) / len(v) for u, v in sorted(units.items())}
    d = sum(per_unit.values()) / len(per_unit) if per_unit else 0.0
    h_d = sum(held["dual"]) / len(held["dual"]) if held["dual"] else 1.0
    h_b = sum(held["broad"]) / len(held["broad"]) if held["broad"] else 1.0
    gate = max(0.0, 1 - W_DUAL * (1 - h_d) - W_BROAD * (1 - h_b))
    return {
        "reward": round(d * gate, 6),
        "D": round(d, 6),
        "h_dual": round(h_d, 6),
        "h_broad": round(h_b, 6),
        "gate": round(gate, 6),
        "units": {
            u: {"pass": round(p, 4), "cases": len(units[u])}
            for u, p in per_unit.items()
        },
        "families": {
            f: {"pass": round(sum(v) / len(v), 4), "cases": len(v)}
            for f, v in sorted(families.items())
        },
        "held": {
            k: {"pass": round(sum(v) / len(v), 4) if v else None, "cases": len(v)}
            for k, v in held.items()
        },
    }


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    for name in ("reward.txt", "reward.json", "metrics.json"):
        (LOGS / name).unlink(missing_ok=True)
    notes: list[str] = []
    try:
        cases, expected = prepare()
        driver = build(notes)
        outputs = run_batches(driver, cases) if driver else {}
    except EvaluationError as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 1
    metrics = score(cases, expected, outputs)
    metrics |= {
        "release": os.environ["RELEASE"],
        "notes": notes,
        "cases": len(cases),
        "outputs": len(outputs),
    }
    (LOGS / "metrics.json").write_text(json.dumps(metrics, indent=1))
    (LOGS / "reward.txt").write_text(f"{metrics['reward']}\n")
    print(
        json.dumps(
            {
                k: metrics[k]
                for k in ("reward", "D", "h_dual", "h_broad", "cases", "outputs")
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
