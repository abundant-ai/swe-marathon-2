"""Build the delivered merge driver from source and run it on the private cases.

Entry point of the separate verifier container. The delivery is /app/driver. Private inputs live in
/tests/private (root only): cases.json (inputs, path and family of each kept case), expected.json
(status and output digest of each case) and netting.json (per family, the best trivial program's
pass rate). Writes /logs/verifier/reward.txt and metrics.json. An infrastructure fault raises and
leaves no reward file.

Everything the delivery runs (build scripts, the compiler it drives, the driver itself) runs as an
unprivileged uid with no new privileges and bounded resources. Root reads only from directories
the uid cannot rename, opens nothing the uid can write without O_NOFOLLOW, kills every process of
the uid before reading results, and writes the reward files last with O_EXCL after removing
whatever already stood under those names.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import delivery_manifest

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
REWARD_NAMES = ("reward.json", "reward.txt", "metrics.json")
MAX_DEPTH = 64
DIGESTS = Path("/tests/upstream-digests.txt")
BUILD_LIMITS = ["--nproc=1024", "--fsize=2147483648"]
CASE_LIMITS = ["--as=4294967296", "--nproc=256", f"--fsize={2 * OUTPUT_CAP}"]
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


def as_user(cmd: list[str], limits: list[str]) -> list[str]:
    """Run a command as the unprivileged verifier uid, bounded, with no new privileges."""
    return [
        "setpriv",
        f"--reuid={UID}",
        f"--regid={UID}",
        "--clear-groups",
        "--no-new-privs",
        "prlimit",
        *limits,
        *cmd,
    ]


def user_pids() -> tuple[list[int], list[int]]:
    """(every pid of the verifier uid, those with a task still running).

    /proc is read as bytes, so no process name can break the parse. A process counts as running
    while any of its tasks is: a thread group whose leader has exited reads as a zombie in its own
    status, but its other threads still run.
    """
    every, running = [], []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            status = (d / "status").read_bytes()
        except OSError:
            continue
        uid = next(
            (ln.split()[1:2] for ln in status.splitlines() if ln.startswith(b"Uid:")),
            [],
        )
        if not uid or int(uid[0]) != UID:
            continue
        every.append(int(d.name))
        try:
            tasks = list((d / "task").iterdir())
        except OSError:
            tasks = []
        for task in tasks:
            try:
                tstatus = (task / "status").read_bytes()
            except OSError:
                continue
            state = next(
                (
                    ln.split()[1:2]
                    for ln in tstatus.splitlines()
                    if ln.startswith(b"State:")
                ),
                [],
            )
            if state and state[0] not in (b"Z", b"X"):
                running.append(int(d.name))
                break
    return every, running


def reap() -> None:
    """Collect exited children (orphans reparent to this process when it is the container's init)."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def kill_user() -> None:
    """Kill every process of the verifier uid, until none is left running."""
    for _ in range(200):
        subprocess.run(
            ["pkill", "-KILL", "-u", str(UID)], check=False, capture_output=True
        )
        every, running = user_pids()
        for pid in every:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
        reap()
        if not running and not user_pids()[1]:
            return
        time.sleep(0.05)
    raise EvaluationError("processes of the verifier uid survived repeated kills")


def run_bounded(
    cmd: list[str], cwd: Path, env: dict, timeout: float, keep: int = 4096
) -> tuple[int | None, bytes]:
    """Run a command with its output drained and only the last `keep` bytes kept.

    Returns (exit status, or None on timeout; output tail). Memory stays bounded whatever the
    command prints.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    tail = bytearray()

    def drain() -> None:
        assert proc.stdout is not None
        while chunk := proc.stdout.read(65536):
            tail.extend(chunk)
            del tail[:-keep]

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        status: int | None = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        status = None
    kill_user()
    proc.kill()
    proc.wait()
    reader.join(timeout=10)
    return status, bytes(tail)


def read_output(path: Path) -> str | None:
    """Digest of a regular file the uid wrote, opened without following links; None if absent."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = bytearray()
        while len(data) <= OUTPUT_CAP and (chunk := os.read(fd, 1 << 20)):
            data.extend(chunk)
    finally:
        os.close(fd)
    if len(data) > OUTPUT_CAP:
        return "too-large"
    return hashlib.sha256(bytes(data)).hexdigest()


def remove_tree(root: Path) -> None:
    """Remove a directory tree iteratively, never following a link (no recursion limit)."""
    if root.is_symlink() or not root.is_dir():
        with contextlib.suppress(FileNotFoundError):
            root.unlink()
        return
    for top, dirs, files in os.walk(root, topdown=False, followlinks=False):
        for name in files:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(os.path.join(top, name))
        for name in dirs:
            path = os.path.join(top, name)
            with contextlib.suppress(FileNotFoundError):
                if os.path.islink(path):
                    os.unlink(path)
                else:
                    os.rmdir(path)
    os.rmdir(root)


def copy_delivery(
    src: Path, dst: Path, digests: set[str]
) -> tuple[list[str], list[str]]:
    """Copy the delivery iteratively: directories, regular files and links as links.

    Leaves out target/ and .delivery/ at the top, special files, and anything deeper than
    MAX_DEPTH levels. Returns (notes on what was left out, delivered files whose digest is one
    of the original's own published files).
    """
    notes, matches = [], []
    dst.mkdir()
    for top, dirs, files in os.walk(src, followlinks=False):
        rel = Path(top).relative_to(src)
        depth = len(rel.parts)
        if depth == 0:
            dirs[:] = [d for d in dirs if d not in ("target", ".delivery")]
        if depth >= MAX_DEPTH and dirs:
            notes.append(f"left out below {rel}: deeper than {MAX_DEPTH} levels")
            dirs[:] = []
        for name in sorted(dirs):
            s, d = Path(top) / name, dst / rel / name
            if s.is_symlink():
                os.symlink(os.readlink(s), d)
                dirs.remove(name)
            else:
                d.mkdir()
        for name in files:
            s, d = Path(top) / name, dst / rel / name
            st = os.lstat(s)
            if stat.S_ISLNK(st.st_mode):
                os.symlink(os.readlink(s), d)
            elif stat.S_ISREG(st.st_mode):
                shutil.copyfile(s, d, follow_symlinks=False)
                os.chmod(d, st.st_mode & 0o755)
                if st.st_size >= 1024 and digest(s) in digests:
                    matches.append(str(rel / name))
            else:
                notes.append(
                    f"left out {rel / name}: not a regular file, directory or link"
                )
    return notes, matches


def digest(path: Path) -> str:
    """sha256 of a file, read in chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def check_path_dirs() -> None:
    """No directory on PATH, and no file in one, may be writable by anyone but root."""
    for entry in os.environ.get("PATH", "").split(":"):
        d = Path(entry)
        if not entry or not d.is_dir():
            continue
        items = [d, *(x for x in d.iterdir() if not x.is_symlink())]
        for x in items:
            st = os.stat(x)
            if st.st_uid != 0 or st.st_mode & 0o022:
                raise EvaluationError(
                    f"{x} on PATH is writable by a user other than root"
                )


def load_digests() -> set[str]:
    """The digests of the original's published files (the tripwire list)."""
    try:
        text = DIGESTS.read_text()
    except OSError as exc:
        raise EvaluationError(f"tripwire list unreadable: {exc}") from exc
    return {
        ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")
    }


def build(ctx: VerificationContext) -> tuple[Path | None, str]:
    """Copy the delivery, drop any prebuilt output, and build it offline as the verifier uid."""
    src = ctx.work / "driver"
    if src.exists() or src.is_symlink():
        remove_tree(src)
    if not (ctx.delivery / "Cargo.toml").is_file():
        return None, "no Cargo.toml in /app/driver"
    notes, matches = copy_delivery(ctx.delivery, src, load_digests())
    if matches:
        return None, (
            "the delivery holds files of the original's own published source or builds: "
            + ", ".join(matches[:20])
        )
    home, cargo_home = ctx.work / "home", ctx.work / "cargo-home"
    for d in (home, cargo_home):
        d.mkdir(exist_ok=True)
    shutil.copy(CARGO_CONFIG, cargo_home / "config.toml")
    for p in (src, home, cargo_home):
        subprocess.run(["chown", "-R", "-h", f"{UID}:{UID}", str(p)], check=True)
    env = dict(
        RUN_ENV,
        PATH="/usr/local/bin:/usr/bin:/bin",
        HOME=str(home),
        CARGO_HOME=str(cargo_home),
        CARGO_TARGET_DIR=str(src / "target"),
    )
    status, tail = run_bounded(
        as_user(["cargo", "build", "--release", "--offline"], BUILD_LIMITS),
        src,
        env,
        BUILD_TIMEOUT,
    )
    if status is None:
        return None, "the build did not finish in time"
    binary = src / "target/release/weave-driver"
    if status != 0 or not binary.is_file():
        return None, "the build failed: " + tail[-2000:].decode("utf-8", "replace")
    return binary, "built" + "".join(f"; {n}" for n in notes[:20])


def run_case(binary: Path, case: dict, root: Path) -> tuple[object, str | None]:
    """Run one case in a fresh directory as the verifier uid; return (status, output digest).

    The case directory stays root's, so the uid cannot rename its subdirectories; only `w`,
    `home` and `tmp` inside it are the uid's.
    """
    d = root / case["id"]
    d.mkdir(mode=0o755)
    names = []
    for sub in ("w", "home", "tmp"):
        (d / sub).mkdir()
    for key in ("base", "ours", "theirs"):
        p = d / "w" / key
        p.write_bytes(case[key].encode("utf-8", "surrogateescape"))
        names.append(str(p))
    for sub in ("w", "home", "tmp"):
        subprocess.run(["chown", "-R", "-h", f"{UID}:{UID}", str(d / sub)], check=True)
    out = d / "w" / "out"
    env = dict(RUN_ENV, HOME=str(d / "home"), TMPDIR=str(d / "tmp"))
    cmd = as_user(
        [str(binary), *names, "-o", str(out), "-l", "7", "-p", case["path"]],
        CASE_LIMITS,
    )
    try:
        r = subprocess.run(
            cmd,
            check=False,
            cwd=d / "w",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CASE_TIMEOUT,
        )
        status: object = r.returncode
    except subprocess.TimeoutExpired:
        status = "timeout"
    kill_user()
    out_digest = read_output(out)
    remove_tree(d)
    return status, out_digest


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
    ctx.work.mkdir(mode=0o755, parents=True, exist_ok=True)
    manifest = delivery_manifest.check(ctx.delivery)
    if manifest["present"] and (manifest["missing"] or manifest["changed"]):
        raise EvaluationError(
            f"the delivery arrived incomplete: {len(manifest['missing'])} files missing, "
            f"{len(manifest['changed'])} changed since the collect step"
        )
    if manifest["late"]:
        binary, note = (
            None,
            (
                "files changed after the end of the work: "
                + ", ".join(map(str, manifest["late"][:20]))
            ),
        )
    else:
        binary, note = build(ctx)
    checks = [CheckResult("build", "passed" if binary else "failed", note, {})]
    passed: dict[str, list[bool]] = {}
    if binary is not None:
        root = ctx.work / "cases"
        root.mkdir(mode=0o755, exist_ok=True)
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
        "delivery": {
            "manifest": manifest["present"],
            "late": len(manifest["late"]),
            "notes": [str(n)[:300] for n in manifest["notes"][:10]],
        },
    }
    return VerificationResult(
        passed=reward == 1.0, checks=tuple(checks), metrics=metrics
    )


