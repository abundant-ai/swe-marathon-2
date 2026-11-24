"""Run candidate commands through a physically independent docking plant."""

import argparse
import json
import os
from pathlib import Path
import pwd
import select
import shutil
import signal
import subprocess
import sys
import tempfile
from time import monotonic

from cases import CASES
from plant import Plant, Record, Violation, require, scenario_config


class Driver:
    """Stream one observation per command to an isolated submission process."""

    def __init__(self, app: Path, config: Path, state: Path) -> None:
        """Store the command paths and start the candidate."""
        self.app = app
        self.config = config
        self.state = state
        self.start()

    def start(self) -> None:
        """Launch the package as the lower-privileged account when available."""
        identity = {}
        if os.geteuid() == 0:
            try:
                account = pwd.getpwnam("candidate")
            except KeyError:
                account = pwd.getpwnam("nobody")
            identity = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        self.process = subprocess.Popen(
            [sys.executable, "-B", "-m", "dock_recovery", "--config", str(self.config),
             "--state", str(self.state)],
            cwd=self.app, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.state),
                 "LC_ALL": "C.UTF-8"},
            **identity,
        )
        self.buffer = b""

    def exchange(self, observation: Record) -> Record:
        """Read one bounded, flushed JSON reply after a submitted observation."""
        fd = self.process.stdout.fileno()
        try:
            self.process.stdin.write(json.dumps(observation).encode() + b"\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise Violation("coordinator stopped before reading observation") from None
        stop = monotonic() + 2
        while b"\n" not in self.buffer:
            readable, _, _ = select.select([fd], [], [], max(0, stop - monotonic()))
            require(bool(readable), "no flushed response within two seconds")
            block = os.read(fd, 4096)
            require(bool(block), "coordinator exited before responding")
            self.buffer += block
            require(len(self.buffer) < 65_536, "oversized response")
        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            result = json.loads(line)
        except (ValueError, UnicodeError):
            raise Violation("response is not valid JSON") from None
        require(isinstance(result, dict), "response must be a JSON object")
        return result

    def close(self) -> None:
        """Terminate the execution group, including stray children."""
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()

    def restart(self) -> None:
        """Simulate unclean loss of the controller with state preserved."""
        self.close()
        self.start()


def reached_crash(mode: str, plant: Plant, response: Record) -> bool:
    """Locate the targeted crash boundary based on observable plant events."""
    speed = response.get("v_mps", 0)
    if mode == "approach":
        return plant.first_reverse is not None and speed < 0 and plant.tick > plant.first_reverse + 3
    if mode == "retreat":
        return plant.retreat_origin is not None and speed > 0 and abs(plant.position - plant.retreat_origin) > 0.07
    return len(plant.contacts) == plant.config["recovery"]["max_attempts"] and plant.true_contact


def mission(app: Path, root: Path, case: Record) -> Record:
    """Drive a full mission, restart once when prescribed and verify the outcome."""
    root.mkdir(mode=0o755)
    state = root / "state"
    state.mkdir(mode=0o777)
    state.chmod(0o777)
    config = scenario_config(case)
    config_path = root / "config.json"
    config_path.write_text(json.dumps(config))
    plant = Plant(case, config)
    driver = Driver(app, config_path, state)
    final = None
    final_tick = None
    did_restart = False
    crash = case.get("restart_on")
    try:
        for tick in range(config["deadline_tick"] + 3):
            obs = plant.observe(tick)
            response = driver.exchange(obs)
            if final is not None:
                require(response["status"] == final and response.get("v_mps") == response.get("w_radps") == 0,
                        "terminal decision did not persist")
            plant.observe_command(response, obs)
            if crash and not did_restart and reached_crash(crash, plant, response):
                driver.restart()
                require(driver.exchange(obs) == response, "lost reply changed after process restart")
                did_restart = True
            if response["status"] != "running" and final is None:
                final = response["status"]
                final_tick = tick
            if final_tick is not None and tick >= final_tick + 2:
                break
        require(final == case.get("expected", "docked"),
                f"expected {case.get('expected', 'docked')}, observed {final}; contacts={plant.contacts}; "
                f"position={plant.position:.3f}; yaw={plant.yaw:.3f}")
        require(len(plant.contacts) == case.get("contact_count", 1), "physical attempt count was incorrect")
        if case.get("pallet_ticks"):
            require(plant.blocked_ticks >= 4, "the pallet fault was never exercised")
        if crash:
            require(did_restart, "the relevant restart boundary was never reached")
        if final == "failed" and case.get("contact_count", 1) and not case.get("failure_at_deadline"):
            require(final_tick >= plant.contacts[-1] + config["charge"]["wait_ticks"],
                    "terminal failure occurred before charge verification expired")
        return {"finish_tick": final_tick, "status": final, "first_reverse": plant.first_reverse,
                "contacts": plant.contacts, "rear_guard_ticks": plant.blocked_ticks,
                "odom_unavailable_ticks": plant.pose_pauses,
                "retreat_distances_m": plant.retreat_distances, "restarted": did_restart}
    finally:
        driver.close()


def stage_artifact(source: Path, app: Path) -> None:
    """Copy regular submission files without following links into private resources."""
    if not source.is_dir() or source.is_symlink():
        return
    package = app / "dock_recovery"
    package.mkdir()
    for source_path in source.rglob("*"):
        if source_path.is_symlink() or not source_path.is_file():
            continue
        relative = source_path.relative_to(source)
        if any(p.is_symlink() for p in source_path.parents if p != source.parent):
            continue
        destination = package / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)


