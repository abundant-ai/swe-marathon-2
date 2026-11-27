"""Package three identically scored tasks differing only in their optional preview."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
BASE = "swe-m2_ai-research_core50-streaming-cnn"
PRIVATE = (
    "common",
    "replicate",
    "source_probe",
    "source",
    "a_arrival",
    "a_return",
    "a_probe",
    "middle",
    "middle_probe",
    "b_arrival",
    "b_return",
    "b_probe",
)


def stage(
    data,
    dest,
    *,
    transfer=False,
    camera=False,
    routed=False,
    reacquired=False,
    inventory_site=False,
):
    reacquired = reacquired or inventory_site
    routed = routed or reacquired
    camera = camera or routed
    transfer = transfer or camera
    if dest.exists():
        raise FileExistsError(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        matrix = Path(tmp) / "matrix"
        matrix.mkdir()
        for arm in ("correct", "swapped", "none"):
            variant = "camera-" if camera else ("transfer-" if transfer else "")
            if routed:
                variant = "dual-camera-"
            if reacquired:
                variant = "reacquired-camera-"
            if inventory_site:
                variant = "stock-commissioning-"
            name = BASE + "-" + variant + arm
            root = matrix / name
            public = root / "environment/public"
            runtime = root / "tests/public"
            private = root / "tests/private"
            for d in (public, runtime, private):
                d.mkdir(parents=True)
            for file in [
                "core_model.py",
                "train.py",
                "online.py",
                "practice.py",
                "ordering.py",
            ]:
                shutil.copy2(TASK / "public" / file, public / file)
            shutil.copy2(TASK / "public/CORe50-attribution.txt", public)
            for file in ["source.npz", "development.npz", "public-splits.json"]:
                shutil.copy2(data / file, public / file)
            if arm != "none":
                shutil.copy2(
                    data / ("preview_a.png" if arm == "correct" else "preview_b.png"),
                    public / "preview.png",
                )
            shutil.copy2(TASK / "public/core_model.py", runtime)
            shutil.copy2(TASK / "public/ordering.py", runtime)
            for file in ["wire.py", "worker.py"]:
                shutil.copy2(TASK / "tests" / file, runtime)
            stems = PRIVATE
            if camera:
                stems = tuple(k for k in PRIVATE if not k.startswith("middle")) + (
                    "a_middle",
                    "a_middle_probe",
                    "b_middle",
                    "b_middle_probe",
                )
            for stem in stems:
                shutil.copy2(data / (stem + ".npz"), private)
            if transfer:
                (private / "transfer-protocol.json").write_text(
                    '{"schedules":["clips","switches"]}\n'
                )
            digests = {
                f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                for f in sorted(private.glob("*.npz"))
            }
            (private / "inventory.json").write_text(
                json.dumps(digests, sort_keys=True) + "\n"
            )
            brief = (TASK / "instruction.md").read_text()
            if transfer:
                brief += (
                    "\nThe camera service also multiplexes independent object feeds. Consecutive frames may follow one object or switch immediately to a different one. "
                    "Each feed continues in chronological order. The updater receives no feed identifier. Changes must improve recognition of separate, previously unseen object captures from that camera, including when they first appear. "
                    "Both schedules, mean improvement on fresh object clips across blocks, and mean improvement on fresh clips immediately after the camera returns all count separately. Use python practice.py --schedule switches to rehearse the multiplexed service.\n"
                )
            if routed:
                brief += "\n" + (TASK / "routed/brief.md").read_text()
                if reacquired:
                    brief = brief.replace(
                        "the same ten exposures before servicing (top) and after passing through one board (bottom)",
                        "two independently ordered sets of ten photographs, taken before servicing (top) and after servicing (bottom). Both sets show the same objects from different viewpoints",
                    )
                    brief += "\nAn additional diagnostic retrains your program after renumbering the supplied category labels and reports held-out accuracy in those new indices.\n"
            elif camera:
                brief += "\n" + (TASK / "camera/brief.md").read_text()
            if inventory_site:
                brief = (TASK / "inventory/instruction.md").read_text()
            (root / "instruction.md").write_text(brief)
            (root / "task.toml").write_text(
                (TASK / "task.toml")
                .read_text()
                .replace(BASE, name)
                .replace(
                    "timeout_sec = 2400",
                    ("timeout_sec = 7500" if reacquired else "timeout_sec = 6000")
                    if routed
                    else ("timeout_sec = 4500" if transfer else "timeout_sec = 2400"),
                )
            )
            for file in ("Dockerfile", "pyproject.toml"):
                shutil.copy2(TASK / "environment" / file, root / "environment")
            for file in (
                "Dockerfile",
                "test.sh",
                "verify.py",
                "execution.py",
                "training_replay.py",
                "label_replay.py",
                "test_stream.py",
                "test_training.py",
            ):
                shutil.copy2(TASK / "tests" / file, root / "tests")
            shutil.copytree(
                TASK / "solution",
                root / "solution",
                ignore=shutil.ignore_patterns("__pycache__"),
            )

            if camera:
                for file in ("fit.py", "online.py", "oracle.py"):
                    shutil.copy2(TASK / "camera" / file, root / "solution" / file)
            elif transfer:
                shutil.copy2(
                    TASK / "transfer/distillation.py", root / "solution/online.py"
                )

            if routed:
                import sys

                sys.path.insert(0, str(TASK / "routed"))
                from install import install

                install(root, TASK)
                if reacquired:
                    (private / "label-replay.json").write_text('{"seed": 7129}\n')
                    shutil.copy2(
                        TASK / "routed/distribution_fit.py", root / "solution/fit.py"
                    )

                if inventory_site:
                    import importlib.util

                    spec = importlib.util.spec_from_file_location(
                        "stock_package", TASK / "inventory/install.py"
                    )
                    stock_package = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(stock_package)
                    stock_package.install_inventory(root, data, arm)

        def inventory(p):
            return {
                str(f.relative_to(p)): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in p.rglob("*")
                if f.is_file()
                and f.name not in {"preview.png", "inventory.png", "task.toml"}
            }

        arms = sorted(matrix.iterdir())
        assert inventory(arms[0]) == inventory(arms[1]) == inventory(arms[2])
        for path in matrix.rglob("*"):
            if path.is_symlink() or path.name == "__pycache__" or path.suffix == ".pyc":
                raise ValueError(
                    f"Unexpected generated or linked file in package: {path}"
                )
        matrix.rename(dest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("--transfer", action="store_true")
    parser.add_argument("--camera", action="store_true")
    parser.add_argument("--routed", action="store_true")
    parser.add_argument("--reacquired", action="store_true")
    parser.add_argument("--inventory-site", action="store_true")
    args = parser.parse_args()
    stage(
        args.data,
        args.dest,
        transfer=args.transfer,
        camera=args.camera,
        routed=args.routed,
        reacquired=args.reacquired,
        inventory_site=args.inventory_site,
    )
