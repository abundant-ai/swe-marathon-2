"""Grade one submitted game: self-test, gates, instances, reward. Always writes a reward
once the self-test has passed.

Order:
1. Remove any stale reward and report files.
2. The self-test on our own tiny project (selftest.py). Failure raises EvaluationError:
   no reward is written, the run is an evaluation error. This is the only path that
   leaves no reward.
3. G_static on the submission as collected, G_import (preparation of a copy), G_boot.
4. Every instance of the release manifest, one fresh game process per run, in manifest
   order, within the grader's own deadline. An instance that cannot start before the
   deadline (or is cut by it) counts 0 within its family's fixed N_f. Game processes get
   the shipped plans (--plan-dir), except those of an instance whose manifest entry names
   its own plan folder (load_manifest), which get a fresh copy of that folder (GDD WD-8).
5. Physics-sensitive instances scoring below 1 rerun once (at most 15% of instances).
6. reward.txt (six decimals) and report.json, each written to a temporary name and
   renamed into place.

A watchdog thread kills every game process at the deadline, and an alarm 60 s later
writes the reward from whatever has been graded and exits, so a reward is written
whatever the game does.
"""

from __future__ import annotations

import dataclasses
import json
import os
import random
import shutil
import signal
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path

from qakit import expect
from qakit.play import Play, PlayError, limits_of, load_play, run_play
from qakit.prepare import prepare, verify_telemetry
from qakit.procs import Limits, kill_all_live
from qakit.session import SessionOptions

from . import gates, scoring
from .hostenv import describe, memory_gate
from .sandbox import CgroupLimits, Sandbox
from .selftest import run_selftest

REWARD = "reward.txt"
REPORT = "report.json"


class EvaluationError(Exception):
    """Grading could not be carried out through no fault of the submission; no reward."""


@dataclass
class GradeConfig:
    """Everything one grading run needs.

    Attributes:
        project: The submitted project folder (read only; a copy is graded).
        out: Folder for reward.txt and report.json.
        work: Scratch folder (copies, runs, logs); created.
        godot: Godot binary.
        library: The telemetry library built for this platform.
        instances: Release manifest (qa-instances/1).
        selftest_dir: tests/selftest.
        denylist: Originality denylist file, or None.
        deadline_s: The grader's own deadline from its start (80 minutes in the release).
        import_cap_s: G_import time cap (PF-3: 600).
        cache_cap_mb: G_import cache cap (PF-3: 1024).
        boot_s: G_boot budget (PF-4: 60).
        server_boot: Also boot the server role in G_boot.
        skip_selftest: Development only: assume the self-test passed.
        seed_names: Random source for the telemetry names (None: fresh each run).
        memory_mb: Development only: a lower memory cap for every game process.
        step_s: Development only: a shorter stall allowance per lockstep step.
        margin_s: Seconds kept back from the deadline when sizing an instance's time.
        plans: The shipped plan folder; every game process gets --plan-dir=<plans> unless
            its instance names another (None: no plan folder is passed).
    """

    project: Path
    out: Path
    work: Path
    godot: str
    library: Path
    instances: Path
    selftest_dir: Path
    denylist: Path | None = None
    deadline_s: float = 4800.0
    import_cap_s: float = 600.0
    cache_cap_mb: float = 1024.0
    boot_s: float = 60.0
    server_boot: bool = True
    skip_selftest: bool = False
    seed_names: int | None = None
    memory_mb: float | None = None
    step_s: float | None = None
    margin_s: float = 60.0
    plans: Path | None = None


@dataclass
class Grading:
    """Mutable state of one grading run (shared with the deadline alarm)."""

    cfg: GradeConfig
    t0: float
    families: dict = field(default_factory=dict)
    manifest_instances: list = field(default_factory=list)
    gates: dict = field(default_factory=dict)
    results: list = field(default_factory=list)
    selftest: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    expired: bool = False
    finished: bool = False


def remove_stale(out: Path) -> None:
    """Delete reward and report files left by an earlier run."""
    out.mkdir(parents=True, exist_ok=True)
    for name in (REWARD, REPORT, REWARD + ".tmp", REPORT + ".tmp"):
        (out / name).unlink(missing_ok=True)


