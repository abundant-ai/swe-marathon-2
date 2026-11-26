"""Score the transferred submission in the separate Harbor verifier sandbox."""

import hashlib
import json
import os
import pwd
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

TESTS = Path(__file__).resolve().parent
PRIVATE = TESTS / "private"
OUTPUT = Path("/logs/verifier")
WORK = Path("/app/work")
sys.path.insert(0, str(PRIVATE / "precision-pilot"))


def read_regular(path: Path, limit: int) -> bytes:
    """Reject artifact links and nonregular inputs before copying source to the worker."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            raise ValueError("Invalid candidate file")
        return f.read(limit + 1)


def worker(source: bytes, task: str) -> dict:
    """Execute an unprivileged process with only the weights it needs, no verifier access."""
    user = pwd.getpwnam("nobody")
    with tempfile.TemporaryDirectory(prefix="artifact-") as d:
        root = Path(d)
        root.chmod(0o711)
        inputs = root / "inputs"
        inputs.mkdir(mode=0o755)
        out = root / "output"
        out.mkdir()
        os.chown(out, user.pw_uid, user.pw_gid)
        (inputs / "submission.py").write_bytes(source)
        shutil.copyfile(PRIVATE / "worker.py", inputs / "build.py")
        if task == "inspection":
            from inspection_eval import build_inputs

            build_inputs(inputs)

        def restrict():
            resource.setrlimit(resource.RLIMIT_FSIZE, (55 * 1024**2, 55 * 1024**2))
            resource.setrlimit(resource.RLIMIT_CPU, (180, 185))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "OPENBLAS_NUM_THREADS": "1",
            "HOME": str(out),
            "TMPDIR": str(out),
        }
        proc = subprocess.run(
            [
                "/usr/bin/setpriv",
                "--no-new-privs",
                "--reuid",
                str(user.pw_uid),
                "--regid",
                str(user.pw_gid),
                "--clear-groups",
                sys.executable,
                "-B",
                str(inputs / "build.py"),
                task,
            ],
            check=False,
            cwd=inputs,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=200,
            preexec_fn=restrict,
        )
        if proc.returncode:
            raise ValueError(
                "Build failed: " + proc.stderr.decode(errors="replace")[-1000:]
            )
        import io

        with np.load(
            io.BytesIO(read_regular(out / "artifact.npz", 55 * 1024**2)),
            allow_pickle=False,
        ) as built:
            return dict(built)


def main() -> None:
    cfg = json.loads((PRIVATE / "condition.json").read_text())
    task, key = cfg["task"], cfg["target"]
    OUTPUT.mkdir(exist_ok=True, parents=True)
    # Keep private assets and scores inaccessible to candidate Python, including after collection.
    TESTS.chmod(0o700)
    OUTPUT.chmod(0o700)
    try:
        source = read_regular(WORK / "submission.py", 2 * 1024**2)
        sha = hashlib.sha256(source).hexdigest()
        artifact = worker(source, task)
    except (ValueError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        report = {"build": "failed", "reason": str(exc), "reward": 0.0}
    else:
        if task == "inspection":
            from inspection_eval import reward, score_edits

            measured = score_edits(artifact)
            metrics = {k: reward(measured, i)["reward"] for i, k in enumerate("ab")}
        else:
            from geometry_eval import GeometryEvaluator, checked_labeled

            mesh = tuple(
                artifact[n] for n in ("vertices", "faces", "colors", "face_ids")
            )
            try:
                mesh = checked_labeled(mesh)
            except (ValueError, TypeError, IndexError) as exc:
                (OUTPUT / "metrics.json").write_text(
                    json.dumps({"build": "invalid", "reason": str(exc), "reward": 0.0})
                )
                (OUTPUT / "reward.txt").write_text("0.0\n")
                return
            evaluator = GeometryEvaluator()
            try:
                measured = {k: evaluator.score_mesh(mesh, k) for k in "ab"}
            finally:
                evaluator.close()
            metrics = {k: measured[k]["macro"]["depth_f1_3cm"] for k in "ab"}
        receipt = {}
        try:
            receipt = json.loads(read_regular(WORK / "test_receipt.json", 65536))
        except (FileNotFoundError, ValueError):
            pass
        report = {
            "build": "valid",
            "source_sha256": sha,
            "test_receipt_matches": receipt.get("source_sha256") == sha,
            "target_rewards": metrics,
            "reward": float(metrics[key]),
            "measured": measured,
        }
        np.savez_compressed(OUTPUT / "artifact.npz", **artifact)
        (OUTPUT / "submitted.py").write_bytes(source)
    (OUTPUT / "metrics.json").write_text(json.dumps(report, allow_nan=False))
    (OUTPUT / "reward.txt").write_text(f"{report['reward']:.9f}\n")


if __name__ == "__main__":
    main()
