"""Build the delivered `dogwood` project, run every private case, write the reward and metrics.

Candidate failures (no project, a failed build, wrong output, a hang) are results, and so is a
delivery that holds Dogwood's own source files or its 1.2.0 build, which scores 0. A failure of
the evaluation itself (a delivery that did not arrive as the working machine's hand-off listed
it, a process of the submission that cannot be ended) exits non-zero and leaves no reward file.

The output folder may be writable by every user, the build's and the runs' included, and a
reward file there is read as the result. So, before anything of the submission runs, the grader
opens the folder once without following links, makes it root's and closes it to everyone else
for good, and closes every other place the submission's users could leave something that root
later runs or reads: the directories on root's PATH, the delivered tree and the hand-off record.
Before it writes, it ends every process of both users (a process whose first thread has exited
included), checks that none is left, removes whatever stands under its output names, and creates
each output fresh, writing the reward last.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import handoff, integrity, listing, procs
from verifier.build import BUILDER, build
from verifier.contracts import (
    Case,
    EvaluationError,
    VerificationContext,
    VerificationResult,
)
from verifier.runner import RUNNER, run_all
from verifier.scoring import WEIGHTS, family_pass_rates, reward

REWARD_FILES = ("reward.txt", "reward.json")
OUTPUTS = (*REWARD_FILES, "metrics.json", "evaluation-error.txt")
LOGS = Path("/logs/verifier")
SUBMISSION = Path("/app/dogwood-rebuild")
PRIVATE = Path("/tests/private")
ROOT_PATH = (
    "/usr/local/cargo/bin",
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
)


class Outputs:
    """The output folder, opened once without following a link and kept root's alone; every name
    is handled relative to that descriptor, so a link planted under an output name redirects
    nothing."""

    def __init__(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchown(self.fd, 0, 0)
            os.fchmod(self.fd, 0o755)
            self.closed = True
        except OSError:
            self.closed = False

    def same(self) -> bool:
        """Whether the folder's path still names the folder this holds open."""
        try:
            here, there = os.fstat(self.fd), os.lstat(self.path)
        except OSError:
            return False
        return (here.st_dev, here.st_ino) == (there.st_dev, there.st_ino)

    def remove(self, names: tuple[str, ...]) -> None:
        for name in names:
            try:
                os.unlink(name, dir_fd=self.fd)
            except FileNotFoundError:
                pass
            except OSError as exc:  # a directory planted under the name
                if exc.errno not in (errno.EISDIR, errno.EPERM):
                    raise
                if not procs.remove_tree(os.fsencode(self.path / name)):
                    raise EvaluationError(f"cannot remove {self.path / name}") from exc

    def write(self, name: str, text: str) -> None:
        self.remove((name,))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        with os.fdopen(os.open(name, flags, 0o644, dir_fd=self.fd), "w") as f:
            f.write(text)


def _close(path: str | bytes) -> bool:
    """Make one directory, or one entry of a directory root runs programs from, writable by root
    alone, changing nothing else. Return whether it already was."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return True
    if stat.S_ISLNK(st.st_mode):
        return True  # only who may write its directory can change a link
    ok = True
    if st.st_uid != 0:
        os.lchown(path, 0, -1)
        ok = False
    # Group write is safe only for root's group: the submission's users are in no other group of
    # root's, and in no group at all once they run.
    open_bits = st.st_mode & (0o002 | (0o020 if st.st_gid != 0 else 0))
    if open_bits:
        os.chmod(path, stat.S_IMODE(st.st_mode) & ~open_bits)
        ok = False
    return ok


def _seal(path: bytes) -> bool:
    """Make one delivered entry root's, writable by root alone, without set-id bits."""
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        if st.st_uid or st.st_gid:
            os.lchown(path, 0, 0)
            return False
        return True
    ok = True
    if st.st_uid or st.st_gid:
        os.lchown(path, 0, 0)
        ok = False
    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o6022:
        os.chmod(path, mode & ~0o6022)
        ok = False
    return ok


