"""Build the delivered merge driver from source and run it on the private cases.

Entry point of the separate verifier container. The delivery is /app/driver. Private inputs live in
/tests/private (root only): cases.json (inputs, path and family of each kept case), expected.json
(status and output digest of each case) and netting.json (per family, the best trivial program's
pass rate). Writes /logs/verifier/reward.txt and metrics.json. An infrastructure fault raises and
leaves no reward file.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WEIGHTS = {
    "F1": 0.08,
    "F2": 0.15,
    "F3": 0.12,
    "F4": 0.11,
    "F5": 0.06,
    "F6": 0.08,
    "F7": 0.06,
    "F8": 0.25,
    "F9": 0.04,
    "F10": 0.05,
}
PRIVATE = Path("/tests/private")
LOGS = Path("/logs/verifier")
CARGO_CONFIG = Path("/usr/local/share/offline-registry/config.toml")
WORK = Path("/work")
UID = 51000
BUILD_TIMEOUT = 1800
CASE_TIMEOUT = 10
OUTPUT_CAP = 16 * 1024 * 1024
RUN_ENV = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
    "TZ": "UTC",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


class EvaluationError(RuntimeError):
    """A fault of the verifier or its environment: no reward may be written."""


@dataclasses.dataclass(frozen=True)
class VerificationContext:
    """Where the delivery, the private inputs and the outputs are."""

    delivery: Path
    private: Path
    logs: Path
    work: Path


@dataclasses.dataclass(frozen=True)
class CheckResult:
    """One requirement's outcome with its evidence."""

    requirement: str
    status: str
    explanation: str
    measurements: dict


@dataclasses.dataclass(frozen=True)
class VerificationResult:
    """The checks, the per-family metrics and the reward."""

    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: dict


def as_user(cmd: list[str]) -> list[str]:
    """Run a command as the unprivileged verifier uid, with no new privileges."""
    return [
        "setpriv",
        f"--reuid={UID}",
        f"--regid={UID}",
        "--clear-groups",
        "--no-new-privs",
        *cmd,
    ]


