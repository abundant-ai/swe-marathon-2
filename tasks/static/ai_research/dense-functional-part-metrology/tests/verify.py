"""Build transferred mesh source under a dedicated UID, then score bounded numeric output."""

from __future__ import annotations

import ctypes
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
import zlib
from pathlib import Path

import numpy as np
from numpy.lib import format as npy

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
from test_reconstruction import (
    ReconstructionMeasurements,
    VerificationContext,
    VerificationResult,
    as_report,
    summarize,
)

PRIVATE = TESTS / "private"
WORK = Path("/app/work")
OUTPUT = Path("/logs/verifier")
NAMES = ("vertices", "faces", "colors", "face_ids", "part_ids")
MB = 1024**2
MAX_SOURCE = 2 * MB
MAX_NUMERIC_ARCHIVE = 5 * MB
LENGTHS = {
    "vertices": (60000, 3),
    "colors": (60000, 3),
    "faces": (20000, 3),
    "face_ids": (20000,),
    "part_ids": (20000,),
    "optical_to_rig": (4, 4),
}
FRESH = (
    "reward.txt",
    "metrics.json",
    "artifact.npz",
    "submitted.py",
    "infrastructure.json",
)


class CandidateError(Exception):
    """A documented input, execution or numerical submission contract was violated."""


