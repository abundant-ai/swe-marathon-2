"""Check selector-free numerical bounds, fresh results and candidate/infrastructure outcomes in scratch."""

from __future__ import annotations

import argparse
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path
from unittest.mock import patch

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "tests"))
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
    # A corrupt transfer must remain a candidate-domain error even when the
    # decoder raises a native Deflate exception instead of BadZipFile.
    blob_copy = blob(valid)
    with patch("zipfile.ZipFile.open", side_effect=zlib.error("corrupt transfer")):
        try:
            verifier.bounded_arrays(blob_copy, verifier.NAMES)
        except CandidateError:
            features.append("damaged compressed data has a candidate outcome")
        else:
            raise AssertionError("Compressed data failure escaped classification")
    return features


def main(bundle, artifact=None):
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
            if status.exists():
                assert any(
                    s.startswith("State:") and "Z" in s
                    for s in status.read_text().splitlines()
                )
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
        (tests / "mode.json").write_text('{"mode":"dense"}')
        (tests / "truth-contract.json").symlink_to(
            (TASK / "tests/truth-contract.json").resolve()
        )
        # Module loading uses only the packaged evaluator modules for these control-flow checks.
        for n in (
            "functional-parts",
            "dense-functional-parts",
            "precision-pilot",
            "field-pilot",
        ):
            src = bundle / "tests/private" / n
            if src.is_dir():
                (private / n).symlink_to(src.resolve(), target_is_directory=True)
        values = {"TESTS": tests, "PRIVATE": private, "OUTPUT": output, "WORK": work}
        with patch.multiple(verifier, **values):
            fixtures = private / "public-observations"
            fixtures.mkdir()
            (fixtures / "probe.txt").write_bytes(b"known input bytes")
            verifier.expose_observations()
            assert (work / "probe.txt").read_bytes() == (
                fixtures / "probe.txt"
            ).read_bytes()
            assert (work / "probe.txt").stat().st_mode & 0o222 == 0
            (work / "cache").mkdir()
            (work / "cache/frame.png").write_bytes(b"decoded pixels")
            verifier.clean_scratch({"probe.txt"})
            assert (work / "probe.txt").is_file() and not (work / "cache").exists()
            checks.append(
                "absolute workdir exposes original inputs and clears candidate extraction"
            )
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
            from score import TOP, thresholds

            for index, cutoff in enumerate(TOP):
                assert thresholds(np.nextafter(cutoff, -np.inf)) == index / len(TOP)
                assert thresholds(cutoff) == (index + 1) / len(TOP)
            checks.append("all ten silhouette cutoffs are inclusive at the boundary")

            if artifact is not None:
                geometry = verifier.bounded_arrays(
                    artifact.read_bytes(), verifier.NAMES
                )
                (work / "test_receipt.json").unlink(missing_ok=True)
                with patch.object(verifier, "rebuild", return_value=geometry):
                    verifier.main()
                metrics = json.loads((output / "metrics.json").read_text())
                terms = metrics["measured"]
                assert metrics["reward"] == min(
                    terms["part_success"],
                    terms["object_depth_f1"],
                    terms["whole_scene"]["rgbd_5cm_10percent_coverage"],
                )
                assert metrics["reward"] > 0 and metrics["build"] == "valid"
                receipt = next(
                    c
                    for c in metrics["verification"]["checks"]
                    if c["requirement_id"] == "final_test"
                )
                assert (
                    receipt["status"] == "failed"
                    and not metrics["verification"]["passed"]
                )
                checks.append(
                    "measured geometry earns its reward with a missing final-source receipt"
                )
            contract = tests / "truth-contract.json"
            expected = json.loads(contract.read_text())
            contract.unlink()
            del expected[1]["part_pixels"]["10"]
            contract.write_text(json.dumps(expected))
            try:
                verifier.main()
            except RuntimeError as exc:
                assert "coverage" in str(exc)
            else:
                raise AssertionError("Missing mandatory contour was silently excluded")
            assert not (output / "reward.txt").exists()
            checks.append(
                "missing expected contour cannot reduce the scoring denominator"
            )
            try:
                verifier.regular_bytes(work / "submission.py", 2)
            except CandidateError:
                checks.append("source byte bound")
            else:
                raise AssertionError("Oversized source file accepted")
    print(json.dumps({"checks_passed": checks}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path, nargs="?", default=TASK)
    p.add_argument(
        "--artifact",
        type=Path,
        help="A known positive mesh to exercise receipt and reward separation",
    )
    cfg = p.parse_args()
    main(cfg.bundle, cfg.artifact)