def main() -> None:
    """Evaluate cumulative missions and write protected Oddish reward artifacts."""
    cli = argparse.ArgumentParser()
    cli.add_argument("--stage", required=True, type=int, choices=range(1, 8))
    cli.add_argument("--artifact", type=Path, default=Path("/app/dock_recovery"))
    cli.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.chmod(0o700)
    (args.output / "reward.json").unlink(missing_ok=True)
    cases = [case for case in CASES if case["stage"] <= args.stage]
    extra = []
    if args.stage >= 5:
        from staging_cases import cases as staging_cases
        from staging_plant import drive_case

        extra = staging_cases()
    checks, observations, compilation, native = {}, {}, {}, {}
    with tempfile.TemporaryDirectory(prefix="dock-recovery-") as temp:
        root = Path(temp)
        root.chmod(0o755)
        app = root / "app"
        app.mkdir()
        stage_artifact(args.artifact, app)
        for index, case in enumerate(cases + extra):
            name = case["name"]
            try:
                if case["stage"] == 5:
                    observations[name] = drive_case(app, root / str(index), case, Driver)
                else:
                    observations[name] = mission(app, root / str(index), case)
                checks[name] = True
            except Violation as error:
                observations[name] = str(error)
                checks[name] = False
        if args.stage >= 6:
            from compile_checks import exercise_compiler

            compilation = exercise_compiler(app, root, Driver)
        if args.stage >= 7:
            from native_cases import CASES as native_cases, pass_case, run_mission

            for index, name in enumerate(native_cases):
                os.environ["ROS_DOMAIN_ID"] = str(int(os.environ.get("DOCK_VERIFIER_DOMAIN", "194")) + index)
                destination = args.output / ("native-" + name)
                scratch = root / ("native-" + name)
                try:
                    native[name] = run_mission(scratch, app, name)
                    native[name]["passed"] = pass_case(native[name])
                except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
                    native[name] = {"passed": False, "error": str(error)}
                destination.mkdir(exist_ok=True)
                for filename in ("candidate.log", "native.log", "trace.json", "summary.json"):
                    if (scratch / filename).is_file():
                        shutil.copyfile(scratch / filename, destination / filename)
    legacy = sum(checks[case["name"]] for case in cases) / len(cases)
    positive = any(checks[case["name"]] for case in extra if case.get("expected", "docked") == "docked")
    staged = sum(checks[case["name"]] for case in extra) / len(extra) if positive else 0.0
    reward = 0.20 * legacy + 0.80 * staged if extra else legacy
    if compilation:
        earned = sum(row["passed"] for row in compilation.values()) / len(compilation)
        qualified = any(row["passed"] for key, row in compilation.items() if key.startswith("mission-"))
        reward = 0.20 * reward + (0.80 * earned if qualified else 0.0)
    if native:
        earned = sum(row["passed"] for row in native.values()) / len(native)
        docked = any(row["passed"] and row["receipt"].get("status") == "docked"
                     for row in native.values())
        reward = 0.15 * reward + (0.85 * earned if docked else 0.0)
    (args.output / "checkpoint.json").write_text(json.dumps({
        "stage": args.stage, "reward": reward, "checks": checks, "observations": observations,
        "legacy_fraction": legacy, "staging_fraction": staged if extra else None,
        "compilation": compilation, "native": native,
    }, indent=2, sort_keys=True) + "\n")
    (args.output / "reward.json").write_text(json.dumps({"reward": reward}) + "\n")


if __name__ == "__main__":
    main()
