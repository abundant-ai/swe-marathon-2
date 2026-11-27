"""Assemble chart-conditioned stockroom tasks from the verified stock-commissioning runtime."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
from prepare import prepare
from renewal import photograph
from site_photos import cards, exposure, sheet

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
NAME = "swe-m2_ai-research_core50-shared-scanner-stockrooms"


def practice_data(public: Path) -> None:
    """Create labeled public rehearsal frames and independent example cards for both rooms."""
    deck = cards(51509)
    sheet(deck).save(public / "practice-cards.png")
    replacements = cards(28734)
    rng = np.random.default_rng(219)
    with np.load(public / "development.npz") as data:
        images, labels, ids = data["x"], data["y"], data["ids"]
    payload = {"renewal": photograph(deck, replacements, np.array([1, 0]))}
    for visit in range(3):
        session = np.unique(ids[:, 0])[visit % 2]
        indices = (
            np.flatnonzero(ids[:, 0] == session).reshape(10, 4, 8)[:, visit].ravel()
        )
        x = images[indices]
        y = labels[indices]
        cams = [
            np.array([[0.07, 0.03, 0.8], [0.04, 0.69, 0.07], [0.61, 0.03, 0.06]]),
            np.array([[0.08, 0.67, 0.04], [0.03, 0.05, 0.59], [0.71, 0.06, 0.04]]),
        ]
        payload[f"x{visit}"] = np.stack(
            [np.rint(x @ cams[h].T).clip(0, 255).astype(np.uint8) for h in (0, 1)]
        )
        for site in (0, 1):
            payload[f"y{visit}_site{site}"] = (y + (3, 7)[site]) % 10
            for h in (0, 1):
                payload[f"chart{visit}_{h}_{site}"] = exposure(
                    replacements[site], cams[h], rng
                )
    np.savez_compressed(public / "practice-handover.npz", **payload)


def stage(parent: Path, destination: Path) -> None:
    """Create three atomic packages with identical stock and optical evidence and one intervened chart sheet."""
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    (matched,) = parent.glob("*-correct")
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        matrix = Path(tmp) / "matrix"
        for arm in ("correct", "swapped", "none"):
            name = NAME + "-" + arm
            root = matrix / name
            root.mkdir(parents=True)
            for folder in ("tests", "solution", "environment"):
                shutil.copytree(
                    matched / folder,
                    root / folder,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            config = (
                (matched / "task.toml")
                .read_text()
                .split("[metadata.task_rating]")[0]
                .replace(matched.name, name)
            )
            config = config.replace(
                "Train a source CNN and adapt its weights while recognizing household objects from an unlabeled camera stream.",
                "Commission a shared scanner using visual handovers and preserve conflicting stockroom mappings in CNN weights.",
            )
            (root / "task.toml").write_text(config)
            shutil.copy2(HERE / "instruction.md", root / "instruction.md")
            public, private, solution = (
                root / "environment/public",
                root / "tests/private",
                root / "solution",
            )
            prepare(private, public, arm)
            practice_data(public)
            shutil.copy2(HERE / "practice.py", public / "practice.py")
            tests = root / "tests"
            stream = tests / "test_stream.py"
            stream.rename(tests / "stream_common.py")
            shutil.copy2(HERE / "site_stream.py", stream)
            shutil.copy2(HERE / "crossed_grade.py", tests / "crossed_grade.py")
            grader = tests / "verify.py"
            old = grader.read_text()
            key = '    return min(row["credit"] for row in summary.values()), summary'
            if old.count(key) != 1:
                raise ValueError("Wrong stock verifier revision")
            grader.write_text(
                old.replace(
                    key,
                    "    from crossed_grade import crossed_credit\n    return crossed_credit(results, summary)",
                )
            )
            source = grader.read_text().replace(
                '    "deployment_b",\n)',
                '    "deployment_b",\n    "paired_stock_ids",\n)',
            )
            anchor = "    if set(checks) != set(REQUIREMENTS)"
            addition = (
                "    from test_requirements import MeasurementContext, assess\n"
                "    checks = assess(MeasurementContext(checks, evidence))\n"
            )
            if anchor not in source or '"paired_stock_ids",\n)' not in source:
                raise ValueError("Unknown check registry")
            source = source.replace(anchor, addition + anchor)
            source = source.replace(
                "def deployment_credit(",
                "from crossed_grade import commissioning_credit as deployment_credit\n\ndef single_installation_credit(",
            )
            source = source.replace(
                '        if tag in fixed:\n            components["weight_contribution"]',
                '        if weights:\n            components["weight_contribution"]',
            )
            source = source.replace(
                'and complete["a"] else 0.0', "and all(complete.values()) else 0.0"
            )
            source = source.replace(
                'evidence["reward"] >= 1 - 1e-12,',
                'evidence["reward"] >= 1 - 1e-12 and all(c.status == "passed" for c in checks.values()),',
            )
            source = (
                source.replace("test_online", "measure_online")
                .replace("    test_training,", "    measure_training,")
                .replace("training = test_training(", "training = measure_training(")
            )
            grader.write_text(source)
            shutil.copy2(HERE / "test_requirements.py", tests / "test_requirements.py")
            stream.write_text(
                stream.read_text().replace("def test_online(", "def measure_online(")
            )

            setup = tests / "test.sh"
            setup.write_text(
                setup.read_text().replace(
                    "cd /tests",
                    "rm -f /logs/verifier/reward.txt /logs/verifier/metrics.json\ncd /tests",
                    1,
                )
            )
            execution = tests / "execution.py"
            execution.write_text(
                execution.read_text().replace(
                    '        cmd = [*command, sys.executable, "-IB", str(public / "worker.py")]',
                    '        cmd = [*command, "prlimit", "--as=3221225472", "--nproc=48", "--", sys.executable, "-IB", str(public / "worker.py")]',
                )
            )
            training = tests / "training_replay.py"
            training.write_text(
                training.read_text().replace(
                    '"--nofile=128",',
                    '"--nofile=128", "--as=3221225472", "--nproc=48",',
                )
            )
            shutil.copy2(HERE / "label_replay.py", tests / "label_replay.py")
            evidence = tests / "test_training.py"
            evidence.write_text(
                evidence.read_text()
                .replace(
                    'minimum = floor - settings["source_floor_margin"]',
                    'minimum = settings["paired_source_minimum"]',
                )
                .replace(
                    "Balanced source accuracy after independently renumbering the training categories",
                    "Balanced paired accuracy on changed sensor-specific source assignments",
                )
            )
            evidence.write_text(
                evidence.read_text()
                .replace(
                    '"source_floor_margin" in settings',
                    '"paired_source_minimum" in settings',
                )
                .replace(
                    '"source_floor_margin" not in settings',
                    '"paired_source_minimum" not in settings',
                )
            )
            (private / "label-replay.json").write_text(
                json.dumps({"seed": 7129, "paired_source_minimum": 0.15}) + "\n"
            )
            evidence.write_text(
                evidence.read_text().replace(
                    "def test_training(", "def measure_training("
                )
            )
            docker = tests / "Dockerfile"
            docker.write_text(
                docker.read_text().replace(
                    "test_stream.py test_training.py",
                    "test_stream.py stream_common.py crossed_grade.py test_requirements.py test_training.py",
                )
            )
            # The worker imports only the single submitted program and the declared CNN API.
            decoder = (HERE / "decoder.py").read_text()
            (solution / "online.py").write_text(
                decoder
                + "\n"
                + (HERE / "updater.py")
                .read_text()
                .replace("from decoder import decode", "")
            )
            shutil.copy2(HERE / "oracle.py", solution / "oracle.py")
            manifest = {
                f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                for f in private.iterdir()
                if f.name != "inventory.json"
            }
            (private / "inventory.json").write_text(
                json.dumps(manifest, sort_keys=True) + "\n"
            )
        matrix.rename(destination)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("parent", type=Path)
    p.add_argument("destination", type=Path)
    a = p.parse_args()
    stage(a.parent, a.destination)