def write_atomic(path: Path, text: str) -> None:
    """Write text to path through a temporary file and a rename."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def make_options(
    sandbox: Sandbox, gate, memory_mb: float | None = None, step_s: float | None = None
):
    """The SessionOptions factory used for every game process of a grading run.

    Args:
        sandbox: Linux isolation (inactive on macOS).
        gate: Memory gate hook (development Mac) or None.
        memory_mb: Override of every process's memory cap (development), or None.
        step_s: Override of the per-step stall allowance (development), or None.

    Returns:
        options(folder, play_or_None) -> SessionOptions.
    """

    def options(folder: Path, play: Play | None) -> SessionOptions:
        lim = (
            limits_of(play)
            if play is not None
            else Limits(cpu_s=300, memory_mb=1536, disk_mb=1024)
        )
        boot_s = float(play.limits.get("boot_s", 60)) if play is not None else 60.0
        step_s_play = float(play.limits.get("step_s", 30)) if play is not None else 30.0
        if memory_mb is not None:
            lim = Limits(**{**lim.__dict__, "memory_mb": memory_mb})
        step_s_now = step_s if step_s is not None else step_s_play
        cgroup = sandbox.new_cgroup(CgroupLimits()) if sandbox.available else None
        return SessionOptions(
            home=folder / "home",
            log_path=folder / "game.log",
            limits=lim,
            boot_s=boot_s,
            step_s=step_s_now,
            cgroup=cgroup,
            user=sandbox.ids,
            before_start=gate,
        )

    return options


def load_manifest(path: Path) -> tuple[dict, list[dict]]:
    """Read a release manifest (format "qa-instances/1").

    The manifest is {"format", "release", "families", "instances"}: "families" maps each
    family letter to {"w": weight, "n": fixed instance count}, and "instances" lists the
    instances in the order they run, each {"file": play file, "family": letter} with an
    optional "plans": a plan folder (the same file names as the shipped plans). Paths are
    relative to the manifest's folder. An instance with "plans" runs its game processes
    with --plan-dir=<a fresh copy of that folder> (instance_plans); the others get the
    shipped plans.

    Returns:
        ({family: {"w", "n"}}, [{"file", "family", "plans"?}]).
    """
    m = json.loads(path.read_text())
    if m.get("format") != "qa-instances/1":
        raise EvaluationError(f"{path} is not a qa-instances/1 manifest")
    return m["families"], m["instances"]


def instance_plans(cfg: GradeConfig, entry: dict, work: Path) -> Path | None:
    """The plan folder one instance's game processes get as --plan-dir.

    An entry that names "plans" (a folder relative to the manifest) runs on a fresh copy
    of that folder, made in the instance's work folder and readable by every user: the
    game runs as a user that cannot read the grader's private inputs (sandbox.py), and no
    earlier game process can have changed the copy. Every other entry runs on the shipped
    plans (cfg.plans).

    Args:
        cfg: The grading run's configuration.
        entry: The instance's manifest entry.
        work: The instance's work folder (created when needed).

    Returns:
        The folder to pass, or None when there is none.

    Raises:
        EvaluationError: The entry names something that is not a folder.
    """
    rel = entry.get("plans")
    if rel is None:
        return cfg.plans
    src = cfg.instances.parent / str(rel)
    if not isinstance(rel, str) or not rel or not src.is_dir():
        raise EvaluationError(
            f"instance {entry.get('file')}: plans {rel!r} is not a folder next to the manifest"
        )
    dst = work / "plans"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=shutil.copyfile)
    for path in [dst, *dst.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    return dst


def grade_instance(
    g: Grading, entry: dict, game_dir: Path, options, tel, work: Path
) -> scoring.InstanceResult:
    """Run and score one instance (with its retry when allowed by the caller)."""
    cfg = g.cfg
    t0 = time.monotonic()
    path = cfg.instances.parent / entry["file"]
    try:
        play = load_play(path)
    except (PlayError, OSError) as exc:
        raise EvaluationError(
            f"instance {entry['file']} cannot be read: {exc}"
        ) from exc
    tampered = verify_telemetry(game_dir, tel)
    if tampered:
        return scoring.InstanceResult(
            play.name,
            entry["family"],
            0.0,
            "telemetry_files",
            detail={"problems": tampered},
        )
    left = cfg.deadline_s - (time.monotonic() - g.t0) - cfg.margin_s
    budget = min(float(play.limits.get("wall_s", 600)), left)
    if budget < 10:
        return scoring.InstanceResult(
            play.name, entry["family"], 0.0, "not_run:deadline"
        )
    play_limited = Play(**{**play.__dict__, "limits": dict(play.limits, wall_s=budget)})
    rec = run_play(
        play_limited,
        game_dir,
        cfg.godot,
        work,
        lambda _k, _n, folder: options(folder, play_limited),
        plans=instance_plans(cfg, entry, work),
    )
    outcomes = expect.check_play(rec) + expect.standing(rec)
    checks = [scoring.Check(o.id, o.kind, o.w, o.ok) for o in outcomes]
    score, failure = scoring.instance_score(checks)
    if g.expired:
        score, failure = 0.0, "not_run:deadline"
    detail = {
        "errors": [r.error for r in rec.runs if r.error],
        "exits": [r.exits for r in rec.runs],
        "replay": [r.chain.replay_hash if r.chain else None for r in rec.runs],
    }
    if "plans" in entry:
        detail["plans"] = entry["plans"]
    return scoring.InstanceResult(
        play.name,
        entry["family"],
        round(score, 6),
        failure,
        [asdict(o) for o in outcomes],
        1,
        round(time.monotonic() - t0, 2),
        detail,
    )


def run_instances(g: Grading, game_dir: Path, options, tel) -> None:
    """Grade every manifest instance in order, honouring the deadline and retry budget."""
    budget = scoring.retry_budget(len(g.manifest_instances))
    for i, entry in enumerate(g.manifest_instances):
        work = g.cfg.work / "instances" / f"{i:03d}"
        if g.expired:
            g.results.append(
                scoring.InstanceResult(
                    entry["file"], entry["family"], 0.0, "not_run:deadline"
                )
            )
            continue
        try:
            res = grade_instance(g, entry, game_dir, options, tel, work)
        except EvaluationError:
            raise
        except Exception as exc:  # noqa: BLE001 - recorded; the instance counts 0 and grading goes on
            res = scoring.InstanceResult(
                entry["file"],
                entry["family"],
                0.0,
                "kit_exception",
                detail={"traceback": traceback.format_exc(), "error": repr(exc)},
            )
        play_tags = []
        try:
            play_tags = list(load_play(g.cfg.instances.parent / entry["file"]).tags)
        except (PlayError, OSError):
            pass
        if (
            res.score < 1.0
            and "physics-sensitive" in play_tags
            and budget > 0
            and not g.expired
        ):
            budget -= 1
            again = grade_instance(
                g, entry, game_dir, options, tel, work.with_name(work.name + "-retry")
            )
            again.attempts = 2
            res = again if again.score > res.score else res
            res.attempts = 2
        g.results.append(res)


def finalize(g: Grading, status: str = "graded") -> float:
    """Compute and write the reward and the report; returns the reward."""
    if g.finished:
        return float((g.cfg.out / REWARD).read_text())
    g.finished = True
    results = list(
        g.results
    )  # instances never graded count 0 within their family's N_f
    scores = scoring.family_scores(results, g.families) if g.families else {}
    gate_pass = {k: v.passed for k, v in g.gates.items()}
    reward = scoring.total_reward(gate_pass, g.families, scores) if gate_pass else 0.0
    report = {
        "status": status,
        "reward": reward,
        "gates": {k: asdict(v) for k, v in g.gates.items()},
        "families": scores,
        "integration_gap": scoring.integration_gap(scores),
        "instances": [asdict(r) for r in results],
        "selftest": g.selftest,
        "notes": g.notes,
        "elapsed_s": round(time.monotonic() - g.t0, 1),
        "host": describe(),
    }
    write_atomic(g.cfg.out / REWARD, f"{reward:.6f}\n")
    write_atomic(g.cfg.out / REPORT, json.dumps(report, indent=1, default=str))
    return reward


def start_deadline(g: Grading) -> threading.Timer:
    """At the deadline: stop grading new instances and kill every game process.

    Also arms SIGALRM 60 s later (main thread only): the handler writes the reward from
    what has been graded and exits, in case grading is stuck somewhere unexpected.
    """

    def expire() -> None:
        g.expired = True
        g.notes.append("the grader's deadline was reached")
        kill_all_live()

    timer = threading.Timer(max(1.0, g.cfg.deadline_s), expire)
    timer.daemon = True
    timer.start()
    if threading.current_thread() is threading.main_thread() and hasattr(
        signal, "SIGALRM"
    ):

        def on_alarm(_signum, _frame) -> None:
            kill_all_live()
            if g.selftest.get("ok"):
                finalize(g, "deadline")
            os._exit(0 if g.selftest.get("ok") else 1)

        signal.signal(signal.SIGALRM, on_alarm)
        signal.alarm(int(g.cfg.deadline_s + 60))
    return timer


def grade(cfg: GradeConfig) -> float:
    """Grade the submission; returns the reward written.

    Raises:
        EvaluationError: The self-test failed or the grader's own inputs are broken;
            no reward has been written.
    """
    remove_stale(cfg.out)
    cfg.work.mkdir(parents=True, exist_ok=True)
    g = Grading(cfg, time.monotonic())
    g.families, g.manifest_instances = load_manifest(cfg.instances)
    sandbox = Sandbox()
    sandbox.prepare_base()
    gate_hook = memory_gate()
    options = make_options(sandbox, gate_hook, cfg.memory_mb, cfg.step_s)
    timer = start_deadline(g)
    try:
        if cfg.skip_selftest:
            g.selftest = {"ok": True, "skipped": True}
        else:
            st = run_selftest(
                cfg.selftest_dir,
                cfg.godot,
                cfg.library,
                cfg.work / "selftest",
                options,
                gate_hook,
            )
            g.selftest = {
                "ok": st.ok,
                "problems": st.problems,
                "wall_s": st.wall_s,
                "measured": st.measured,
            }
            if not st.ok:
                write_atomic(
                    cfg.out / REPORT,
                    json.dumps(
                        {"status": "evaluation_error", "selftest": g.selftest},
                        indent=1,
                        default=str,
                    ),
                )
                raise EvaluationError("self-test failed: " + "; ".join(st.problems[:5]))
        denylist = (
            cfg.denylist.read_text().splitlines()
            if cfg.denylist and cfg.denylist.is_file()
            else []
        )
        g.gates["static"] = gates.static_gate(cfg.project, denylist)
        rng = random.Random(cfg.seed_names)
        prep = prepare(
            cfg.project,
            cfg.work / "game",
            cfg.godot,
            cfg.library,
            rng,
            cfg.work / "prep",
            Limits(wall_s=cfg.import_cap_s, memory_mb=4096),
            gate_hook,
        )
        g.gates["import"] = gates.import_gate(prep, cfg.cache_cap_mb, cfg.import_cap_s)
        if g.gates["static"].passed and g.gates["import"].passed:
            g.gates["boot"] = gates.boot_gate(
                prep,
                cfg.godot,
                cfg.work / "boot",
                lambda _role, folder: dataclasses.replace(
                    options(folder, None), boot_s=cfg.boot_s
                ),
                cfg.boot_s,
                cfg.server_boot,
                cfg.plans,
            )
        else:
            g.gates["boot"] = gates.GateResult(
                "boot", False, ["not run: an earlier gate failed"]
            )
        if all(x.passed for x in g.gates.values()):
            run_instances(g, prep.game_dir, options, prep.telemetry)
        else:
            g.notes.append("instances not run: a gate failed")
        return finalize(g, "deadline" if g.expired else "graded")
    finally:
        timer.cancel()
        if (
            hasattr(signal, "SIGALRM")
            and threading.current_thread() is threading.main_thread()
        ):
            signal.alarm(0)
        kill_all_live()
