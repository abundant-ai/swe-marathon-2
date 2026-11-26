"""Re-runs recorded program runs from their saved input and compares with the record.

One run gives several checks, each a test: "exit" (exit code), "files" (no file missing,
extra, changed or removed beyond what OpenFOAM did), "stdout", "stderr", and "file <path>"
for each file OpenFOAM wrote.

  check      run once and report each check (put other programs first on PATH to test them)
  stability  run K times with OpenFOAM. Numbers in printed output and text files that change
             are run-time information (timings, dates, ids) and are masked. Numbers in
             OpenFOAM data files that change get tolerance FACTOR x the change; if they are
             integers, or anything else changes, the record is unstable. Runs that compile code
             at run time are out of scope. Writes stability.json.
  dummy      run once with a do-nothing program first on PATH; checks it passes are dropped
             (run with each do-nothing program; the passes add up).
             Adds "dummy_passes" to stability.json.

usage: replay.py check|stability|dummy <verifier dir> <records or record dirs>...
                 [--store dir] [--repeats K] [--timeout s]
"""

import argparse
import json
import os
import sys
from pathlib import Path

FACTOR = 10
R = None  # verifier.recorded, imported in main() from the given verifier folder


class Record:
    """A record folder of a harvest run: cmd.json, input.json, output.json, removed, exit,
    stdout, stderr; file contents in the shared store, named by sha256."""

    def __init__(self, path, store):
        self.path = path
        rd = lambda n: Path(os.path.join(path, n)).read_text(errors="replace")
        self.run = R.Record(
            json.loads(Path(os.path.join(path, "cmd.json")).read_text()),
            json.loads(Path(os.path.join(path, "input.json")).read_text()),
            json.loads(Path(os.path.join(path, "output.json")).read_text()),
            set(rd("removed").split()),
            int(rd("exit")),
            rd("stdout"),
            rd("stderr"),
            lambda h: os.path.join(store, h),
        )

    def stability(self):
        p = os.path.join(self.path, "stability.json")
        return json.load(open(p)) if os.path.exists(p) else {}

    def save_stability(self, st):
        with open(os.path.join(self.path, "stability.json"), "w") as stream:
            json.dump(st, stream, indent=1)


def Run(rec: Record, timeout):
    return R.Run(rec.run, R.Limits(env=dict(os.environ), timeout=timeout))


def check(run, tols=None, masked=(), calibrating=False):
    return R.check(run, tols, masked, calibrating)


def records(paths, store):
    """Complete records under the given paths. A run killed at the tutorial's time limit has no
    exit file; it is skipped."""
    out = []
    for d in paths:
        if os.path.exists(os.path.join(d, "cmd.json")):
            out.append(d)
        elif os.path.isdir(d):
            out += sorted(
                os.path.join(d, x)
                for x in os.listdir(d)
                if os.path.exists(os.path.join(d, x, "cmd.json"))
            )
    out = [p for p in out if os.path.exists(os.path.join(p, "exit"))]
    return [
        Record(
            p,
            store
            or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(p))), "store"
            ),
        )
        for p in out
    ]


def kept(rec: Record, names):
    """Checks that count as tests: the record is stable and the do-nothing program fails them."""
    st = rec.stability()
    if not st.get("stable"):
        return []
    return [n for n in names if n not in set(st.get("dummy_passes", ()))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "stability", "dummy"])
    ap.add_argument("verifier")
    ap.add_argument("records", nargs="+")
    ap.add_argument("--store")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=120)
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(a.verifier)))
    global R
    from verifier import recorded as R

    recs = records(a.records, a.store)
    total = passed = 0
    for rec in recs:
        name = os.path.relpath(rec.path)
        try:
            n_total, n_ok = run_one(a, rec, name)
        except Exception as e:  # a broken record must not stop the others  # noqa: BLE001 - Handle failures at the task boundary.
            print(f"ERROR    {name}: {type(e).__name__}: {e}", flush=True)
            if a.mode == "stability":
                rec.save_stability(
                    {"stable": False, "error": f"{type(e).__name__}: {e}"}
                )
            continue
        total += n_total
        passed += n_ok
    if a.mode == "check":
        print(f"{passed} of {total} checks pass")
    elif a.mode == "stability":
        print(f"{passed} of {total} records stable")


def run_one(a, rec, name):
    """Handles one record; returns (number counted, number passed)."""
    st = rec.stability()
    if a.mode in ("check", "dummy"):
        run = Run(rec, a.timeout)
        res = check(run, st.get("tolerances"), st.get("masked", ()))
        run.close()
        if a.mode == "dummy":
            passes = {n for n, r in res.items() if r.ok}
            st["dummy_passes"] = sorted(passes | set(st.get("dummy_passes", ())))
            rec.save_stability(st)
            return 0, 0
        names = kept(rec, res) if st else list(res)
        ok = [n for n in names if res[n].ok]
        print(f"{len(ok):3d}/{len(names):<3d} {run.seconds:6.2f}s  {name}", flush=True)
        for n in names:
            if not res[n].ok:
                print(f"          FAIL {n}: {res[n].mismatches[0]}", flush=True)
        return len(names), len(ok)
    if any("dynamicCode/" in f for f in rec.run.output):
        rec.save_stability(
            {"stable": False, "out_of_scope": "compiles code at run time"}
        )
        print(f"OUT OF SCOPE     {name}  (compiles code at run time)", flush=True)
        return 1, 0
    spreads, problems, secs = {}, [], []
    for _ in range(a.repeats):
        run = Run(rec, a.timeout)
        res = check(run, calibrating=True)
        secs.append(run.seconds)
        run.close()
        for r in res.values():
            problems += r.mismatches
            problems += [
                f"{k}: integer changes between identical runs"
                for k in r.int_paths
                if not _is_text(k)
            ]
            for k, v in r.spreads.items():
                spreads[k] = max(spreads.get(k, 0.0), v)
    varying = {k: v for k, v in spreads.items() if v > 0}
    masked = sorted(k for k in varying if _is_text(k))
    tolerances = {k: FACTOR * v for k, v in varying.items() if k not in masked}
    stable = not problems
    rec.save_stability(
        {
            "stable": stable,
            "repeats": a.repeats,
            "problems": problems[:10],
            "masked": masked,
            "tolerances": tolerances,
            "seconds": secs,
        }
    )
    print(
        ("STABLE   " if stable else "UNSTABLE ")
        + f"{max(secs):6.2f}s  {name}"
        + (f"  ({len(masked)} printed numbers masked)" if masked else "")
        + ("" if stable else "\n        " + "\n        ".join(problems[:3])),
        flush=True,
    )
    return 1, int(stable)


def _is_text(path):
    """Paths of numbers in printed output or in text files (not OpenFOAM data files)."""
    return path.startswith(("stdout ", "stderr ")) or ":" in path.split("#")[0]


if __name__ == "__main__":
    main()
