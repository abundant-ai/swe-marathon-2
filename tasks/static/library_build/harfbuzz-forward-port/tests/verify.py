"""Build the delivered tree with the product's commands, run every case batch, and publish the reward.

The release to check comes from the verifier environment (`RELEASE`), never from the tree. The tree's own build
scripts and library code run only as the unprivileged `builder` user, which cannot read the recorded outputs in
/tests/private; a root process compares the outputs after each driver has exited. An evaluation fault leaves no
reward file.

Reward: D x G. D is the mean over the graded changes of each change's pass fraction. G is the held-fixed gate:
h_d x (1 - 0.10 x (1 - h_b)), where h_d is the mean over the changes of the pass fraction of each change's
neighbouring cases (inputs one stated condition away, on which the library must behave as 14.3.0 does) and h_b the
pass fraction of the other unchanged cases.

With RECORD=1 the outputs of every case are written to /logs/verifier/outputs.tsv and nothing is scored.
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
DRIVERS = TESTS / "driver"
TREE = Path("/app/harfbuzz")
WORK = Path("/tmp/hbv")
LOGS = Path("/logs/verifier")
RELEASES = ("15.0.0", "15.1.0", "15.2.0")
W_BROAD = 0.10
# Case driver per case kind. hbdrv, hbapi and hbmeta use API that every release has; each hbapiNN probes one function
# the notes add, so a tree without that function fails only that function's cases.
PROGRAMS = {
    "shape": "hbdrv",
    "api": "hbapi",
    "meta": "hbmeta",
    "api48": "hbapi48",
    "api49": "hbapi49",
    "api51": "hbapi51",
}
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


def prepare(record: bool) -> tuple[list[dict], dict[str, str]]:
    release = os.environ.get("RELEASE", "")
    if release not in RELEASES:
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
        expected = (
            {}
            if record
            else json.loads((PRIVATE / "expected.json").read_text())[release]
        )
    except (OSError, ValueError, KeyError) as exc:
        raise EvaluationError(f"private inputs unreadable: {exc}") from exc
    if not cases or (not record and any(c["id"] not in expected for c in cases)):
        raise EvaluationError("private inputs incomplete")
    for kind in {c.get("drv", "shape") for c in cases}:
        if kind not in PROGRAMS or not (DRIVERS / f"{PROGRAMS[kind]}.c").is_file():
            raise EvaluationError(f"driver for {kind!r} missing")
    return cases, expected


MAX_FILE = 512 * 1024 * 1024  # no file of a HarfBuzz tree comes near this
MAX_OUTPUT = 256 * 1024 * 1024  # far above any batch's real output
BATCH_TIMEOUT = 300  # one driver process over one font's cases
DRIVER_BUDGET = 1200  # all batches together, so a hanging library cannot outlast the verifier's own limit


def skip_entries(directory: str, names: list[str]) -> set[str]:
    """copytree filter: leave out meson build directories, special files (pipes, sockets, devices) and huge files.

    Symbolic links are copied as links (copytree runs with symlinks=True), never followed.
    """
    skipped = set()
    for n in names:
        path = Path(directory) / n
        if path.is_symlink():
            continue
        if path.is_dir():
            if (path / "meson-private").is_dir():
                skipped.add(n)
        elif not path.is_file() or path.stat().st_size > MAX_FILE:
            skipped.add(n)
    return skipped


def step(notes: list[str], name: str, cmd: list[str], cwd: Path, limit: int) -> bool:
    started = time.time()
    result = as_builder(cmd, cwd=cwd, timeout=limit)
    notes.append(f"{name}: exit {result.returncode} in {time.time() - started:.0f}s")
    if result.returncode:
        (WORK / f"{name}.log").write_bytes(result.stdout or b"")
    return result.returncode == 0


def build(notes: list[str], kinds: set[str]) -> dict[str, Path]:
    """Copy and build the delivered tree as builder; return the drivers that compiled and linked against it."""
    WORK.mkdir(
        parents=True
    )  # a fresh container each time; an existing one fails loudly
    if not TREE.is_dir():
        notes.append("/app/harfbuzz is missing")
        return {}
    # Build out of tree, and leave out build directories, special files and huge files the tree may carry.
    shutil.copytree(TREE, WORK / "tree", symlinks=True, ignore=skip_entries)
    subprocess.run(["chown", "-R", "builder:builder", str(WORK)], check=True)
    tree = WORK / "tree"
    if not (
        step(notes, "setup", MESON, tree, 900)
        and step(
            notes, "build", ["ninja", "-C", str(WORK / "b"), "-j", "4"], tree, 1800
        )
    ):
        return {}
    drivers: dict[str, Path] = {}
    for kind in sorted(kinds):
        name = PROGRAMS[kind]
        obj, exe = WORK / f"{name}.o", WORK / name
        compiled = step(
            notes,
            f"{name}-compile",
            [
                "cc", "-O2", "-Werror=implicit-function-declaration", "-c",
                "-Isrc", f"-I{WORK / 'b' / 'src'}", "-o", str(obj), str(DRIVERS / f"{name}.c"),
            ],
            tree,
            300,
        ) and step(
            notes,
            f"{name}-link",
            ["c++", "-o", str(exe), str(obj), str(WORK / "b" / "src" / "libharfbuzz.a"), "-lm"],
            tree,
            300,
        )  # fmt: skip
        if compiled:
            drivers[kind] = exe
    return drivers


def run_batches(drivers: dict[str, Path], cases: list[dict]) -> dict[str, str]:
    """One driver process per driver and font, so a hang or crash costs only that batch's cases."""
    batches: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        batches[(c.get("drv", "shape"), c["font"])].append(c)
    outputs: dict[str, str] = {}
    deadline = time.time() + DRIVER_BUDGET
    for n, ((kind, font), items) in enumerate(sorted(batches.items())):
        remaining = int(deadline - time.time())
        if kind not in drivers or remaining < 5:
            continue  # its cases fail: no driver, or the drivers have used up their time
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
            as_builder(
                [str(drivers[kind])],
                cwd=WORK,
                timeout=min(BATCH_TIMEOUT, remaining),
                stdin=fin,
                stdout=fout,
            )
        if out.stat().st_size > MAX_OUTPUT:
            continue  # a driver that floods its output fails its batch
        for line in out.read_text(errors="replace").splitlines():
            cid, _, result = line.partition("\t")
            outputs[cid] = result
    return outputs