def clear_reward_names(logs: Path) -> None:
    """Remove whatever stands under the reward names, files, links or directories alike."""
    for name in REWARD_NAMES:
        p = logs / name
        if p.is_dir() and not p.is_symlink():
            remove_tree(p)
        elif os.path.lexists(p):
            p.unlink()


def abandon(logs: Path) -> None:
    """An evaluation error: stop the uid's processes and leave no reward file of anyone's."""
    try:
        for _ in range(5):
            subprocess.run(
                ["pkill", "-KILL", "-u", str(UID)], check=False, capture_output=True
            )
            reap()
    finally:
        clear_reward_names(logs)


def write_new(path: Path, text: str) -> None:
    """Create a file that must not exist yet, without following links."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def main() -> int:
    """Run the verification and write the reward last."""
    ctx = VerificationContext(Path("/app/driver"), PRIVATE, LOGS, WORK)
    ctx.logs.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chown(ctx.logs, 0, 0)
        os.chmod(ctx.logs, 0o755)
    clear_reward_names(ctx.logs)
    try:
        check_path_dirs()
        result = verify(ctx)
        kill_user()
    except EvaluationError as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        abandon(ctx.logs)
        return 2
    except BaseException:
        abandon(ctx.logs)
        raise
    clear_reward_names(ctx.logs)
    write_new(
        ctx.logs / "metrics.json",
        json.dumps(
            {
                **result.metrics,
                "checks": [dataclasses.asdict(c) for c in result.checks],
            },
            indent=1,
        ),
    )
    write_new(ctx.logs / "reward.txt", f"{result.metrics['reward']}\n")
    print(f"reward {result.metrics['reward']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
