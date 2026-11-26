"""Check selector-free numerical bounds, fresh results and candidate/infrastructure outcomes in scratch."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import numpy as np
import verify as verifier
from verify import CandidateError


def blob(d):
    stream = io.BytesIO()
    np.savez_compressed(stream, **d)
    return stream.getvalue()


def numerical():
    valid = {
        "vertices": np.array([[0.0, 0.0, 1.0], [0.2, 0.0, 1.0], [0.0, 0.2, 1.0]]),
        "faces": np.array([[0, 1, 2]]),
        "colors": np.zeros((3, 3), np.uint8),
        "face_ids": np.zeros(1, int),
        "part_ids": np.zeros(1, int),
    }
    features = []
    data = verifier.bounded_arrays(blob(valid), verifier.NAMES)
    assert data["faces"].shape == (1, 3)
    for name, overrides in [
        ("extra array", {"unused": np.zeros(1)}),
        ("invalid shape", {"vertices": np.zeros((60001, 3))}),
        ("object dtype", {"colors": np.array([[None] * 3] * 3, dtype=object)}),
        ("label length", {"face_ids": np.array([0, 0])}),
    ]:
        test = blob({**valid, **overrides})
        with patch.object(
            np,
            "load",
            side_effect=AssertionError("allocation before header validation"),
        ):
            try:
                verifier.bounded_arrays(test, verifier.NAMES)
            except CandidateError:
                features.append(name)
            else:
                raise AssertionError(name)
    for name, overrides in [
        ("mesh index", {"faces": np.array([[0, 1, 5]])}),
        ("label relationship", {"part_ids": np.array([8])}),
        ("nonfinite vertex", {"vertices": np.full((3, 3), np.nan)}),
    ]:
        try:
            verifier.bounded_arrays(blob({**valid, **overrides}), verifier.NAMES)
        except CandidateError:
            features.append(name)
        else:
            raise AssertionError(name)
    return features


def main(bundle):
    checks = numerical()
    # Only the new session created below receives a signal in this local check.
    # The full dedicated-UID path runs inside the packaged verifier.
    with tempfile.TemporaryDirectory() as d:
        pidfile = Path(d) / "child.pid"
        cmd = [
            sys.executable,
            "-c",
            (
                "import subprocess,sys,time; from pathlib import Path; "
                'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); '
                "Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)"
            ),
            str(pidfile),
        ]
        parent = subprocess.Popen(cmd, start_new_session=True)
        try:
            for _ in range(100):
                if pidfile.is_file() and pidfile.read_text().isdecimal():
                    break
                time.sleep(0.01)
            child = int(pidfile.read_text())
            assert os.getpgid(child) == parent.pid
            verifier.clean_processes(parent.pid, 2**31 - 1)
            assert parent.wait(timeout=2) == -signal.SIGKILL
            status = Path("/proc") / str(child) / "status"
            # SIGKILL can be pending until the child is next scheduled.
            for _ in range(200):
                try:
                    state = status.read_text().splitlines()
                except FileNotFoundError:
                    break
                if any(line.startswith("State:") and "Z" in line for line in state):
                    break
                time.sleep(0.01)
            else:
                raise AssertionError("Worker group child remained alive")
            checks.append("worker process group and ordinary child stopped")
        finally:
            if parent.poll() is None:
                os.killpg(parent.pid, signal.SIGKILL)
                parent.wait(timeout=2)
    with tempfile.TemporaryDirectory() as first:
        p = Path(first)
        tests = p / "tests"
        tests.mkdir()
        private = tests / "private"
        private.mkdir()
        work = p / "public"
        work.mkdir()
        output = p / "logs"
        output.mkdir()
        # Module loading uses only the packaged evaluator modules for these control-flow checks.
        for n in (
            "dense-telephone-parts",
            "functional-parts",
            "dense-functional-parts",
            "precision-pilot",
            "field-pilot",
        ):
            src = bundle / "tests/private" / n
            if src.is_dir():
                (private / n).symlink_to(src.resolve(), target_is_directory=True)
        (private / "public-observations").symlink_to(
            (bundle / "tests/private/public-observations").resolve(),
            target_is_directory=True,
        )
        shutil.copyfile(
            bundle / "tests/fixture-digests.json", tests / "fixture-digests.json"
        )
        values = {"TESTS": tests, "PRIVATE": private, "OUTPUT": output, "WORK": work}
        with patch.multiple(verifier, **values):
            for n in verifier.FRESH:
                (output / n).write_text("stale")
            verifier.main()
            assert (output / "reward.txt").read_text().strip() == "0.000000000"
            assert (
                json.loads((output / "metrics.json").read_text())["error_domain"]
                == "candidate"
            )
            assert all(
                not (output / n).exists()
                for n in ("submitted.py", "artifact.npz", "infrastructure.json")
            )
            checks.append("missing transferred source has fresh candidate zero")
            for observation in (private / "public-observations").iterdir():
                assert (
                    work / observation.name
                ).read_bytes() == observation.read_bytes()
            checks.append(
                "absolute public observation paths match the isolated working directory"
            )
            (work / "submission.py").write_text("def scene(): return ()")
            with patch.object(
                verifier,
                "rebuild",
                side_effect=RuntimeError("trusted fixture unavailable"),
            ):
                try:
                    verifier.main()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("Infrastructure exception swallowed")
            assert (
                not (output / "reward.txt").exists()
                and not (output / "metrics.json").exists()
            )
            assert (
                json.loads((output / "infrastructure.json").read_text())["error_domain"]
                == "verifier"
            )
            checks.append("unexpected infrastructure exception clears stale reward")
            try:
                verifier.regular_bytes(work / "submission.py", 2)
            except CandidateError:
                checks.append("source byte bound")
            else:
                raise AssertionError("Oversized source file accepted")
        # This scratch overlay intentionally omits a single held annotation; it
        # must invalidate the trial even when transferred source is absent.
        (private / "dense-telephone-parts").unlink()
        hidden = private / "dense-telephone-parts"
        hidden.mkdir()
        for original in (bundle / "tests/private/dense-telephone-parts").iterdir():
            if original.name != "h2.json":
                (hidden / original.name).symlink_to(original.resolve())
        with patch.multiple(verifier, **values):
            (output / "reward.txt").write_text("stale")
            try:
                verifier.main()
            except FileNotFoundError:
                pass
            else:
                raise AssertionError(
                    "Missing held-out annotations did not invalidate trial"
                )
            assert (output / "infrastructure.json").is_file()
            assert not (output / "reward.txt").exists()
            checks.append(
                "missing held-out annotation cannot shrink the score denominator"
            )
    print(json.dumps({"checks_passed": checks}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "bundle", type=Path, nargs="?", default=Path(__file__).resolve().parents[1]
    )
    cfg = p.parse_args()
    main(cfg.bundle)