def score(cases: list[dict], expected: dict[str, str], outputs: dict[str, str]) -> dict:
    units: dict[str, list[bool]] = defaultdict(list)
    duals: dict[str, list[bool]] = defaultdict(list)
    broad: list[bool] = []
    families: dict[str, list[bool]] = defaultdict(list)
    for c in cases:
        ok = outputs.get(c["id"]) == expected[c["id"]]
        if c["kind"] == "changed":
            units[c["unit"]].append(ok)
            families[c["family"]].append(ok)
        elif c["kind"] == "dual":
            duals[c["unit"]].append(ok)
        else:
            broad.append(ok)
    per_unit = {u: sum(v) / len(v) for u, v in sorted(units.items())}
    per_dual = {u: sum(v) / len(v) for u, v in sorted(duals.items())}
    d = sum(per_unit.values()) / len(per_unit) if per_unit else 0.0
    h_d = sum(per_dual.values()) / len(per_dual) if per_dual else 1.0
    h_b = sum(broad) / len(broad) if broad else 1.0
    gate = h_d * (1 - W_BROAD * (1 - h_b))
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
        "neighbours": {
            u: {"pass": round(p, 4), "cases": len(duals[u])}
            for u, p in per_dual.items()
        },
        "families": {
            f: {"pass": round(sum(v) / len(v), 4), "cases": len(v)}
            for f, v in sorted(families.items())
        },
        "broad": {
            "pass": round(h_b, 4) if broad else None,
            "cases": len(broad),
        },
    }


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    for name in ("reward.txt", "reward.json", "metrics.json", "outputs.tsv"):
        (LOGS / name).unlink(missing_ok=True)
    record = os.environ.get("RECORD") == "1"
    notes: list[str] = []
    try:
        cases, expected = prepare(record)
        drivers = build(notes, {c.get("drv", "shape") for c in cases})
        outputs = run_batches(drivers, cases)
    except EvaluationError as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 1
    if record:
        if "shape" not in drivers:
            print("evaluation error: the reference tree did not build", file=sys.stderr)
            return 1
        (LOGS / "outputs.tsv").write_text(
            "".join(f"{c['id']}\t{outputs.get(c['id'], '!missing')}\n" for c in cases)
        )
        print(
            json.dumps(
                {"recorded": len(cases), "drivers": sorted(drivers), "notes": notes}
            )
        )
        return 0
    metrics = score(cases, expected, outputs)
    metrics |= {
        "release": os.environ["RELEASE"],
        "notes": notes,
        "drivers": sorted(drivers),
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
