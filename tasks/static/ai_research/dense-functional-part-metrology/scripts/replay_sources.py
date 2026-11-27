"""Rebuild fixed submitted programs under three image conditions and compare their actual numeric meshes."""

import argparse
import hashlib
import importlib.util
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def digest(contents):
    return hashlib.sha256(contents).hexdigest()


def bind(args, path, target):
    args.extend(("--ro-bind", str(path), target))


def isolated_build(config, runtime, source, names):
    """Run scene() offline with read-only observations and disposable /app/work and /tmp."""
    with tempfile.TemporaryDirectory() as folder:
        scratch = Path(folder)
        output = scratch / "output"
        output.mkdir()
        # Production writes one readiness byte before importing the candidate. A local
        # replay can discard this notification while preserving the same bootstrap.
        launcher = scratch / "build.py"
        launcher.write_text(
            "import os\n"
            "import runpy\n"
            "os.environ['MESH_READY'] = str(os.open('/dev/null', os.O_WRONLY))\n"
            "runpy.run_path('/checks/worker_bootstrap.py', run_name='__main__')\n"
        )
        args = [
            str(config.bwrap),
            "--unshare-all",
            "--die-with-parent",
            "--new-session",
            "--clearenv",
            "--setenv",
            "PATH",
            "/venv/bin:/usr/bin:/bin",
            "--setenv",
            "HOME",
            "/tmp",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--setenv",
            "OPENBLAS_NUM_THREADS",
            "1",
            "--setenv",
            "OMP_NUM_THREADS",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONHASHSEED",
            "0",
        ]
        for path in ("/usr", "/lib", "/lib64", "/bin", "/etc/alternatives"):
            if Path(path).exists():
                bind(args, path, path)
        bind(args, config.venv.resolve(), "/venv")
        if config.pillow_root:
            bind(args, config.pillow_root.resolve(), "/pillow")
            args.extend(("--setenv", "PYTHONPATH", "/pillow"))
        args.extend(
            (
                "--dev",
                "/dev",
                "--proc",
                "/proc",
                "--tmpfs",
                "/tmp",
                "--tmpfs",
                "/app/work",
            )
        )
        for path in (runtime / "tests/private/public-observations").iterdir():
            bind(args, path.resolve(), "/app/work/" + path.name)
        bind(args, source.resolve(), "/app/work/submission.py")
        bind(args, launcher, "/checks/build.py")
        bind(
            args,
            (runtime / "tests/worker_bootstrap.py").resolve(),
            "/checks/worker_bootstrap.py",
        )
        args.extend(
            (
                "--setenv",
                "MESH_ARTIFACT",
                "/output/artifact.npz",
                "--setenv",
                "MESH_FIELDS",
                json.dumps(names),
            )
        )
        args.extend(
            (
                "--bind",
                str(output),
                "/output",
                "--chdir",
                "/app/work",
                "/venv/bin/python",
                "-B",
                "/checks/build.py",
            )
        )
        # Bound logs independently of candidate output. Only the stdout pipe from the submitted source is discarded.
        with tempfile.TemporaryFile() as error:
            process = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=error, start_new_session=True
            )
            try:
                timed_out = False
                try:
                    code = process.wait(timeout=640)
                except subprocess.TimeoutExpired:
                    timed_out, code = True, None
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=10)
            if timed_out:
                return None, "elapsed-time limit"
            if code:
                error.seek(max(0, error.seek(0, os.SEEK_END) - 1500))
                return None, error.read(1500).decode(errors="replace")
        artifact = output / "artifact.npz"
        try:
            fd = os.open(artifact, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError as exc:
            return None, f"No regular output artifact ({exc.errno})"
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 5 * 1024**2:
                return None, "invalid numerical artifact size or type"
            return stream.read(5 * 1024**2 + 1), None


def unordered_triangles(mesh):
    """Hash triangle coordinates at micrometer resolution, allowing reordered and oppositely wound faces."""
    triangles = np.rint(mesh["vertices"][mesh["faces"]].astype(float) * 1e6).astype(
        "<i8"
    )
    order = np.lexsort(
        (triangles[:, :, 2], triangles[:, :, 1], triangles[:, :, 0]), axis=1
    )
    geometry = np.take_along_axis(triangles, order[:, :, None], axis=1).reshape(-1, 9)
    records = np.column_stack((geometry, mesh["face_ids"], mesh["part_ids"])).astype(
        "<i8"
    )
    order = np.lexsort(records.T[::-1])
    return digest(records[order].tobytes())


def describe(arrays, baseline):
    """Compare exact shape, topology and labels, and report color/position changes when correspondence exists."""
    same = {k: bool(np.array_equal(v, baseline[k])) for k, v in arrays.items()}
    out = {
        "identical_arrays": same,
        "vertices": len(arrays["vertices"]),
        "triangles": len(arrays["faces"]),
    }
    out["same_labeled_triangles_at_micrometer_resolution"] = unordered_triangles(
        arrays
    ) == unordered_triangles(baseline)
    if not same["vertices"]:
        a = np.asarray(arrays["vertices"], dtype=float)
        b = np.asarray(baseline["vertices"], dtype=float)
        out["mean_symmetric_nearest_vertex_distance_m"] = float(
            (cKDTree(a).query(b)[0].mean() + cKDTree(b).query(a)[0].mean()) / 2
        )
    if arrays["vertices"].shape == baseline["vertices"].shape and same["faces"]:
        out["vertex_rmse_m"] = float(
            np.sqrt(
                np.mean((arrays["vertices"].astype(float) - baseline["vertices"]) ** 2)
            )
        )
        out["mean_absolute_srgb_change"] = float(
            np.mean(np.abs(arrays["colors"].astype(float) - baseline["colors"]))
        )
    return out


def run(config):
    runtimes = {k: getattr(config, k) for k in ("correct", "swapped", "none")}
    tests = runtimes["correct"] / "tests"
    spec = importlib.util.spec_from_file_location(
        "bounded_replay_verifier", tests / "verify.py"
    )
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    for module in ("functional-parts", "dense-functional-parts"):
        sys.path.insert(0, str(tests / "private" / module))
    from score import score
    from whole_scene import scene_metrics

    runs = []
    for metadata in sorted((config.results / "correct").glob("*/trial.json")):
        meta = json.loads(metadata.read_text())
        if (meta.get("agent"), meta.get("model"), meta.get("reasoning_effort")) != (
            "codex",
            "openai/gpt-6.2-sol",
            "xhigh",
        ):
            continue
        if (
            meta.get("experiment_id") != config.experiment
            or meta.get("task_version") != config.version
        ):
            continue
        source = metadata.parent / "submission.py"
        official = json.loads((metadata.parent / "metrics.json").read_text())
        receipt = json.loads((metadata.parent / "test_receipt.json").read_text())
        sha = digest(source.read_bytes())
        if not (
            official.get("build") == "valid"
            and official.get("test_receipt_matches")
            and sha == receipt.get("source_sha256") == official.get("source_sha256")
        ):
            raise ValueError(
                f"Archive lacks a valid independently tested source: {meta['id']}"
            )
        runs.append((meta, source, official))
    if len(runs) != 3:
        raise ValueError(f"Expected three completed matching trials, found {len(runs)}")
    result = {
        "experiment": config.experiment,
        "version": config.version,
        "model": "openai/gpt-6.2-sol",
        "reasoning_effort": "xhigh",
        "trials": {},
    }
    for meta, source, official in runs:
        baseline = None
        hosted = verifier.bounded_arrays(
            (source.parent / "artifact.npz").read_bytes(), verifier.NAMES
        )
        report = {
            "source_sha256": digest(source.read_bytes()),
            "official_reward": meta["reward"],
            "conditions": {},
        }
        for arm, runtime in [
            ("correct", runtimes["correct"]),
            ("matched_repeat", runtimes["correct"]),
            ("swapped", runtimes["swapped"]),
            ("none", runtimes["none"]),
        ]:
            blob, error = isolated_build(config, runtime, source, verifier.NAMES)
            if error:
                report["conditions"][arm] = {"build": "failed", "error": error}
                continue
            try:
                arrays = verifier.bounded_arrays(blob, verifier.NAMES)
            except verifier.CandidateError as exc:
                report["conditions"][arm] = {"build": "invalid", "error": str(exc)}
                continue
            mesh = tuple(arrays[k] for k in verifier.NAMES)
            parts = score(mesh)
            scene = scene_metrics(mesh)
            measured = {
                "build": "valid",
                "part_accuracy": parts["part_success"],
                "parent_depth_f1": parts["object_depth_f1"],
                "workspace_rgbd": scene["rgbd_5cm_10percent_coverage"],
                "depth_coverage": scene["depth_5cm_coverage"],
            }
            measured["reward"] = min(
                measured["part_accuracy"],
                measured["parent_depth_f1"],
                measured["workspace_rgbd"],
            )
            if arm == "correct":
                baseline = arrays
                measured["compared_to_hosted"] = describe(arrays, hosted)
            if baseline is not None:
                measured["compared_to_local_matched"] = describe(arrays, baseline)
            report["conditions"][arm] = measured
        result["trials"][meta["id"]] = report
        config.output.parent.mkdir(parents=True, exist_ok=True)
        config.output.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("correct", "swapped", "none", "results", "output", "bwrap", "venv"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--pillow-root", type=Path)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--version", required=True, type=int)
    run(parser.parse_args())
