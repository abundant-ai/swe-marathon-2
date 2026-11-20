#!/usr/bin/env bash
set -euo pipefail

exec python3 -I - <<'PY'
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
from tempfile import TemporaryDirectory


LOGS = Path("/logs/verifier")
SUBMISSION = Path(os.environ.get("BATTLE_ROYALE_SUBMISSION", "/app/submission"))
PROJECT = SUBMISSION / "BattleRoyale.uproject"
ENGINE = Path("/opt/unreal")
RUNNER = Path("/tests/build_smoke.py")
ENGINE_PREP = Path("/tests/prepare_engine.sh")
COMMAND_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/root"}
LOG_LIMIT = 16 * 1024 * 1024
REPORT_LIMIT = 16 * 1024


def submission_error() -> str | None:
    if SUBMISSION.is_symlink() or SUBMISSION.parent.is_symlink() or not SUBMISSION.is_dir():
        return f"Expected a regular project directory at {SUBMISSION}."
    for path in (PROJECT, SUBMISSION / "README.md"):
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            return f"Expected a nonempty regular file at {path}."
    for path in SUBMISSION.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            return "The project must contain only regular files and directories."
    return None


def read_evidence(directory: int, name: str, limit: int) -> bytes | None:
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        file_stat = os.fstat(stream.fileno())
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError(f"Expected regular smoke evidence in {name}.")
        if file_stat.st_size > limit and name.endswith(".log"):
            stream.seek(-limit, os.SEEK_END)
            return b"[Log truncated to its last 16 MiB.]\n" + stream.read(limit)
        if file_stat.st_size > limit:
            raise ValueError(f"Smoke evidence exceeds the permitted size in {name}.")
        return stream.read(limit)


def collect_evidence(scratch: Path) -> dict:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    run = os.open(scratch / "run", flags)
    try:
        smoke = os.open("smoke", flags, dir_fd=run)
        try:
            for log in ("build.log", "launch.log"):
                contents = read_evidence(smoke, log, LOG_LIMIT)
                if contents is not None:
                    (LOGS / log).write_bytes(contents)
            contents = read_evidence(smoke, "smoke.json", REPORT_LIMIT)
            report = json.loads(contents) if contents is not None else None
            if not isinstance(report, dict):
                raise ValueError("The build runner did not produce a JSON object.")
            return report
        finally:
            os.close(smoke)
    finally:
        os.close(run)


def evaluate(checks: dict[str, str]) -> tuple[dict, int | None]:
    if ENGINE_PREP.is_file():
        try:
            with (LOGS / "engine.log").open("wb") as output:
                subprocess.run(
                    ["/bin/bash", str(ENGINE_PREP)], env=COMMAND_ENV, stdout=output,
                    stderr=subprocess.STDOUT, check=True, timeout=300,
                )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"status": "infra_error", "stage": "engine", "error": str(exc)}, None

    error = submission_error()
    if error:
        checks["delivery"] = "failed"
        return {"status": "failed", "stage": "submission", "error": error}, 0
    checks["delivery"] = "passed"

    try:
        user = pwd.getpwnam("ue")
        with TemporaryDirectory(prefix="battle-royale-verifier-", dir="/var/tmp") as tmp:
            scratch = Path(tmp)
            scratch.chmod(0o711)
            run = scratch / "run"
            run.mkdir(mode=0o700)
            os.chown(run, user.pw_uid, user.pw_gid)
            result = subprocess.run(
                [
                    "/usr/sbin/runuser", "-u", "ue", "--", "python3", "-I", str(RUNNER),
                    "--project", str(PROJECT), "--engine-root", str(ENGINE),
                    "--output-dir", str(run / "smoke"), "--build-timeout", "2400",
                ],
                cwd=scratch,
                env=COMMAND_ENV,
                stdout=subprocess.DEVNULL,
                check=False,
            )
            report = collect_evidence(scratch)
    except (KeyError, OSError, ValueError) as exc:
        return {"status": "infra_error", "stage": "verifier", "error": str(exc)}, None

    if result.returncode == 0 and report.get("status") == "passed":
        checks.update(build="passed", launch="passed")
        return report, 1
    if (
        result.returncode == 1
        and report.get("status") == "failed"
        and report.get("stage") in ("build", "archive", "launch")
        and not str(report.get("error", "")).startswith("[Errno ")
    ):
        if report["stage"] == "launch":
            checks.update(build="passed", launch="failed")
        else:
            checks["build"] = "failed"
        return report, 0
    return report, None


if os.geteuid() != 0:
    raise SystemExit("Run the verifier entry point as root. The game builds and launches as ue.")
if LOGS.is_symlink() or not SUBMISSION.is_absolute():
    raise SystemExit("Expected a regular verifier log directory and an absolute project path.")
LOGS.mkdir(parents=True, exist_ok=True)
os.chown(LOGS, 0, 0)
LOGS.chmod(0o755)
if any(os.path.lexists(LOGS / name) for name in ("engine.log", "build.log", "launch.log", "smoke.json", "reward.txt")):
    raise SystemExit("The build smoke requires a fresh verifier log directory.")

checks = dict.fromkeys(("delivery", "build", "launch"), "skipped")
report, reward = evaluate(checks)
if reward is None:
    report["status"] = "infra_error"
report["checks"] = checks
(LOGS / "smoke.json").write_text(json.dumps(report, indent=2) + "\n")
if reward is None:
    raise SystemExit("Build smoke could not complete. See smoke.json and any saved logs.")
(LOGS / "reward.txt").write_text(f"{reward}\n")
PY
