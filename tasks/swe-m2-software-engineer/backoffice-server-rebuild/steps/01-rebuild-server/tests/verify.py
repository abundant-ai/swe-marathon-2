"""Entry point of the step's tests: replay the private scenarios against the submitted server and publish the result."""

from __future__ import annotations

import contextlib
import json
import os
import pwd
import stat
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.replay import RUN_AS, EvaluationError, Progress, end_user_processes, evaluate  # noqa: E402

REWARD_FILES = ("reward.txt", "reward.json")
PENDING = ".reward.pending"
PLACEHOLDER = b"0.000000"  # a reward in [0, 1] written with six decimals always has this length
MANIFEST = ".fsmaint-manifest"  # written into /app/server by the collect hook (environment/fsmaint-sweep)
MANIFEST_READ = 1 << 16  # the hook writes at most about 50 KB: a first line, 40 one-line changes and the timer's lines
MISSING_MANIFEST = ("/app/server arrived without the collect hook's manifest (the hook did not run, or the copy was cut short); "
                    "it was scored as it arrived")
# The step allows 6,000 s, and that clock also covers copying the tests in and the results out. The replay ends at
# 5,400 s and winds down within about two minutes; whatever the evaluation is doing at this point, the reward is
# published from what it has decided, with a note.
HARD_STOP_SEC = 5_640
RUNNING = {"status": "evaluation_error", "error": "the evaluation did not finish: no reward was published"}


def reserve(output: Path) -> None:
    """Before any submitted code runs, write a placeholder the size of the reward under another name, and a summary
    that calls the evaluation unfinished.

    The server may fill the disk while it runs. The reward is later written over the
    placeholder's bytes in place and renamed, which needs no free space. If the evaluation dies before
    that (memory taken from it, say), no reward file exists, so the result is an evaluation error and
    never a 0, and the summary says so.
    """
    with open(output / PENDING, "wb") as placeholder:
        placeholder.write(PLACEHOLDER)
        placeholder.flush()
        os.fsync(placeholder.fileno())
    with contextlib.suppress(OSError):
        (output / "metrics.json").write_text(json.dumps(RUNNING) + "\n")


def publish(output: Path, metrics: dict[str, Any]) -> None:
    """Write the reward first, then the summary, then the per-scenario diagnostics.

    The reward goes over the placeholder `reserve` wrote, when there is one; the diagnostics can be
    large, and a full disk or any other failure writing them costs only those files.
    """
    results = metrics.pop("results", [])
    reward = f"{metrics['reward']:.6f}".encode()
    pending = output / PENDING
    if pending.is_file():
        with open(pending, "r+b") as placeholder:
            placeholder.write(reward)
            placeholder.truncate(len(reward))
        os.replace(pending, output / "reward.txt")
    else:
        (output / "reward.txt").write_bytes(reward)
    with contextlib.suppress(OSError):  # the "unfinished" summary from `reserve`; the real one follows if there is room
        (output / "metrics.json").unlink(missing_ok=True)
    for name, text in (("metrics.json", json.dumps(dict(metrics, status="completed"), indent=1, sort_keys=True) + "\n"),
                       ("scenario_results.json", json.dumps(results))):
        try:
            (output / name).write_text(text)
        except OSError as exc:
            print(f"could not write {name}: {exc}", flush=True)


def run_bounded(call: Callable[[], dict[str, Any]], progress: Progress, seconds: float) -> dict[str, Any]:
    """Run the evaluation, and if it has not returned within `seconds`, stop waiting and return the reward from what it
    has decided, with a note. The server's processes are ended after the reward is published.

    Raises:
        EvaluationError: The evaluation raised one, or ran out of time before it had read the scenarios.
    """
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["metrics"] = call()
        except BaseException as exc:  # noqa: BLE001 - handed to the caller
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(max(1.0, seconds))
    if "error" in outcome:
        raise outcome["error"]
    if "metrics" in outcome:
        return outcome["metrics"]
    if progress.ballast is not None:  # the evaluation's own clean-up has not run: room for the results
        progress.ballast.release()
    metrics = progress.summary("the evaluation did not finish before the step's time limit: the reward counts the scenarios it "
                               "had decided, and the others as not matched")
    if metrics is None:
        raise EvaluationError("The evaluation did not finish before the step's time limit")
    return metrics


def arrived(server: Path) -> tuple[int, int]:
    """Entries (files, directories and links; the manifest left out) under `server`, and bytes in its files (each file
    once, however many names it has), counted as the collect hook counts them."""
    entries = size = 0
    files: set[tuple[int, int]] = set()
    folders = [str(server)]
    while folders:
        folder = folders.pop()
        try:
            listing = os.scandir(folder)
        except OSError:
            continue
        with listing:
            for entry in listing:
                if folder == str(server) and entry.name == MANIFEST:
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                entries += 1
                if stat.S_ISDIR(info.st_mode):
                    folders.append(entry.path)
                elif stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in files:
                    files.add((info.st_dev, info.st_ino))
                    size += info.st_size
    return entries, size


def manifest_notes(server: Path) -> list[str]:
    return manifest_record(server)["notes"]


