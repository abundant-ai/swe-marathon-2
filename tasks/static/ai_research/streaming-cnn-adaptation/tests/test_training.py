"""Execute and classify the submitted source-training and checkpoint requirements."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping
import hashlib
import json
import zipfile

import numpy as np
from core_model import load
from execution import CandidateFailure
from label_replay import measure as measure_label_replay
from test_stream import balanced, predict
from training_replay import rebuilt_checkpoint


@dataclass(frozen=True)
class CheckResult:
    requirement_id: str
    status: Literal["passed", "failed", "skipped"]
    explanation: str
    measurements: Mapping[str, float] = field(default_factory=dict)


def artifact(root, name):
    path = root / name
    if (
        not path.is_file()
        or path.is_symlink()
        or not 0 < path.stat().st_size <= 512 * 1024
    ):
        raise CandidateFailure("Missing or oversized " + name)
    return path


def validated_checkpoint(path):
    try:
        if path.is_symlink() or path.stat().st_size > 512 * 1024:
            raise ValueError("Source checkpoint exceeds its size limit")
        with zipfile.ZipFile(path) as z:
            if (
                len(z.infolist()) > 64
                or sum(v.file_size for v in z.infolist()) > 512 * 1024
            ):
                raise ValueError("Invalid checkpoint archive")
        load(path)
    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        EOFError,
        zipfile.BadZipFile,
    ) as exc:
        raise CandidateFailure("Invalid trained.npz: " + str(exc)) from exc


def signature(path):
    model = load(path)
    digest = hashlib.sha256()
    for key, val in model.state_dict().items():
        digest.update(key.encode())
        digest.update(val.numpy().tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class TrainingContext:
    work: Path
    data: Path
    public: Path
    source_x: np.ndarray
    source_y: np.ndarray
    floor: float


@dataclass
class TrainingEvidence:
    own: Path | None
    rebuilt: bool
    eligible: bool
    checks: dict[str, CheckResult]
    report: dict


def test_training(context: TrainingContext) -> TrainingEvidence:
    """Run independent submitted, rebuilt and relabeled training checks on disjoint source probes."""
    data, public, work = context.data, context.public, context.work
    source_x, source_y, floor = context.source_x, context.source_y, context.floor
    checks: dict[str, CheckResult] = {}
    report = {}
    own = None
    predictions = {}
    try:
        submitted = artifact(work, "trained.npz")
        validated_checkpoint(submitted)
        predictions["submitted"] = predict(load(submitted), source_x)
        report["source_state_sha256"] = signature(submitted)
        own = submitted
        checks["submitted_checkpoint"] = CheckResult(
            "submitted_checkpoint",
            "passed",
            "Loaded the fixed CNN and measured held-out predictions",
        )
    except CandidateFailure as exc:
        checks["submitted_checkpoint"] = CheckResult(
            "submitted_checkpoint", "failed", str(exc)
        )

    try:
        trainer = artifact(work, "train.py")
        report["training_sha256"] = hashlib.sha256(trainer.read_bytes()).hexdigest()
        with rebuilt_checkpoint(trainer, data / "source.npz", public) as fresh:
            validated_checkpoint(fresh)
            predictions["rebuilt"] = predict(load(fresh), source_x)
            rebuilt_signature = signature(fresh)
        checks["source_training"] = CheckResult(
            "source_training",
            "passed",
            "Rebuilt and measured a fresh source checkpoint",
        )
    except CandidateFailure as exc:
        checks["source_training"] = CheckResult("source_training", "failed", str(exc))

    follows_labels = True
    audit = data / "label-replay.json"
    if audit.exists():
        settings = json.loads(audit.read_text())
        try:
            trainer = artifact(work, "train.py")
            accuracy = measure_label_replay(
                trainer,
                data / "source.npz",
                public,
                source_x,
                source_y,
                settings["seed"],
                validated_checkpoint,
            )
            if "source_floor_margin" in settings:
                minimum = floor - settings["source_floor_margin"]
                follows_labels = accuracy + 1e-12 >= minimum
                report["relabeled_source_minimum"] = minimum
                status = "passed" if follows_labels else "failed"
            else:
                status = "passed"
            report["relabeled_source_accuracy"] = accuracy
            checks["source_label_dependence"] = CheckResult(
                "source_label_dependence",
                status,
                "Balanced source accuracy after independently renumbering the training categories",
                {"accuracy": accuracy},
            )
        except CandidateFailure as exc:
            follows_labels = "source_floor_margin" not in settings
            checks["source_label_dependence"] = CheckResult(
                "source_label_dependence", "failed", str(exc)
            )
    else:
        checks["source_label_dependence"] = CheckResult(
            "source_label_dependence",
            "skipped",
            "This release has no relabeling protocol",
        )

    if len(predictions) == 2:
        submitted_accuracy = balanced(predictions["submitted"], source_y)
        rebuilt_accuracy = balanced(predictions["rebuilt"], source_y)
        agreement = float(np.mean(predictions["submitted"] == predictions["rebuilt"]))
        reproducible = (
            agreement >= 0.8
            and abs(submitted_accuracy - rebuilt_accuracy) <= 0.05 + 1e-12
        )
        competent = min(submitted_accuracy, rebuilt_accuracy) + 1e-12 >= floor
        report["training_replay"] = dict(
            submitted_accuracy=submitted_accuracy,
            rebuilt_accuracy=rebuilt_accuracy,
            prediction_agreement=agreement,
            matching_tensors=report["source_state_sha256"] == rebuilt_signature,
            passed=reproducible,
        )
        checks["reproducibility"] = CheckResult(
            "reproducibility",
            "passed" if reproducible else "failed",
            "Compared both checkpoints on the same reserved captures",
            {
                "prediction_agreement": agreement,
                "accuracy_delta": abs(submitted_accuracy - rebuilt_accuracy),
            },
        )
        checks["source_competence"] = CheckResult(
            "source_competence",
            "passed" if competent else "failed",
            "Measured balanced source accuracy against the fixed starts",
            {
                "submitted": submitted_accuracy,
                "rebuilt": rebuilt_accuracy,
                "minimum": floor,
            },
        )
    else:
        reproducible = competent = False
        for name in ("reproducibility", "source_competence"):
            checks[name] = CheckResult(
                name,
                "skipped",
                "Requires both the submitted and independently rebuilt checkpoint",
            )
    report["source_competence"] = {"minimum": floor, "passed": competent}

    return TrainingEvidence(
        own,
        "rebuilt" in predictions,
        competent and reproducible and follows_labels,
        checks,
        report,
    )
