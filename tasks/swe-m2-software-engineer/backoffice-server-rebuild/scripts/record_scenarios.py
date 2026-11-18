"""Record the private scenarios, every answer the pinned reference server's.

usage: record_scenarios.py --count 2160 --runs 44 [--term 6] [--kill 3] [--screens 8] [--seed N] [--out FILE] [--media DIR]

Two recorders, one file:

- the reference's own recorder (backend/tools/record_corpus.py) for the legacy request streams, read from the
  Stockwell repository's history (STOCKWELL_REPO), and for the media theme on the files in DIR (scripts/make_media.py);
- scripts/record_live.py for `--runs` months of trading, one unit per day, with the web client's screens after each
  and planned restarts in `--term` + `--kill` of them; their supplier invoices and photos are written under DIR/trading.

The legacy streams are filtered (QA 05 S2): a scenario whose every write is refused is left out (a crawl of the demo
company and the role table answer it), and in the counts and kits themes only scenarios that post a count or build a
kit are kept. The live recorder makes as many counts and kits, start to finish, as the filter took out.

Without --seed the seed comes from experiment/seeds.json (scripts/seeds.py), which is never committed. The live
recorder needs a Python with PyMuPDF, Pillow and numpy (MEDIA_PYTHON, default python3), ffmpeg and node.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reference import TASK_ROOT, checkout, python, repository  # noqa: E402
from seeds import seed as private_seed  # noqa: E402


def media_python() -> str:
    """MEDIA_PYTHON, or the first python3 on PATH that can make the month's files (PyMuPDF, Pillow, numpy)."""
    if os.environ.get("MEDIA_PYTHON"):
        return os.environ["MEDIA_PYTHON"]
    for folder in os.environ.get("PATH", "").split(os.pathsep) + ["/usr/bin"]:
        candidate = Path(folder) / "python3"
        if candidate.is_file() and subprocess.run([str(candidate), "-c", "import fitz, PIL, numpy"], capture_output=True).returncode == 0:
            return str(candidate)
    raise SystemExit("no python3 with PyMuPDF, Pillow and numpy: set MEDIA_PYTHON")


def reaches_its_work(scenario: dict) -> bool:
    """Whether a legacy scenario changes its workspace: at least one write answered 2xx; for counts, a count posted; for
    kits, a kit built."""
    steps = scenario["steps"]

    def done(prefix: str, suffix: str) -> bool:
        return any(step["method"] == "POST" and step["path"].startswith(prefix) and step["path"].endswith(suffix) and 200 <= step["status"] < 300
                   for step in steps)

    if scenario["theme"] == "counts":
        return done("/stock/counts/", "/post")
    if scenario["theme"] == "kits":
        return done("/kits/", "/builds")
    return any(step["method"] != "GET" and 200 <= step["status"] < 300 for step in steps)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, required=True, help="scenarios from the legacy request streams")
    parser.add_argument("--runs", type=int, default=0, help="months of trading")
    parser.add_argument("--term", type=int, default=0)
    parser.add_argument("--kill", type=int, default=0)
    parser.add_argument("--screens", type=int, default=0)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out", type=Path, default=TASK_ROOT / "steps" / "01-rebuild-server" / "tests" / "private" / "scenarios.json")
    parser.add_argument("--media", type=Path, default=TASK_ROOT / "experiment" / "media" / "private",
                        help="the private files the scenarios upload (scripts/make_media.py); never the set shipped as samples")
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else private_seed("scenarios")
    reference = checkout()
    with tempfile.TemporaryDirectory(prefix="stockwell-record-") as folder:
        legacy, live = Path(folder) / "legacy.json", Path(folder) / "live.json"
        command = [*python(reference), "-B", str(reference / "backend" / "tools" / "record_corpus.py"), "--count", str(args.count), "--trading", "0",
                   "--seed", str(seed), "--out", str(legacy)]
        if (args.media / "manifest.json").is_file():
            command += ["--media", str(args.media.resolve())]
        else:
            print(f"no media set at {args.media}: recording without the media theme (make it with scripts/make_media.py)", file=sys.stderr)
        done = subprocess.run(command, cwd=reference / "backend", env=dict(os.environ, STOCKWELL_GIT=str(repository())))
        if done.returncode != 0:
            return done.returncode
        scenarios = json.loads(legacy.read_text())
        kept = [scenario for scenario in scenarios["scenarios"] if reaches_its_work(scenario)]
        dropped: dict[str, int] = {}
        for scenario in scenarios["scenarios"]:
            if not reaches_its_work(scenario):
                dropped[scenario["theme"]] = dropped.get(scenario["theme"], 0) + 1
        scenarios["scenarios"] = kept
        scenarios["recorded_with"]["left_out"] = dict(sorted(dropped.items()))
        print(json.dumps({"legacy left out": dict(sorted(dropped.items()))}), file=sys.stderr)
        top_up = {theme: dropped.get(theme, 0) for theme in ("counts", "kits")}
        if args.runs or any(top_up.values()):
            args.media.mkdir(parents=True, exist_ok=True)
            done = subprocess.run([media_python(), str(Path(__file__).resolve().parent / "record_live.py"),
                                   "--runs", str(args.runs), "--term", str(args.term), "--kill", str(args.kill), "--screens", str(args.screens),
                                   "--counts", str(top_up["counts"]), "--kits", str(top_up["kits"]),
                                   "--seed", str(seed), "--media", str(args.media.resolve()), "--out", str(live)])
            if done.returncode != 0:
                return done.returncode
            months = json.loads(live.read_text())
            scenarios = {"scenarios": scenarios["scenarios"] + months["scenarios"],
                         "recorded_with": {"legacy": scenarios["recorded_with"], "live": months["recorded_with"]}}
        ids = [scenario["id"] for scenario in scenarios["scenarios"]]
        if len(ids) != len(set(ids)):
            raise SystemExit("two scenarios share an id")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scenarios, sort_keys=True, separators=(",", ":")) + "\n")
    units = sum(len(s.get("units") or [None]) for s in scenarios["scenarios"])
    print(json.dumps({"scenarios": len(scenarios["scenarios"]), "units": units, "requests": sum(len(s["steps"]) for s in scenarios["scenarios"]),
                      "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