def regular_bytes(path, limit):
    """Read an ordinary bounded file without following its last path component."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError as exc:
        raise CandidateError(f"Missing {path.name}") from exc
    except OSError as exc:
        if exc.errno in (40, 13, 21):
            raise CandidateError(f"Unusable file {path.name}") from exc
        raise
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise CandidateError(f"Invalid {path.name} size or file type")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise CandidateError(f"{path.name} exceeds its limit")
        return data


def bounded_arrays(blob, names):
    """Inspect each NPY header before allocating, checking lengths and cumulative decoded bytes."""
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            infos = archive.infolist()
            expected = {name + ".npy" for name in names}
            if len(infos) != len(expected) or {v.filename for v in infos} != expected:
                raise CandidateError("Unexpected or duplicate numerical members")
            if sum(v.file_size for v in infos) > MAX_NUMERIC_ARCHIVE:
                raise CandidateError("Expanded numeric arrays exceed 5 MiB")
            headers = {}
            for info in infos:
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise CandidateError("Unsupported numeric array compression")
                name = info.filename[:-4]
                with archive.open(info) as raw:
                    version = npy.read_magic(raw)
                    if version == (1, 0):
                        shape, _, dtype = npy.read_array_header_1_0(
                            raw, max_header_size=1024
                        )
                    elif version == (2, 0):
                        shape, _, dtype = npy.read_array_header_2_0(
                            raw, max_header_size=1024
                        )
                    else:
                        raise CandidateError(f"Unsupported numerical header {name}")
                    limit = LENGTHS[name]
                    if len(shape) != len(limit) or any(
                        type(d) is not int or d <= 0 or d > n
                        for d, n in zip(shape, limit)
                    ):
                        raise CandidateError(f"Invalid dimensions of {name}")
                    if len(limit) == 2 and shape[1] != limit[1]:
                        raise CandidateError(f"Invalid columns of {name}")
                    if name == "optical_to_rig" and shape != (4, 4):
                        raise CandidateError("Expected a 4 by 4 mounting")
                    kinds = "iu" if name in ("faces", "part_ids", "face_ids") else "iuf"
                    if (
                        dtype.fields
                        or dtype.subdtype
                        or dtype.kind not in kinds
                        or dtype.itemsize > 8
                    ):
                        raise CandidateError(f"Expected plain numeric data for {name}")
                    count = 1
                    for d in shape:
                        count *= d
                    if raw.tell() + count * dtype.itemsize != info.file_size:
                        raise CandidateError(f"Numerical member length mismatch {name}")
                    headers[name] = shape
            if headers["vertices"] != headers["colors"] or not (
                headers["faces"][0] == headers["part_ids"][0] == headers["face_ids"][0]
            ):
                raise CandidateError("Mesh array lengths disagree")
            # Header dimensions and declared payload have now been bounded for every member.
            with np.load(
                io.BytesIO(blob), allow_pickle=False, max_header_size=1024
            ) as data:
                result = {name: data[name] for name in names}
    except (
        ValueError,
        EOFError,
        KeyError,
        zipfile.BadZipFile,
        zlib.error,
        RuntimeError,
        NotImplementedError,
    ) as exc:
        raise CandidateError(f"Invalid mesh archive: {type(exc).__name__}") from exc
    v, f, c, o, part = (result[k] for k in NAMES)
    if not np.isfinite(v).all() or (np.abs(v.astype(float)) > 10000).any():
        raise CandidateError("Coordinates outside representable workspace")
    if not np.isfinite(c).all() or c.min() < 0 or c.max() > 255:
        raise CandidateError("Invalid vertex colors")
    if f.min() < 0 or f.max() >= len(v):
        raise CandidateError("Triangle index outside vertex array")
    if not np.isin(o, (0, 1, 2, 3)).all() or not np.isin(part, range(11)).all():
        raise CandidateError("Invalid object or part ID")
    if np.any(
        ((part >= 1) & (part <= 8) & (o != 1))
        | ((part == 9) & (o != 2))
        | ((part == 10) & (o != 3))
    ):
        raise CandidateError("Part belongs to the wrong object")
    if "optical_to_rig" in result:
        x = result["optical_to_rig"].astype(float)
        if (
            not np.isfinite(x).all()
            or np.max(np.abs(x)) > 10000
            or not np.allclose(x[3], [0, 0, 0, 1], atol=1e-7)
        ):
            raise CandidateError("Invalid homogeneous mounting")
        if (
            not np.allclose(x[:3, :3].T @ x[:3, :3], np.eye(3), atol=1e-5)
            or abs(np.linalg.det(x[:3, :3]) - 1) > 1e-5
        ):
            raise CandidateError("Improper mounting rotation")
    return result


def clean_processes(launch_pid, uid):
    """Terminate the session and any remaining processes owned by this verifier-only UID."""
    try:
        os.killpg(launch_pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for _ in range(6):
        live = []
        for proc in Path("/proc").iterdir():
            if not proc.name.isdecimal():
                continue
            try:
                # A pidfd binds the signal to the inspected process even across PID reuse.
                if proc.stat().st_uid != uid:
                    continue
                fd = os.pidfd_open(int(proc.name))
                try:
                    data = (proc / "status").read_text()
                    fields = dict(
                        line.split(":", 1) for line in data.splitlines() if ":" in line
                    )
                    if int(fields["Uid"].split()[0]) != uid or fields[
                        "State"
                    ].lstrip().startswith("Z"):
                        continue
                    live.append(proc.name)
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                finally:
                    os.close(fd)
            except (FileNotFoundError, ProcessLookupError):
                continue
        if not live:
            return
        time.sleep(0.025)
    raise RuntimeError("Verifier worker UID still has a live process")


def expose_observations():
    """Materialize original public observations under their documented absolute paths."""
    WORK.chmod(0o755)
    for fixture in (PRIVATE / "public-observations").iterdir():
        if not fixture.is_file() or fixture.is_symlink():
            raise RuntimeError("Malformed trusted observation fixture")
        absolute = WORK / fixture.name
        if absolute.is_symlink():
            raise RuntimeError(f"Unexpected deployment input alias {fixture.name}")
        if absolute.exists():
            if not absolute.is_file():
                raise RuntimeError(f"Invalid deployment input {fixture.name}")
            with absolute.open("rb") as deployed, fixture.open("rb") as truth:
                if (
                    hashlib.file_digest(deployed, "sha256").digest()
                    != hashlib.file_digest(truth, "sha256").digest()
                ):
                    raise RuntimeError(f"Conflicting deployment input {fixture.name}")
        else:
            shutil.copyfile(fixture, absolute)
        absolute.chmod(0o444)


def clean_scratch(frozen):
    """Remove only transient worker output after all worker processes have stopped."""
    WORK.chmod(0o755)
    for path in WORK.iterdir():
        if path.name in frozen:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def check_reference_coverage():
    """Enforce all frozen native contours and all four coarse depth denominators."""
    from score import Reference, mask

    expected = json.loads((TESTS / "truth-contract.json").read_text())
    ref = Reference.load(PRIVATE / "precision-pilot/data/clutter/data", "a")
    if len(expected) != 4:
        raise RuntimeError("Expected four held-out poses")
    for view, contract in enumerate(expected):
        polygons = json.loads(
            (PRIVATE / f"functional-parts/held-{view}.json").read_text()
        )
        counts = {name: int(mask(polygon).sum()) for name, polygon in polygons.items()}
        known = ref.depth[view] > 0
        parents = [int((known & (ref.labels[view] == k)).sum()) for k in (1, 2, 3)]
        actual = {
            "part_pixels": counts,
            "kinect_valid": int(known.sum()),
            "parent_measured": parents,
        }
        if actual != contract:
            raise RuntimeError(
                f"Incomplete or changed evaluation coverage in held-out view {view + 1}"
            )


def rebuild(source, names):
    """Run from the public working directory with immutable inputs and disposable scratch."""
    user = pwd.getpwnam("meshworker")
    with tempfile.TemporaryDirectory(prefix="mesh-") as directory:
        base = Path(directory)
        base.chmod(0o711)
        out = base / "output"
        out.mkdir(mode=0o700)
        os.chown(out, user.pw_uid, user.pw_gid)
        my_inputs = {p.name for p in (PRIVATE / "public-observations").iterdir()}
        frozen = my_inputs | {"submission.py", "test_receipt.json"}
        unexpected = {p.name for p in WORK.iterdir()} - frozen
        if unexpected:
            raise RuntimeError("Undeclared files in fresh deployment workspace")
        expose_observations()
        if regular_bytes(WORK / "submission.py", MAX_SOURCE) != source:
            raise RuntimeError(
                "Transferred source changed during workspace preparation"
            )
        for file in WORK.iterdir():
            if file.is_symlink() or not file.is_file():
                raise CandidateError(
                    "Transferred workspace entry is not a regular file"
                )
            os.chown(file, 0, 0)
            file.chmod(0o444)
        bootstrap = base / "_bootstrap.py"
        shutil.copyfile(TESTS / "worker_bootstrap.py", bootstrap)
        cmd = [
            "/usr/bin/setpriv",
            "--no-new-privs",
            "--reuid",
            str(user.pw_uid),
            "--regid",
            str(user.pw_gid),
            "--clear-groups",
            sys.executable,
            "-B",
            str(bootstrap),
        ]
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "HOME": str(out),
            "TMPDIR": str(out),
            "MESH_ARTIFACT": str(out / "artifact.npz"),
            "MESH_FIELDS": json.dumps(names),
        }
        # This verifier runs one worker. Adopt orphaned grandchildren so they can
        # be reaped after the dedicated UID has been cleared.
        if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
            raise RuntimeError("Cannot configure verifier subreaper")
        rd, wr = os.pipe()
        try:
            env["MESH_READY"] = str(wr)
            with (base / "stderr.txt").open("w+b") as err:
                # Fixed input names are root-owned. The sticky directory permits
                # ordinary local extraction without allowing input removal.
                WORK.chmod(0o1777)
                proc = subprocess.Popen(
                    cmd,
                    cwd=WORK,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=err,
                    start_new_session=True,
                    pass_fds=(wr,),
                )
                os.close(wr)
                wr = -1
                try:
                    try:
                        code = proc.wait(timeout=640)
                    except subprocess.TimeoutExpired as exc:
                        raise CandidateError(
                            "Scene builder exceeded its time budget"
                        ) from exc
                finally:
                    clean_processes(proc.pid, user.pw_uid)
                    proc.wait(timeout=5)
                    for _ in range(12):
                        try:
                            child, _ = os.waitpid(-1, os.WNOHANG)
                            if child == 0:
                                time.sleep(0.02)
                        except ChildProcessError:
                            break
                if os.read(rd, 1) != b"R":
                    raise RuntimeError("Isolated builder failed to initialize")
                if code:
                    err.seek(0, os.SEEK_END)
                    offset = max(0, err.tell() - 768)
                    err.seek(offset)
                    raise CandidateError(
                        "Scene builder failed: "
                        + err.read(768).decode(errors="replace")
                    )
        finally:
            if wr >= 0:
                os.close(wr)
            os.close(rd)
            clean_scratch(frozen)
        return bounded_arrays(
            regular_bytes(out / "artifact.npz", MAX_NUMERIC_ARCHIVE), names
        )


def commit_text(name, value):
    tmp = OUTPUT / (name + ".new")
    tmp.write_text(value)
    tmp.replace(OUTPUT / name)


def verify(context: VerificationContext) -> VerificationResult:
    """Rebuild the program and measure the selected protocol on all four withheld views."""
    mode = context.mode
    if mode not in ("rig", "dense"):
        raise RuntimeError("Unknown trusted task mode")
    names = NAMES + ("optical_to_rig",) if mode == "rig" else NAMES
    for f in ("functional-parts", "dense-functional-parts", "rig-functional-parts"):
        sys.path.insert(0, str(PRIVATE / f))
    from score import score
    from whole_scene import scene_metrics

    check_reference_coverage()

    source_evidence = {}
    try:
        source = regular_bytes(WORK / "submission.py", MAX_SOURCE)
        digest = hashlib.sha256(source).hexdigest()
        try:
            receipt = json.loads(regular_bytes(WORK / "test_receipt.json", 65536))
        except (CandidateError, ValueError):
            receipt = {}
        matches = isinstance(receipt, dict) and receipt.get("source_sha256") == digest
        source_evidence = {"source_sha256": digest, "test_receipt_matches": matches}
        (OUTPUT / "submitted.py").write_bytes(source)
        artifact = rebuild(source, names)
        mesh = tuple(artifact[k] for k in NAMES)
        measured = score(mesh)
        whole = scene_metrics(mesh)
        measured["whole_scene"] = whole
        reward = min(measured["reward"], whole["rgbd_5cm_10percent_coverage"])
        if mode == "rig":
            from registration import measure

            r = PRIVATE / "rig-functional-parts"
            with np.load(r / "pose-checkpoints.npz") as truth:
                registration = measure(
                    artifact["optical_to_rig"], truth, np.load(r / "contact-radii.npy")
                )
            measured["rig_registration"] = registration
            reward = min(reward, registration["reacquisition_rate"])
        measured["reward"] = float(reward)
        report = {
            "build": "valid",
            **source_evidence,
            "reward": float(reward),
            "measured": measured,
        }
        with (OUTPUT / "artifact.npz.new").open("wb") as stream:
            np.savez_compressed(stream, **artifact)
        (OUTPUT / "artifact.npz.new").replace(OUTPUT / "artifact.npz")
    except CandidateError as exc:
        report = {
            "build": "invalid",
            **source_evidence,
            "error_domain": "candidate",
            "reason": str(exc),
            "reward": 0.0,
        }
    return summarize(ReconstructionMeasurements(mode, report))


def main():
    """Only candidate-domain failures receive a numerical zero; hidden fixture errors propagate."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    TESTS.chmod(0o700)
    OUTPUT.chmod(0o700)
    for n in FRESH:
        (OUTPUT / n).unlink(missing_ok=True)
        (OUTPUT / (n + ".new")).unlink(missing_ok=True)
    try:
        mode = json.loads((TESTS / "mode.json").read_text())["mode"]
        result = verify(VerificationContext(mode))
        report = {**result.report, "verification": as_report(result)}
        commit_text("metrics.json", json.dumps(report, allow_nan=False))
        commit_text("reward.txt", f"{result.metrics['reward']:.9f}\n")
    except Exception as exc:
        (OUTPUT / "reward.txt").unlink(missing_ok=True)
        (OUTPUT / "metrics.json").unlink(missing_ok=True)
        commit_text(
            "infrastructure.json",
            json.dumps(
                {
                    "error_domain": "verifier",
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            ),
        )
        raise


if __name__ == "__main__":
    main()