def manifest_record(server: Path) -> dict[str, Any]:
    """What the collect hook's manifest and the copy that arrived say about /app/server: `notes` for metrics.json, and
    whether the maintenance timer ended the agent's session (`ended_by_timer`, with the log's last lines in
    `timer_log`), which is recorded and never a reason to change the reward.

    The hook writes the manifest before the copy, for an empty directory too and for anything else it finds at
    /app/server, after bounding the tree and packing it once the way the copy packs it, so that nothing the agent
    leaves can make the copy fail. A tree that arrived is scored as it arrived, with a note when the manifest is
    missing or says the tree was refused. Only the manifest's first MANIFEST_READ bytes are read, which hold all the
    hook writes.

    More than the manifest counts can arrive where the copy could not keep a file's hard links and made copies of it;
    that tree is scored as it arrived, with a note.

    Raises:
        EvaluationError: Nothing arrived at all, so the copy never happened; or fewer entries or bytes arrived than the
            manifest counts, so the copy was cut short, which nothing the agent does can bring about.
    """
    try:
        empty = server.is_symlink() or not server.is_dir() or next(server.iterdir(), None) is None
    except OSError:
        empty = True
    if empty:
        raise EvaluationError("Nothing arrived: /app/server is missing or empty, though the collect hook writes a manifest for every tree")
    manifest = server / MANIFEST
    try:
        if manifest.is_file() and not manifest.is_symlink():
            with open(manifest, "rb") as handle:
                lines = handle.read(MANIFEST_READ).decode(errors="replace").splitlines()
        else:
            lines = None
    except OSError:
        lines = None
    if not lines:
        return {"notes": [MISSING_MANIFEST], "ended_by_timer": False, "timer_log": []}
    rest = [line for line in lines[1:] if line.strip()]
    timer_log = [line[len("timer: "):] for line in rest if line.startswith("timer: ")][-20:]
    notes = [f"collect hook: {line}" for line in rest if not line.startswith("timer: ")][:20]
    record = {"notes": notes, "ended_by_timer": any(" fired after " in line for line in timer_log), "timer_log": timer_log}
    head = lines[0].split()
    if head[:1] == ["refused"]:
        record["notes"] = notes or ["collect hook: /app/server was not copied"]
        return record
    if len(head) == 3 and head[0] == "complete" and all(value.isascii() and value.isdigit() for value in head[1:]):
        entries, size = arrived(server)
        counted = int(head[1]), int(head[2])
        if entries < counted[0] or size < counted[1]:
            raise EvaluationError(f"The copy arrived incomplete: {entries:,} of {counted[0]:,} entries and {size:,} of "
                                  f"{counted[1]:,} bytes")
        if (entries, size) != counted:
            record["notes"] = notes + [f"more arrived than the collect hook's manifest counts ({entries:,} entries and {size:,} bytes, "
                                       f"against {counted[0]:,} and {counted[1]:,}): hard links the copy could not keep arrive as "
                                       "copies; /app/server was scored as it arrived"]
        return record
    record["notes"] = notes + ["the collect hook's manifest could not be read; /app/server was scored as it arrived"]
    return record


def main() -> int:
    """Run one evaluation in this fresh container.

    Returns:
        Zero for a completed evaluation, including a failed submission; one for
        an evaluation error, which leaves no reward file.
    """
    started = time.monotonic()
    tests = Path(__file__).resolve().parent
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    for name in REWARD_FILES + ("metrics.json", PENDING):
        (output / name).unlink(missing_ok=True)
    code, published = 1, False
    try:
        if os.geteuid() != 0:
            raise EvaluationError("Verifier must start as root to isolate submitted code")
        for closed in (tests, output):
            closed.chmod(0o700)
        reserve(output)
        server = Path("/app/server")
        record = manifest_record(server)  # before the sandbox seals it; raises when nothing arrived
        scenarios = tests / "private" / "scenarios.json.gz"
        scenario_file = scenarios if scenarios.exists() else tests / "private" / "scenarios.json"
        progress = Progress()
        metrics = run_bounded(lambda: evaluate(server, scenario_file, Path("/work"), output, progress=progress), progress,
                              HARD_STOP_SEC - (time.monotonic() - started))
        metrics["notes"] = record["notes"] + metrics["notes"]
        # whether the maintenance timer ended the agent's session: recorded, never scored
        metrics["ended_by_timer"], metrics["timer_log"] = record["ended_by_timer"], record["timer_log"]
        publish(output, metrics)
        published, code = True, 0
        print(f"reward: {metrics['reward']:.6f} ({metrics['units_matched']}/{metrics['units_total']} units)", flush=True)
    except Exception as exc:  # noqa: BLE001 - every unexpected failure before the reward is out invalidates the evaluation
        if not published:  # once published, a later failure (a print to a full disk) never takes the reward back
            message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
            with contextlib.suppress(Exception):
                print(f"evaluation error: {message}", flush=True)
            for name in REWARD_FILES + (PENDING,):
                with contextlib.suppress(OSError):
                    (output / name).unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                (output / "metrics.json").write_text(json.dumps({"status": "evaluation_error", "error": message}) + "\n")
                (output / "verifier_error.txt").write_text(traceback.format_exc())
    finally:
        with contextlib.suppress(Exception):
            end_user_processes(pwd.getpwnam(RUN_AS).pw_uid)
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False, capture_output=True, timeout=60)
    return code


if __name__ == "__main__":
    status = main()
    with contextlib.suppress(Exception):
        sys.stdout.flush()
    os._exit(status)  # without waiting for an evaluation thread the hard stop left behind
