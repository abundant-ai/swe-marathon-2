"""Record the private scenarios, every answer the pinned reference server's.

usage: record_scenarios.py --count 2160 --runs 44 [--term 6] [--kill 3] [--screens 8] [--routines 12] [--seed N] [--out FILE]
                           [--media DIR] [--record FILE]
       record_scenarios.py --append --routines 12 [--seed N] [--out FILE] [--record FILE]

Two recorders, one file:

- the reference's own recorder (backend/tools/record_corpus.py) for the legacy request streams, read from the
  Stockwell repository's history (STOCKWELL_REPO), and for the media theme on the files in DIR (scripts/make_media.py);
- scripts/record_live.py for `--runs` months of trading, one unit per day, with the web client's screens after each
  and planned restarts in `--term` + `--kill` of them; their supplier invoices and photos are written under DIR/trading;
  then the counts and kits (below) and `--routines` scenarios of each office routine (record_live.py ROUTINES), the
  documented calls the legacy streams never make or only ever see refused.

`--append` records the routines alone, with the same seed, and adds them at the end of the corpus already at --out,
where a full recording puts them; every scenario the corpus holds stays byte for byte, so the file is the one a full
recording with --routines gives. It refuses a corpus that holds any of their themes already, and brings the record up
to date (its digest and the routines' count).

The legacy streams are filtered (QA 05 S2): a scenario whose every write is refused is left out (a crawl of the demo
company and the role table answer it), and in the counts and kits themes only scenarios that post a count or build a
kit are kept. The live recorder makes as many counts and kits, start to finish, as the filter took out.

The corpus holds the scenarios and nothing else, since it ships to the verifier image. How it was recorded (the seed,
the legacy commit, the counts left out, the media set's digest and the live recorder's settings) goes to the record file
with the corpus's SHA-256: experiment/recording.json for the task's own corpus, never committed or packaged; for any
other --out, a `.recording.json` beside it. A record file inside the folders the bundle is made from is refused.

Without --seed the seed comes from experiment/seeds.json (scripts/seeds.py), which is never committed. The live
recorder needs a Python with PyMuPDF, Pillow and numpy (MEDIA_PYTHON, default python3), ffmpeg and node.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from reference import TASK_ROOT, checkout, python, repository
from seeds import seed as private_seed
from verifier.replay import iter_scenarios

CORPUS = TASK_ROOT / "tests" / "private" / "scenarios.json"
RECORDING = (
    TASK_ROOT / "experiment" / "recording.json"
)  # Git-ignored with the rest of experiment/, and never packaged
PACKAGED = tuple(
    TASK_ROOT / name for name in ("environment", "instruction.md", "tests", "solution")
)  # where scripts/package_step.py takes the bundle's files from


def media_python() -> str:
    """MEDIA_PYTHON, or the first python3 on PATH that can make the month's files (PyMuPDF, Pillow, numpy)."""
    if os.environ.get("MEDIA_PYTHON"):
        return os.environ["MEDIA_PYTHON"]
    for folder in os.environ.get("PATH", "").split(os.pathsep) + ["/usr/bin"]:
        candidate = Path(folder) / "python3"
        if (
            candidate.is_file()
            and subprocess.run(
                [str(candidate), "-c", "import fitz, PIL, numpy"],
                check=False,
                capture_output=True,
            ).returncode
            == 0
        ):
            return str(candidate)
    raise SystemExit("no python3 with PyMuPDF, Pillow and numpy: set MEDIA_PYTHON")


def reaches_its_work(scenario: dict) -> bool:
    """Whether a legacy scenario changes its workspace: at least one write answered 2xx; for counts, a count posted; for
    kits, a kit built."""
    steps = scenario["steps"]

    def done(prefix: str, suffix: str) -> bool:
        return any(
            step["method"] == "POST"
            and step["path"].startswith(prefix)
            and step["path"].endswith(suffix)
            and 200 <= step["status"] < 300
            for step in steps
        )

    if scenario["theme"] == "counts":
        return done("/stock/counts/", "/post")
    if scenario["theme"] == "kits":
        return done("/kits/", "/builds")
    return any(
        step["method"] != "GET" and 200 <= step["status"] < 300 for step in steps
    )


