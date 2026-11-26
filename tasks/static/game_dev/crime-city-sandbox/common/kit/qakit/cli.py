"""The qa command: run QA's playtests against the game and list what does not hold.

  qa run  [--game DIR] [--plans DIR] [--work DIR] [--json FILE] [PLAYTEST ...]
  qa list [PLAYTEST ...]

qa run copies the game (without its .godot folder), adds QA's telemetry node, imports the
copy headless, then plays each playtest in fresh game processes and checks its
expectations, plus the ones every playtest carries: the game keeps running (PF-8), the
telemetry node is left alone (AC-18), entity ids hold (AC-4) and events carry their
fields (AC-13). It prints each playtest that does not hold with the expectations that
failed and what was measured. The game itself is never changed.

Exit status: 0 when every expectation held, 1 when one did not (or the copy could not be
prepared), 2 when qa itself could not run (a malformed playtest, no Godot binary).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import expect
from .play import Play, PlayError, load_play, run_play
from .prepare import LIB_SUFFIX, prepare
from .procs import Limits, kill_all_live, which_godot
from .session import SessionOptions

KIT = Path(__file__).resolve().parent.parent
PLAYTESTS = KIT / "playtests"
MARKER = ".qa-run"


def telemetry_library(explicit: str | None) -> Path:
    """The telemetry library: the explicit path, $QA_TELEMETRY, then the kit's own copy."""
    plat = "darwin-arm64" if sys.platform == "darwin" else "linux-x86_64"
    for cand in (
        explicit,
        os.environ.get("QA_TELEMETRY"),
        str(KIT / "telemetry" / f"libtelemetry{LIB_SUFFIX}"),
        str(KIT.parent / "probe" / "build" / plat / f"libtelemetry{LIB_SUFFIX}"),
    ):
        if cand and Path(cand).is_file():
            return Path(cand).resolve()
    raise FileNotFoundError(
        "no QA telemetry library: set QA_TELEMETRY or pass --telemetry"
    )


def free_memory_percent() -> int | None:
    """System-wide free memory from memory_pressure (macOS), or None."""
    if not shutil.which("memory_pressure"):
        return None
    out = subprocess.run(
        ["memory_pressure"], capture_output=True, text=True, check=False
    ).stdout
    m = re.search(r"System-wide memory free percentage:\s*(\d+)%", out)
    return int(m.group(1)) if m else None


def memory_wait():
    """With $QA_MEM_FLOOR set, a hook that waits for that much free memory; else None."""
    floor = os.environ.get("QA_MEM_FLOOR")
    if not floor:
        return None
    poll = float(os.environ.get("QA_MEM_POLL_S", "60"))

    def wait() -> None:
        while True:
            pct = free_memory_percent()
            if pct is None or pct >= int(floor):
                return
            print(
                f"  (waiting for free memory: {pct}% < {floor}%)",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(poll)

    return wait


def find_playtests(names: list[str]) -> list[Path]:
    """Playtest files: the given files, names (such as world.replay/two-paces) or folders."""
    if not names:
        return sorted(PLAYTESTS.glob("*.json"))
    out = []
    for n in names:
        p = Path(n)
        if p.is_dir():
            out += sorted(p.glob("*.json"))
        elif p.is_file():
            out.append(p)
        else:
            cand = PLAYTESTS / (n.replace("/", ".") + ".json")
            if not cand.is_file():
                raise FileNotFoundError(f"no playtest {n}")
            out.append(cand)
    return out


def load_all(paths: list[Path]) -> list[Play]:
    """Load and check every playtest first, so a malformed one stops nothing midway."""
    return [load_play(p) for p in paths]


def short(value: object, limit: int = 240) -> str:
    """Compact JSON of a value, cut to limit characters."""
    text = json.dumps(value, default=str, separators=(", ", ": "))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def describe(o: expect.Outcome) -> list[str]:
    """The lines that explain one expectation that did not hold."""
    head = f"  - {o.id}" + (f" ({o.rule})" if o.rule else "")
    if o.kind == "pre":
        head += " [the situation this playtest sets up]"
    lines = [head + (f": {o.says}" if o.says else "")]
    lines.append(f"      {o.note or 'could not be measured'}")
    if o.measured:
        lines.append(f"      measured: {short(o.measured)}")
    return lines


def cmd_list(a: argparse.Namespace) -> int:
    """Print each playtest with the rules it exercises and what it is about."""
    plays = load_all(find_playtests(a.playtests))
    for p in plays:
        rules = ", ".join(p.rules)
        about = p.raw.get("about", "")
        print(f"{p.name}  ({rules})" + (f"\n    {about}" if about else ""))
    return 0


def prepare_work(work: Path) -> None:
    """Make an empty work folder; an earlier qa run's folder is cleared, nothing else."""
    if work.exists():
        if not (work / MARKER).is_file():
            raise FileExistsError(
                f"{work} exists and was not made by qa run; pick another --work"
            )
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / MARKER).write_text("made by qa run\n")