def build(ctx: VerificationContext) -> tuple[Path | None, str]:
    """Copy the delivery, drop any prebuilt output, and build it offline as the verifier uid."""
    src = ctx.work / "driver"
    if src.exists():
        shutil.rmtree(src)
    if not (ctx.delivery / "Cargo.toml").is_file():
        return None, "no Cargo.toml in /app/driver"
    shutil.copytree(
        ctx.delivery, src, symlinks=True, ignore=shutil.ignore_patterns("target")
    )
    home, cargo_home = ctx.work / "home", ctx.work / "cargo-home"
    for d in (home, cargo_home):
        d.mkdir(exist_ok=True)
    shutil.copy(CARGO_CONFIG, cargo_home / "config.toml")
    for p in (src, home, cargo_home):
        subprocess.run(["chown", "-R", f"{UID}:{UID}", str(p)], check=True)
    env = dict(
        RUN_ENV,
        PATH="/usr/local/bin:/usr/bin:/bin",
        HOME=str(home),
        CARGO_HOME=str(cargo_home),
        CARGO_TARGET_DIR=str(src / "target"),
    )
    try:
        r = subprocess.run(
            as_user(["cargo", "build", "--release", "--offline"]),
            check=False,
            cwd=src,
            env=env,
            capture_output=True,
            timeout=BUILD_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None, "the build did not finish in time"
    binary = src / "target/release/weave-driver"
    if r.returncode != 0 or not binary.is_file():
        return None, "the build failed: " + r.stderr[-2000:].decode("utf-8", "replace")
    return binary, "built"


def run_case(binary: Path, case: dict, root: Path) -> tuple[object, str | None]:
    """Run one case in a fresh directory as the verifier uid; return (status, output digest)."""
    d = root / case["id"]
    for sub in ("w", "home", "tmp"):
        (d / sub).mkdir(parents=True)
    names = []
    for key in ("base", "ours", "theirs"):
        p = d / "w" / key
        p.write_bytes(case[key].encode("utf-8", "surrogateescape"))
        names.append(str(p))
    subprocess.run(["chown", "-R", f"{UID}:{UID}", str(d)], check=True)
    out = d / "w" / "out"
    env = dict(RUN_ENV, HOME=str(d / "home"), TMPDIR=str(d / "tmp"))
    cmd = as_user(
        [
            "prlimit",
            "--as=4294967296",
            str(binary),
            *names,
            "-o",
            str(out),
            "-l",
            "7",
            "-p",
            case["path"],
        ]
    )
    try:
        r = subprocess.run(
            cmd,
            check=False,
            cwd=d / "w",
            env=env,
            capture_output=True,
            timeout=CASE_TIMEOUT,
        )
        status: object = r.returncode
    except subprocess.TimeoutExpired:
        status = "timeout"
    subprocess.run(["pkill", "-KILL", "-u", str(UID)], check=False, capture_output=True)
    digest = None
    if out.is_file() and not out.is_symlink():
        data = out.read_bytes()[: OUTPUT_CAP + 1]
        digest = (
            "too-large" if len(data) > OUTPUT_CAP else hashlib.sha256(data).hexdigest()
        )
    shutil.rmtree(d, ignore_errors=True)
    return status, digest


def score(
    passed: dict[str, list[bool]], netting: dict[str, float]
) -> tuple[float, dict]:
    """Per-family pass rate, net credit and the weighted reward (fixed denominators)."""
    fams, reward = {}, 0.0
    for fam, w in WEIGHTS.items():
        outcomes = passed.get(fam, [])
        if not outcomes:
            continue
        p = sum(outcomes) / len(outcomes)
        s = netting.get(fam, 0.0)
        g = 0.0 if s >= 1 else max(0.0, (p - s) / (1 - s))
        fams[fam] = {
            "cases": len(outcomes),
            "pass": round(p, 6),
            "stub": round(s, 6),
            "net": round(g, 6),
            "weight": w,
        }
    total_w = sum(WEIGHTS[f] for f in fams)
    for fam, row in fams.items():
        reward += row["weight"] / total_w * row["net"]
    return round(reward, 6), fams


def verify(ctx: VerificationContext) -> VerificationResult:
    """Build the delivery, run every case, and score it."""
    try:
        cases = json.loads((ctx.private / "cases.json").read_text(encoding="utf-8"))
        expected = json.loads((ctx.private / "expected.json").read_text())
        netting = json.loads((ctx.private / "netting.json").read_text())
    except (OSError, ValueError) as exc:
        raise EvaluationError(f"private inputs unreadable: {exc}") from exc
    ctx.work.mkdir(parents=True, exist_ok=True)
    binary, note = build(ctx)
    checks = [CheckResult("build", "passed" if binary else "failed", note, {})]
    passed: dict[str, list[bool]] = {}
    if binary is not None:
        os.chmod(ctx.work, 0o755)
        root = ctx.work / "cases"
        root.mkdir(exist_ok=True)
        for case in cases:
            status, digest = run_case(binary, case, root)
            want = expected[case["id"]]
            ok = status == want["status"] and digest == want["sha256"]
            passed.setdefault(case["family"], []).append(ok)
    else:
        for case in cases:
            passed.setdefault(case["family"], []).append(False)
    reward, fams = score(passed, netting)
    for fam, row in fams.items():
        checks.append(
            CheckResult(
                fam,
                "passed" if row["pass"] == 1 else "failed",
                f"{row['pass']:.4f} of {row['cases']} cases",
                row,
            )
        )
    metrics = {
        "reward": reward,
        "families": fams,
        "cases": len(cases),
        "build": note[:2000],
    }
    return VerificationResult(
        passed=reward == 1.0, checks=tuple(checks), metrics=metrics
    )


def main() -> int:
    """Run the verification and write the reward last."""
    ctx = VerificationContext(Path("/app/driver"), PRIVATE, LOGS, WORK)
    ctx.logs.mkdir(parents=True, exist_ok=True)
    for stale in ("reward.txt", "metrics.json"):
        (ctx.logs / stale).unlink(missing_ok=True)
    try:
        result = verify(ctx)
    except EvaluationError as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2
    (ctx.logs / "metrics.json").write_text(
        json.dumps(
            {
                **result.metrics,
                "checks": [dataclasses.asdict(c) for c in result.checks],
            },
            indent=1,
        )
    )
    (ctx.logs / "reward.txt").write_text(f"{result.metrics['reward']}\n")
    print(f"reward {result.metrics['reward']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