def live_command(
    args: argparse.Namespace,
    seed: int,
    media: Path,
    out: Path,
    counts: int = 0,
    kits: int = 0,
) -> list[str]:
    return [
        media_python(),
        str(Path(__file__).resolve().parent / "record_live.py"),
        "--runs",
        str(args.runs),
        "--term",
        str(args.term),
        "--kill",
        str(args.kill),
        "--screens",
        str(args.screens),
        "--counts",
        str(counts),
        "--kits",
        str(kits),
        "--routines",
        str(args.routines),
        "--seed",
        str(seed),
        "--media",
        str(media.resolve()),
        "--out",
        str(out),
    ]


def append(args: argparse.Namespace, seed: int, record_file: Path) -> int:
    """Record the routines alone and add them at the end of the corpus at --out, as a full recording places them.

    The corpus is `{"scenarios":[...]}` and a newline, written by main() below: what is added goes in before its closing
    `]}`, each scenario written exactly as main() writes it, so every scenario already there keeps its bytes and the file
    is the one a full recording with the same seed and --routines gives (a check in checks/test_backoffice.py records
    both ways and compares them). Nothing under the media folder is touched: the routines upload no file.
    """
    old = args.out.read_text()
    if not old.startswith('{"scenarios":[') or not old.endswith("]}\n"):
        raise SystemExit(f"{args.out} is not a corpus this script wrote")
    themes, ids = set(), set()
    for scenario in iter_scenarios(old):
        themes.add(scenario["theme"])
        ids.add(scenario["id"])
    with tempfile.TemporaryDirectory(prefix="stockwell-routines-") as folder:
        live = Path(folder) / "live.json"
        args.runs = args.term = args.kill = args.screens = 0
        done = subprocess.run(
            live_command(args, seed, Path(folder) / "media", live), check=False
        )
        if done.returncode != 0:
            return done.returncode
        added = json.loads(live.read_text())["scenarios"]
    repeated = sorted({scenario["theme"] for scenario in added} & themes)
    if repeated or any(scenario["id"] in ids for scenario in added):
        raise SystemExit(
            f"{args.out} holds routines already ({', '.join(repeated) or 'their ids'}): record it again in full instead"
        )
    joined = ",".join(
        json.dumps(scenario, sort_keys=True, separators=(",", ":"))
        for scenario in added
    )
    corpus = (
        old[:-3]
        + ("," if old != '{"scenarios":[]}\n' and joined else "")
        + joined
        + "]}\n"
    )
    args.out.write_text(corpus)
    record = (
        json.loads(record_file.read_text())
        if record_file.is_file()
        else {"recorded_with": {}}
    )
    record["corpus_sha256"] = hashlib.sha256(corpus.encode()).hexdigest()
    record["recorded_with"].setdefault("live", {})["routines"] = args.routines
    record_file.parent.mkdir(parents=True, exist_ok=True)
    record_file.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "appended": len(added),
                "requests": sum(len(s["steps"]) for s in added),
                "scenarios": len(ids) + len(added),
                "out": str(args.out),
                "record": str(record_file),
            }
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--count",
        type=int,
        help="scenarios from the legacy request streams (required unless --append)",
    )
    parser.add_argument("--runs", type=int, default=0, help="months of trading")
    parser.add_argument("--term", type=int, default=0)
    parser.add_argument("--kill", type=int, default=0)
    parser.add_argument("--screens", type=int, default=0)
    parser.add_argument(
        "--routines",
        type=int,
        default=0,
        help="scenarios of each office routine (record_live.py ROUTINES)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="record only the routines and add them to the corpus at --out",
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out", type=Path, default=CORPUS)
    parser.add_argument(
        "--media",
        type=Path,
        default=TASK_ROOT / "experiment" / "media" / "private",
        help="the private files the scenarios upload (scripts/make_media.py); never the set shipped as samples",
    )
    parser.add_argument(
        "--record",
        type=Path,
        help="how the scenarios were recorded, the seed included (default: experiment/recording.json "
        "for the task's own corpus; for another --out, beside it as NAME.recording.json)",
    )
    args = parser.parse_args()
    if args.append and (
        args.routines < 1
        or args.count is not None
        or args.runs
        or not args.out.is_file()
    ):
        parser.error(
            "--append takes --routines N and an existing corpus at --out, and records nothing else"
        )
    if not args.append and args.count is None:
        parser.error("--count is required")
    record_file = args.record or (
        RECORDING
        if args.out.resolve() == CORPUS.resolve()
        else args.out.with_suffix(".recording.json")
    )
    if any(
        record_file.resolve().is_relative_to(folder.resolve()) for folder in PACKAGED
    ):
        raise SystemExit(
            f"{record_file} would be packaged with the task, and it holds the seed: write it elsewhere (--record)"
        )
    seed = args.seed if args.seed is not None else private_seed("scenarios")
    if args.append:
        return append(args, seed, record_file)
    reference = checkout()
    with tempfile.TemporaryDirectory(prefix="stockwell-record-") as folder:
        legacy, live = Path(folder) / "legacy.json", Path(folder) / "live.json"
        command = [
            *python(reference),
            "-B",
            str(reference / "backend" / "tools" / "record_corpus.py"),
            "--count",
            str(args.count),
            "--trading",
            "0",
            "--seed",
            str(seed),
            "--out",
            str(legacy),
        ]
        if (args.media / "manifest.json").is_file():
            command += ["--media", str(args.media.resolve())]
        else:
            print(
                f"no media set at {args.media}: recording without the media theme (make it with scripts/make_media.py)",
                file=sys.stderr,
            )
        done = subprocess.run(
            command,
            check=False,
            cwd=reference / "backend",
            env=dict(os.environ, STOCKWELL_GIT=str(repository())),
        )
        if done.returncode != 0:
            return done.returncode
        streams = json.loads(legacy.read_text())
        scenarios = [
            scenario for scenario in streams["scenarios"] if reaches_its_work(scenario)
        ]
        dropped: dict[str, int] = {}
        for scenario in streams["scenarios"]:
            if not reaches_its_work(scenario):
                dropped[scenario["theme"]] = dropped.get(scenario["theme"], 0) + 1
        record = {
            "legacy": dict(
                streams["recorded_with"], left_out=dict(sorted(dropped.items()))
            )
        }
        del streams
        print(
            json.dumps({"legacy left out": dict(sorted(dropped.items()))}),
            file=sys.stderr,
        )
        top_up = {theme: dropped.get(theme, 0) for theme in ("counts", "kits")}
        if args.runs or any(top_up.values()) or args.routines:
            args.media.mkdir(parents=True, exist_ok=True)
            done = subprocess.run(
                live_command(
                    args, seed, args.media, live, top_up["counts"], top_up["kits"]
                ),
                check=False,
            )
            if done.returncode != 0:
                return done.returncode
            months = json.loads(live.read_text())
            scenarios += months["scenarios"]
            record["live"] = months["recorded_with"]
        ids = [scenario["id"] for scenario in scenarios]
        if len(ids) != len(set(ids)):
            raise SystemExit("two scenarios share an id")
    corpus = (
        json.dumps({"scenarios": scenarios}, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(corpus)
    record_file.parent.mkdir(parents=True, exist_ok=True)
    record_file.write_text(
        json.dumps(
            {
                "corpus_sha256": hashlib.sha256(corpus.encode()).hexdigest(),
                "recorded_with": record,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )
    units = sum(len(s.get("units") or [None]) for s in scenarios)
    print(
        json.dumps(
            {
                "scenarios": len(scenarios),
                "units": units,
                "requests": sum(len(s["steps"]) for s in scenarios),
                "out": str(args.out),
                "record": str(record_file),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