def cmd_run(a: argparse.Namespace) -> int:
    """Prepare the game, play the playtests, print what does not hold."""
    plays = load_all(find_playtests(a.playtests))
    godot = which_godot(a.godot)
    library = telemetry_library(a.telemetry)
    game = Path(a.game).resolve()
    plans = Path(a.plans).resolve()
    if not plans.is_dir():
        raise FileNotFoundError(f"no plan folder at {plans} (pass --plans)")
    work = Path(a.work).expanduser().resolve()
    prepare_work(work)
    gate = memory_wait()
    print(f"QA playtests on {game}")
    prep = prepare(
        game, work / "game", godot, library, random.Random(), work / "prep",
        Limits(wall_s=600, memory_mb=4096), gate,
    )  # fmt: skip
    if not prep.ready:
        print("The game could not be prepared for QA:")
        for problem in prep.problems:
            print(f"  - {problem}")
        print(f"  import log: {work / 'prep' / 'import.log'}")
        return 1
    print(f"Imported a copy with QA's telemetry in {prep.import_s:.1f} s.\n")
    report = []
    all_held = True
    for play in plays:
        folder = work / "plays" / play.name.replace("/", ".")

        def options(
            _k: int, _n: int, run_folder: Path, _p: Play = play
        ) -> SessionOptions:
            lim = _p.limits
            return SessionOptions(
                home=run_folder / "home",
                log_path=run_folder / "game.log",
                limits=Limits(
                    cpu_s=lim.get("cpu_s", 600),
                    memory_mb=lim.get("memory_mb", 1536),
                    disk_mb=lim.get("disk_mb", 1024),
                ),
                boot_s=float(lim.get("boot_s", 60)),
                step_s=float(lim.get("step_s", 30)),
                before_start=gate,
            )

        rec = run_play(play, prep.game_dir, godot, folder, options, plans=plans)
        outcomes = expect.check_play(rec) + expect.standing(rec)
        failed = [o for o in outcomes if o.ok is not True]
        all_held = all_held and not failed
        rules = ", ".join(play.rules)
        print(f"{play.name}  ({rules})")
        if not failed:
            print("  every expectation holds")
        else:
            for o in sorted(
                failed, key=lambda o: (o.kind != "standing", o.kind != "pre")
            ):
                for line in describe(o):
                    print(line)
            stopped = [r.error for r in rec.runs if r.error]
            if stopped:
                e = stopped[0]
                print(
                    f"  the run stopped at step {e.get('step')}: {e.get('kind')}: {e.get('message')}"
                )
            print(f"  logs and traces: {folder}")
        report.append(
            {
                "playtest": play.name,
                "rules": list(play.rules),
                "held": not failed,
                "expectations": [
                    {
                        k: getattr(o, k)
                        for k in (
                            "id",
                            "rule",
                            "says",
                            "kind",
                            "ok",
                            "note",
                            "measured",
                        )
                    }
                    for o in outcomes
                ],
                "stopped": [r.error for r in rec.runs if r.error],
            }
        )
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1, default=str))
    print(f"\nCopies, logs and traces: {work}")
    return 0 if all_held else 1


def parser() -> argparse.ArgumentParser:
    """The command line."""
    ap = argparse.ArgumentParser(
        prog="qa",
        description="QA's playtests for the game: run them and list what does not hold.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run playtests against the game")
    run.add_argument(
        "playtests", nargs="*", help="playtest names or files (default: all of them)"
    )
    run.add_argument(
        "--game", default="/app/game", help="the game project (default /app/game)"
    )
    run.add_argument(
        "--plans",
        default="/app/design/plan",
        help="the plan folder the game is given (--plan-dir)",
    )
    run.add_argument(
        "--work", default="~/.cache/qa/last", help="where the copy, logs and traces go"
    )
    run.add_argument("--json", help="also write what was found to this file as JSON")
    run.add_argument(
        "--godot", help="the Godot binary (default $QA_GODOT, /opt/godot/godot)"
    )
    run.add_argument(
        "--telemetry", help="QA's telemetry library (default: the kit's own)"
    )
    run.set_defaults(fn=cmd_run)
    ls = sub.add_parser("list", help="list the playtests and the rules they exercise")
    ls.add_argument("playtests", nargs="*")
    ls.set_defaults(fn=cmd_list)
    return ap


def main(argv: list[str] | None = None) -> int:
    """Entry point of the qa command."""
    a = parser().parse_args(argv)
    try:
        return a.fn(a)
    except (PlayError, FileNotFoundError, FileExistsError) as exc:
        print(f"qa: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    finally:
        kill_all_live()