def close_root_path() -> list[str]:
    """Root runs programs by name from these directories (Harbor packs this folder with `tar`
    after the grader), so none of them, nothing in them and none of their parents may be
    writable by another user. The image is built that way; this makes sure. Returns what had to
    be closed."""
    fixed: list[str] = []
    for d in ROOT_PATH:
        real = os.path.realpath(d)
        parts = real.split("/")
        for i in range(2, len(parts) + 1):
            p = "/".join(parts[:i]) or "/"
            if not _close(p):
                fixed.append(p)
        try:
            names = os.listdir(real)
        except OSError:
            continue
        for name in names:
            p = os.path.join(real, name)
            if not _close(p):
                fixed.append(p)
    return fixed


def close_tree(root: Path) -> int:
    """The delivered tree arrives writable (the copy into this machine opens its top): make every
    entry root's and writable by root alone before anything of the submission runs. Returns how
    many entries had to change."""
    count = 0
    if not root.is_dir() or root.is_symlink():
        return count
    rb = os.fsencode(root)
    for p in [rb, *(item.path for item in listing.walk(rb, 1 << 30, 1 << 30))]:
        try:
            if not _seal(p):
                count += 1
        except OSError:
            continue
    return count


def stray_files() -> list[str]:
    """Anything the build's or the runs' users own anywhere on this machine's own filesystem
    once they are gone, their home directories apart (none is expected: every place they could
    write is swept or closed). Each one found is listed and removed."""
    try:
        out = subprocess.run(
            [
                "/usr/bin/find",
                "/",
                "-xdev",
                "(",
                "-user",
                BUILDER,
                "-o",
                "-user",
                RUNNER,
                ")",
                "-prune",
                "-print0",
            ],
            capture_output=True,
            timeout=300,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ["(the search for leftover files did not finish)"]
    homes = {os.fsencode(str(Path("~" + u).expanduser())) for u in (BUILDER, RUNNER)}
    found = [p for p in out.split(b"\0") if p and p not in homes]
    for start in range(0, len(found), 500):
        procs.remove_tree(*found[start : start + 500])
    return [p.decode("utf-8", "backslashreplace") for p in found[:20]] + (
        [f"... {len(found) - 20} more"] if len(found) > 20 else []
    )


def settle(outputs: Outputs) -> dict:
    """End every process of the build user and the run user, check that none is left, remove
    what they left, then whatever stands under the output names, so only what the grader writes
    next is there."""
    procs.clear_user(
        BUILDER, (*procs.SHARED_DIRS, str(Path("~" + BUILDER).expanduser()))
    )
    procs.clear_user(RUNNER)
    strays = stray_files()
    for user in (BUILDER, RUNNER):
        uid, _ = procs.uid_gid(user)
        if procs.live_tasks(uid):
            raise EvaluationError(f"a process of {user} is still alive")
    if not outputs.same():
        raise EvaluationError(
            f"{outputs.path} is no longer the folder the grader opened"
        )
    outputs.remove(OUTPUTS)
    return {"stray_files_removed": strays}


def load_cases(private: Path) -> tuple[list[Case], dict]:
    """Join the case list with the expected results recorded from the release build."""
    gold: dict[str, dict] = {}
    gold_text = (private / "gold.jsonl").read_bytes()
    for line in gold_text.decode("utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            gold[entry["id"]] = entry
    cases: list[Case] = []
    for line in (private / "cases.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        g = gold.get(c["id"])
        if g is None:
            raise EvaluationError(f"case {c['id']} has no recorded result")
        cases.append(
            Case(
                case_id=c["id"],
                family=c["family"],
                bundle=c["bundle"],
                args=tuple(c["args"]),
                fmt=c["fmt"],
                pair=c.get("pair"),
                expected_rc=g["rc"],
                expected_stdout=g["stdout"],
                stdin=c.get("stdin"),
                files=tuple(c["files"]) if "files" in c else None,
            )
        )
    if not cases:
        raise EvaluationError("the private case set is empty")
    meta_path = private / "gold-meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    meta["gold_sha256"] = hashlib.sha256(gold_text).hexdigest()
    return cases, meta


def delivered_kinds(root: Path) -> dict[str, int]:
    """How many delivered files of each suffix (the twenty most common), for review."""
    kinds: Counter = Counter()
    if root.is_dir():
        for item in listing.walk(os.fsencode(root)):
            if isinstance(item, listing.Entry) and item.kind == "f":
                kinds[os.path.splitext(item.rel)[1] or "(none)"] += 1
    return dict(kinds.most_common(20))


def refused(reason: str, metrics: dict) -> VerificationResult:
    """A delivery scored 0 without a build: every family at 0."""
    detail = {
        f: {"weight": w, "present": 1.0, "pass": 0.0, "g": 0.0}
        for f, w in WEIGHTS.items()
    }
    return VerificationResult(
        reward=0.0,
        metrics=dict(metrics, reward=0.0, refused=reason, weighting=detail),
    )


def verify(
    context: VerificationContext, handed: handoff.Handoff, began: float
) -> VerificationResult:
    cases, gold_meta = load_cases(context.private)
    baselines_path = context.private / "baselines.json"
    baselines = (
        json.loads(baselines_path.read_text()) if baselines_path.is_file() else {}
    )
    started = time.monotonic()
    metrics: dict = {
        "cases": len(cases),
        "gold": gold_meta,
        "handoff": dict(
            handed.summary,
            state=handed.state,
            reason=handed.reason,
            entries=handed.entries,
            files=handed.files,
            bytes=handed.bytes,
        ),
        "delivered_kinds": delivered_kinds(context.submission),
    }
    if handed.state != "listed":
        return refused(handed.reason or "nothing was delivered", metrics)
    copied = (
        integrity.findings(context.submission) if context.submission.is_dir() else []
    )
    metrics["dogwood_source_files"] = copied
    if copied:
        return refused(
            f"the delivery holds {len(copied)} of Dogwood's own files (its source or its "
            "1.2.0 build), which the brief rules out",
            metrics,
        )
    built = build(context.submission, context.work, context.limits)
    limits = context.limits
    until = began + limits.verifier_sec - limits.settle_sec
    results = run_all(built.binary, cases, context.private / "bundles", limits, until)
    rates = family_pass_rates(results)
    score, detail = reward(rates, baselines)
    passed = sum(1 for r in results if r.passed)
    metrics.update(
        {
            "reward": score,
            "build": {
                "ok": built.ok,
                "detail": built.detail,
                "seconds": round(built.seconds, 1),
            },
            "cases_passed": passed,
            "families": rates,
            "weighting": detail,
            "all_cases": passed == len(results),
            "at_least_99pct": passed >= 0.99 * len(results),
            "at_least_95pct": passed >= 0.95 * len(results),
            "seconds": round(time.monotonic() - started, 1),
            "failed_cases": [r.case_id for r in results if not r.passed][:200],
            "leftover_processes_ended": dict(procs.LEFTOVERS),
        }
    )
    return VerificationResult(reward=score, metrics=metrics)


def main() -> int:
    began = time.monotonic()
    protected = procs.protect_self()
    adopts_orphans = procs.become_subreaper()
    logs_closed = _close_quietly(str(LOGS.parent))
    outputs = Outputs(LOGS)
    outputs.remove(OUTPUTS)
    try:
        path_fixed = close_root_path()
        tree_fixed = close_tree(SUBMISSION)
        handoff.close(handoff.RECORDS)
        handed = handoff.check(SUBMISSION)
        context = VerificationContext(
            submission=SUBMISSION,
            private=PRIVATE,
            logs=LOGS,
            work=Path(tempfile.mkdtemp(prefix="dw-build-")),
        )
        result = verify(context, handed, began)
        settled = settle(outputs)
    except Exception:  # noqa: BLE001 - any failure here is the evaluation's, never the candidate's
        error = traceback.format_exc()
        try:
            settle(outputs)
        except Exception:  # noqa: BLE001
            error += (
                "\nwhile ending the submission's processes:\n" + traceback.format_exc()
            )
        outputs.write("evaluation-error.txt", error)
        return 1
    metrics = dict(
        result.metrics,
        **settled,
        adopts_orphans=adopts_orphans,
        grader_protected_from_oom=protected,
        output_folder_closed=outputs.closed and logs_closed,
        root_path_closed_here=path_fixed,
        delivered_entries_closed=tree_fixed,
    )
    outputs.write("metrics.json", json.dumps(metrics, indent=1, sort_keys=True))
    # Last: the reward exists only once everything else is done.
    outputs.write("reward.txt", f"{result.reward}\n")
    return 0


def _close_quietly(path: str) -> bool:
    try:
        _close(path)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(main())
