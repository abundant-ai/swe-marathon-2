"""Validate a fixed six-station editor artifact outside the candidate process."""

from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import pwd
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

TESTS = Path(__file__).resolve().parent
PRIVATE = TESTS / "private"
OUTPUT = Path("/logs/verifier")
WORK = Path("/app/work")
SOURCE_LIMIT = 2 * 1024**2
ARCHIVE_LIMIT = 1024 * 1024
WORKER_SECONDS = 200
sys.path.insert(0, str(PRIVATE / "precision-pilot"))
sys.path.insert(0, str(TESTS))
from contract import validate, validate_pace, validate_station
from test_scanner import (
    VerificationContext,
    VerificationResult,
    requirement_results,
)


class CandidateError(Exception):
    """A missing submission, execution failure, or invalid numeric return."""


def read_regular(path, limit):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno in (
            errno.ENOENT,
            errno.ELOOP,
            errno.EACCES,
            errno.EISDIR,
            errno.ENOTDIR,
        ):
            raise CandidateError(
                f"Unusable or missing submitted file {path.name}"
            ) from exc
        raise
    with os.fdopen(fd, "rb") as file:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise CandidateError(f"Invalid file type or size for {path.name}")
        data = file.read(limit + 1)
        if len(data) > limit:
            raise CandidateError(f"File exceeds its declared limit: {path.name}")
        return data


def bounded_array(archive, member, expected):
    expected_bytes = int(np.prod(expected)) * 8
    if (
        member.compress_type != zipfile.ZIP_STORED
        or member.file_size != member.compress_size
        or member.file_size > expected_bytes + 1024
        or member.flag_bits & 1
    ):
        raise CandidateError("Unexpected numeric member encoding")
    with archive.open(member) as f:
        version = np.lib.format.read_magic(f)
        header = {
            (1, 0): np.lib.format.read_array_header_1_0,
            (2, 0): np.lib.format.read_array_header_2_0,
        }.get(version)
        if header is None:
            raise CandidateError("Unsupported numeric header")
        shape, fortran, dtype = header(f, max_header_size=768)
        if (
            tuple(shape) != expected
            or dtype.kind != "f"
            or dtype.itemsize not in (4, 8)
        ):
            raise CandidateError("Invalid returned parameter shape or type")
        size = int(np.prod(expected)) * dtype.itemsize
        payload = f.read(size + 1)
        if len(payload) != size:
            raise CandidateError("Invalid numeric member length")
        array = np.frombuffer(payload, dtype).reshape(
            shape, order="F" if fortran else "C"
        )
        if not np.isfinite(array).all():
            raise CandidateError("Nonfinite returned parameter")
        return array


def parse_numeric(data, originals):
    params = ("W", "b", "heads", "bridge", "pace")
    expected = {
        f"{kind}{i}.npy": bank[key].shape
        for i, bank in enumerate(originals)
        for kind, key in zip(params, ("W", "b", "v", "bridge", "pace"))
    }
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = archive.infolist()
            if len(files) != len(expected) or {f.filename for f in files} != set(
                expected
            ):
                raise CandidateError("Wrong set of returned parameter arrays")
            artifact = {
                f.filename[:-4]: bounded_array(archive, f, expected[f.filename])
                for f in files
            }
    except (ValueError, OSError, EOFError, IndexError, zipfile.BadZipFile) as exc:
        raise CandidateError("Invalid numeric artifact") from exc
    usage = []
    for i, old in enumerate(originals):
        try:
            usage.append(
                validate(
                    old["W"],
                    old["b"],
                    old["v"],
                    old["bridge"],
                    artifact[f"W{i}"],
                    artifact[f"b{i}"],
                    artifact[f"heads{i}"],
                    artifact[f"bridge{i}"],
                )
            )
            validate_pace(artifact[f"pace{i}"])
            if len(usage) == 3:
                validate_station(usage)
                usage = []
        except ValueError as exc:
            raise CandidateError(str(exc)) from exc
    if usage:
        raise RuntimeError("Incomplete station checkpoint group")
    return artifact


