"""Run a merge driver over cases, one fresh scratch directory per case, and record status and bytes.

Runs inside a container. The driver gets: BASE OURS THEIRS -o OUT -l 7 -p PATH, in a scratch
directory outside any repository, with an empty HOME, a fresh TMPDIR, no git configuration, the C.UTF-8
locale, UTC, and a 10 s limit. A perturbed run changes the scratch path length and directory names
and pins the process to one CPU.

Usage: python3 -I run_cases.py --cases C.json --driver CMD --out R.json [--perturb] [--jobs N] [--keep]
CMD is either an executable path or "stub:MODE" (stubs.py beside this script).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_BASE = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
    "TZ": "UTC",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


def to_bytes(text: str) -> bytes:
    """Case text to bytes; a lone surrogate escape carries a raw (non-UTF-8) byte."""
    return text.encode("utf-8", "surrogateescape")


def run_one(args: tuple) -> dict:
    """Run the driver on one case and return its status, output hash and (optionally) output."""
    case, driver, perturb, keep, timeout = args
    root = tempfile.mkdtemp(prefix=("p" * 40 + "-") if perturb else "m-", dir="/tmp")
    work = os.path.join(root, "work-perturbed-dir" if perturb else "w")
    home, tmp = os.path.join(root, "home"), os.path.join(root, "tmp")
    for d in (work, home, tmp):
        os.makedirs(d)
    names = ("b.txt", "o.txt", "t.txt") if perturb else ("base", "ours", "theirs")
    paths = []
    for name, key in zip(names, ("base", "ours", "theirs")):
        p = os.path.join(work, name)
        with open(p, "wb") as fh:
            fh.write(to_bytes(case[key]))
        paths.append(p)
    out = os.path.join(work, "merged.out" if perturb else "out")
    cmd = (
        [sys.executable, "-I", os.path.join(HERE, "stubs.py"), driver[5:]]
        if driver.startswith("stub:")
        else [driver]
    )
    cmd += [*paths, "-o", out, "-l", "7", "-p", case["path"]]
    if perturb:
        cmd = ["taskset", "-c", "0", *cmd]
    env = dict(ENV_BASE, HOME=home, TMPDIR=tmp)
    rec: dict = {"id": case["id"]}
    try:
        r = subprocess.run(
            cmd, check=False, cwd=work, env=env, capture_output=True, timeout=timeout
        )
        rec["status"] = r.returncode
        rec["stderr_tail"] = r.stderr[-300:].decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        rec["status"] = "timeout"
    if os.path.exists(out):
        data = Path(out).read_bytes()
        rec["sha256"] = hashlib.sha256(data).hexdigest()
        if keep:
            rec["out"] = base64.b64encode(data).decode()
    else:
        rec["sha256"] = None
    shutil.rmtree(root, ignore_errors=True)
    return rec


def main() -> None:
    """Run every case and write the records."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--driver", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--perturb", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--ids", help="file with case ids to run (one per line)")
    args = ap.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.ids:
        wanted = set(Path(args.ids).read_text().split())
        cases = [c for c in cases if c["id"] in wanted]
    jobs = [(c, args.driver, args.perturb, args.keep, args.timeout) for c in cases]
    with ProcessPoolExecutor(max_workers=1 if args.perturb else args.jobs) as pool:
        recs = list(pool.map(run_one, jobs, chunksize=8))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(recs, fh)
    print(
        f"{len(recs)} cases run with {args.driver}{' (perturbed)' if args.perturb else ''}"
    )


if __name__ == "__main__":
    main()