def same_uid_processes(uid):
    result = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            lines = (entry / "status").read_text(errors="replace").splitlines()
        except (FileNotFoundError, ProcessLookupError):
            continue
        identity = next((l.split()[1:] for l in lines if l.startswith("Uid:")), [])
        state = next((l.split()[1] for l in lines if l.startswith("State:")), "")
        if identity and int(identity[0]) == uid and state != "Z":
            result.append(int(entry.name))
    return result


def stop_worker(uid, proc):
    # The separate verifier dedicates this UID exclusively to candidate code.
    # A process that opens another session remains visible under the same UID.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for _ in range(30):
        remaining = same_uid_processes(uid)
        if not remaining:
            break
        for pid in remaining:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.04)
    else:
        raise RuntimeError("Unable to terminate worker processes")
    proc.wait(timeout=5)


def execute(source, build_inputs):
    user = pwd.getpwnam("pilot-exec")
    launcher = shutil.which("setpriv")
    if not launcher or os.geteuid() != 0:
        raise RuntimeError("Missing verifier privilege boundary")
    if same_uid_processes(user.pw_uid):
        raise RuntimeError("The dedicated worker account is already in use")
    with tempfile.TemporaryDirectory(prefix="inspection-") as tmp:
        root = Path(tmp)
        root.chmod(0o711)
        inp = root / "inputs"
        inp.mkdir(mode=0o755)
        out = root / "output"
        out.mkdir()
        os.chown(out, user.pw_uid, user.pw_gid)
        (inp / "submission.py").write_bytes(source)
        shutil.copyfile(PRIVATE / "worker.py", inp / "build.py")
        shutil.copyfile(TESTS / "contract.py", inp / "contract.py")
        shutil.copyfile(
            PRIVATE / "precision-pilot/deployment.py", inp / "deployment.py"
        )
        build_inputs(inp)
        with np.load(inp / "pairs.npz", allow_pickle=False) as data:
            originals = [
                {k: data[k][i] for k in ("W", "b", "v", "bridge", "pace")}
                for i in range(len(data["W"]))
            ]
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "OPENBLAS_NUM_THREADS": "1",
            "HOME": str(out),
            "TMPDIR": str(out),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        identity = [
            launcher,
            "--no-new-privs",
            "--reuid",
            str(user.pw_uid),
            "--regid",
            str(user.pw_gid),
            "--clear-groups",
        ]
        # Apply the same hard limits before the interpreter starts in both runs.
        # prlimit avoids running a Python callback in a fork of the BLAS process.
        limited = [
            *identity,
            "/usr/bin/prlimit",
            "--as=1073741824:1073741824",
            "--nproc=16:16",
            "--nofile=96:96",
            "--fsize=16777216:16777216",
            "--core=0:0",
            "--cpu=180:185",
            "--",
        ]
        health = subprocess.run(
            [*limited, sys.executable, "-I", "-B", "-c", "import numpy"],
            cwd=out,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
        if health.returncode:
            raise RuntimeError(
                "Verifier could not launch its isolated numerical worker"
            )
        args = [*limited, sys.executable, "-B", str(inp / "build.py"), "inspection"]
        with tempfile.TemporaryFile() as log:
            proc = subprocess.Popen(
                args,
                cwd=inp,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=log,
                start_new_session=True,
            )
            try:
                try:
                    code = proc.wait(timeout=WORKER_SECONDS)
                except subprocess.TimeoutExpired as exc:
                    raise CandidateError("Editor exceeded worker time limit") from exc
            finally:
                stop_worker(user.pw_uid, proc)
            if code:
                log.seek(0, os.SEEK_END)
                n = log.tell()
                log.seek(max(0, n - 1000))
                message = log.read(1000).decode(errors="replace")
                raise CandidateError("Editor failed: " + message)
        return parse_numeric(
            read_regular(out / "artifact.npz", ARCHIVE_LIMIT), originals
        )


def check_coverage(measured: dict, diagnostic_target: int) -> None:
    """Require complete site, bank, prior-head and paired continuation denominators."""
    for field in ("rows", "installation"):
        if len(measured[field]) != 6 or any(len(site) != 3 for site in measured[field]):
            raise RuntimeError("Incomplete site or field measurements")
    unavailable = measured.get("unavailable_handovers", [])
    if unavailable not in ([], [diagnostic_target]):
        raise RuntimeError("Missing official handover")
    for field in ("runs", "frozen_runs"):
        arms = measured[field]
        if len(arms) != 2 or any(
            len(arm) != (0 if index in unavailable else 18)
            for index, arm in enumerate(arms)
        ):
            raise RuntimeError("Incomplete future sequence replay for " + field)
        for arm in arms:
            for phase in arm:
                if [len(v) for v in phase["revisit_by_phase"]] != [1, 2, 3, 4]:
                    raise RuntimeError("Incomplete earlier-head revisits")
                if len(phase["initial_heads"]) != 4 or any(
                    len(phase[k]) != 3 for k in ("early", "initial", "final")
                ):
                    raise RuntimeError("Incomplete per-order learning outcomes")
                if (
                    len(phase["old_baseline"]) != 8
                    or len(phase["legacy"]) != 21
                    or any(len(v) != 8 for v in phase["legacy"])
                ):
                    raise RuntimeError(
                        "Incomplete archived inspections from the two scanners"
                    )


def staging_inputs():
    """Rebuild the three public station-17 banks from the trusted checkpoint copies."""
    from inspection_eval import branch_seed, many_gallery, station

    seeds = [branch_seed(977, index) for index in range(3)]
    states = [station(seed) for seed in seeds]
    galleries = [many_gallery(seed) for seed in seeds]
    return {
        "W": np.stack([state["W"] for state in states]),
        "b": np.stack([state["b"] for state in states]),
        "v": np.stack([state["legacy"] for state in states]),
        "bridge": np.stack([state["bridge"] for state in states]),
        "x": np.stack([x for x, _ in galleries]),
        "tags": np.stack([t for _, t in galleries]),
        "pace": np.ones((3, 2, 2, 28)),
    }


def receipt_reproduced(receipt, source) -> bool:
    """Replay the public smoke installation in a fresh worker separate from the six graded sites."""
    records = receipt.get("details")
    if not isinstance(records, list) or len(records) != 3:
        return False
    from deployment import hidden

    cal = staging_inputs()
    try:
        artifact = execute(source, lambda dest: np.savez(dest / "pairs.npz", **cal))
    except CandidateError:
        return False
    for bank, row in enumerate(records):
        if not isinstance(row, dict):
            return False
        old = {name: cal[name][bank] for name in ("W", "b", "bridge")}
        new = {name: artifact[f"{name}{bank}"] for name in old}
        x, tags, heads = (cal[name][bank] for name in ("x", "tags", "v"))
        features = hidden(x, new)
        old_scores = np.einsum("nbh,bch->nc", hidden(x, old), heads)
        new_scores = np.einsum("nbh,bch->nc", features, artifact[f"heads{bank}"])
        known = tags[:, 64] != 255
        marked = features[known].reshape(known.sum(), -1)
        label = tags[known, 64:66]
        distance = np.mean((marked[:, None] - marked[None]) ** 2, axis=2)
        np.fill_diagonal(distance, np.inf)
        changed = (old["W"] != new["W"]).any(-1) | (old["b"] != new["b"])
        expected = {
            "station": int(tags[0, 66]),
            "field": int(tags[0, 69]),
            "verified": int(known.sum()),
            "edited_rows": np.argwhere(changed).tolist(),
        }
        if any(row.get(k) != value for k, value in expected.items()):
            return False
        diagnostics = {
            "mean_shift_rate": artifact[f"pace{bank}"].mean((1, 2)),
            "neighbor_glyph_pose": (label[distance.argmin(1)] == label).mean(0),
            "normalized_old_drift": np.sqrt(((new_scores - old_scores) ** 2).mean(0))
            / old_scores.std(0).clip(0.05),
        }
        for key, value in diagnostics.items():
            try:
                actual = np.asarray(row.get(key), dtype=float)
            except (TypeError, ValueError, OverflowError):
                return False
            if actual.shape != value.shape or not np.allclose(
                actual, value, rtol=1e-4, atol=1e-6
            ):
                return False
    return True


def verify(context: VerificationContext) -> VerificationResult:
    """Rebuild all physical installations, replay both handovers and score the selected target.

    Model code runs only in the dedicated numerical worker. A candidate-domain
    failure receives zero. A missing reference or incomplete trusted measurement
    propagates to the caller, which records an infrastructure failure.
    """
    from inspection_eval import build_inputs, reward, score_edits

    def result(report, sites=()):
        context_scores = replace(
            context,
            build=report["build"],
            matched_smoke=report.get("staging_receipt_reproduced"),
            station_scores=tuple(sites),
            reward=report["reward"],
            frozen_comparison=report.get("adaptation"),
        )
        checks = requirement_results(context_scores)
        report["verification"] = asdict(checks)
        (context.output / "metrics.json.new").write_text(
            json.dumps(report, allow_nan=False)
        )
        return checks

    try:
        source = read_regular(context.work / "submission.py", SOURCE_LIMIT)
    except CandidateError as exc:
        return result(
            {
                "build": "failed",
                "error_domain": "candidate",
                "reason": str(exc),
                "reward": 0.0,
            }
        )
    sha = hashlib.sha256(source).hexdigest()
    try:
        receipt = json.loads(read_regular(context.work / "test_receipt.json", 65536))
    except (CandidateError, ValueError, RecursionError):
        receipt = {}
    tested = isinstance(receipt, dict) and receipt.get("source_sha256") == sha
    reproduced = tested and receipt_reproduced(receipt, source)
    try:
        artifact = execute(source, build_inputs)
    except CandidateError as exc:
        return result(
            {
                "build": "failed",
                "error_domain": "candidate",
                "reason": str(exc),
                "reward": 0.0,
                "source_sha256": sha,
                "test_receipt_matches": tested,
                "staging_receipt_reproduced": reproduced,
            }
        )
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            official = "ab".index(context.target)
            alternate = 1 - official
            measured = score_edits(artifact, diagnostic_target=alternate)
            check_coverage(measured, alternate)
            grades = {context.target: reward(measured, official)}
            if alternate not in measured["unavailable_handovers"]:
                try:
                    grades["ab"[alternate]] = reward(measured, alternate)
                except FloatingPointError:
                    measured["unavailable_handovers"].append(alternate)
    except FloatingPointError:
        return result(
            {
                "build": "invalid",
                "error_domain": "candidate",
                "reason": "Numerically unstable edit",
                "reward": 0.0,
                "source_sha256": sha,
                "test_receipt_matches": tested,
                "staging_receipt_reproduced": reproduced,
            }
        )
    target = grades[context.target]
    report = {
        "build": "valid",
        "source_sha256": sha,
        "test_receipt_matches": tested,
        "staging_receipt_reproduced": reproduced,
        "target_rewards": {k: v["reward"] for k, v in grades.items()},
        "adaptation": {
            key: target["acquisition_vs_own_frozen"][key]
            for key in ("mean", "normalized", "anchor")
        },
        "reward": float(target["reward"]),
        "measured": measured,
    }
    np.savez_compressed(context.output / "artifact.npz", **artifact)
    (context.output / "submitted.py").write_bytes(source)
    return result(report, target["pairs"])


def main() -> None:
    """Publish the verified result for this run or an isolated infrastructure diagnostic."""
    OUTPUT.mkdir(exist_ok=True, parents=True)
    TESTS.chmod(0o700)
    OUTPUT.chmod(0o700)
    for name in (
        "metrics.json",
        "metrics.json.new",
        "reward.txt",
        "reward.txt.new",
        "submitted.py",
        "artifact.npz",
        "infrastructure.json",
    ):
        (OUTPUT / name).unlink(missing_ok=True)
    try:
        target = json.loads((PRIVATE / "condition.json").read_text())["target"]
        if target not in ("a", "b"):
            raise RuntimeError("Unrecognized physical handover")
        measured = verify(VerificationContext(target, WORK, OUTPUT))
        (OUTPUT / "metrics.json.new").replace(OUTPUT / "metrics.json")
        (OUTPUT / "reward.txt.new").write_text(f"{measured.metrics['reward']:.9f}\n")
        (OUTPUT / "reward.txt.new").replace(OUTPUT / "reward.txt")
    except Exception as exc:
        for name in (
            "metrics.json",
            "metrics.json.new",
            "reward.txt",
            "reward.txt.new",
        ):
            (OUTPUT / name).unlink(missing_ok=True)
        (OUTPUT / "infrastructure.json").write_text(
            json.dumps({"domain": "verifier", "type": type(exc).__name__})
        )
        raise


if __name__ == "__main__":
    main()
