"""Rebuild the paired deployment and publish measurements of the fixed forward pass."""

from dataclasses import dataclass
from typing import Mapping
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, os.environ.get("PILOT_PUBLIC", "/opt/core50"))
from core_model import load
from execution import CandidateFailure
from test_stream import (
    VerificationContext as StreamContext,
    test_online,
    dataset,
    balanced,
    predict,
)
from test_training import (
    CheckResult,
    TrainingContext,
    artifact,
    signature,
    test_training,
)


def deployment_credit(results: dict, *, transfer: bool) -> tuple[float, dict]:
    """Score each stock visit order within each schedule and preserve the per-start evidence."""
    overall, summary = credit_for_runs(results, transfer=transfer)
    sample = results["common"]["a"]
    if not any(
        "paused_at_switch_accuracy" in block
        for row in sample
        for block in row.get("blocks", ())
    ):
        return overall, summary
    if "reason" in summary:
        return overall, summary
    conditions = {(r["schedule"], r["order"]) for r in sample}
    if conditions != {(s, k) for s in ("clips", "switches") for k in (4201, 7303)}:
        raise RuntimeError("Missing stock deployment order or schedule")
    for schedule, order in sorted(conditions):
        split = {
            start: {
                "a": [
                    row
                    for row in worlds["a"]
                    if (row["schedule"], row["order"]) == (schedule, order)
                ]
            }
            for start, worlds in results.items()
        }
        if any(len(worlds["a"]) != 1 for worlds in split.values()):
            raise RuntimeError("Incomplete stock deployment comparison")
        _, detail = credit_for_runs(split, transfer=transfer)
        for tag, row in detail.items():
            summary[tag].setdefault("by_schedule_and_order", {})[
                f"{schedule}-{order}"
            ] = row
            summary[tag]["credit"] = min(summary[tag]["credit"], row["credit"])
    return min(row["credit"] for row in summary.values()), summary


def credit_for_runs(results: dict, *, transfer: bool) -> tuple[float, dict]:
    """Compare learned changes on fixed starts and absolute accuracy on the submitted start."""
    fixed = ("common", "replicate")
    if any("error" in r for worlds in results.values() for r in worlds["a"]):
        return 0.0, {"reason": "incomplete target deployment"}
    anchors = {
        tag: {(r["schedule"], r["order"]): r for r in results[tag]["a"]}
        for tag in fixed
    }
    scores = {}
    for tag, worlds in results.items():
        by_schedule = {}
        weights, probes, returns, losses = [], [], [], []
        for run in worlds["a"]:
            key = (run["schedule"], run["order"])
            refs = [anchors[t][key] for t in fixed] if tag == "submitted" else [run]
            frozen = np.mean([ref["frozen"] for ref in refs])
            by_schedule.setdefault(run["schedule"], []).append(run["adapted"] - frozen)
            weights.append(run["learned_weight_gain_pp"] / 100)
            for index, block in enumerate(run["blocks"]):
                frozen_probe = np.mean(
                    [ref["blocks"][index]["probe"]["frozen"] for ref in refs]
                )
                probes.append(block["probe"]["adapted"] - frozen_probe)
                if block["block"].endswith("_return"):
                    returns.append(probes[-1])
                losses.append(run["source_before"] - block["source_accuracy_after"])
                if "source_accuracy_after_first_update" in block:
                    losses.append(
                        run["source_before"]
                        - block["source_accuracy_after_first_update"]
                    )
        components = {s: float(np.mean(v)) for s, v in by_schedule.items()}
        if tag in fixed:
            components["weight_contribution"] = float(np.mean(weights))
        if transfer:
            components["fresh_objects"] = float(np.mean(probes))
            components["return_objects"] = float(np.mean(returns))
        if any("commissioned_accuracy" in b for r in worlds["a"] for b in r["blocks"]):
            other_camera = []
            for run in worlds["a"]:
                first, second = (
                    anchors[t][(run["schedule"], run["order"])] for t in fixed
                )
                for i, block in enumerate(run["blocks"]):
                    if not block["block"].endswith("_middle"):
                        continue
                    refs = [first, second] if tag == "submitted" else [run]
                    other_camera.append(
                        block["probe"]["adapted"]
                        - np.mean([r["blocks"][i]["probe"]["frozen"] for r in refs])
                    )
            components["other_camera_probe"] = float(np.mean(other_camera))
        if any(
            "paused_at_switch_accuracy" in block
            for run in worlds["a"]
            for block in run["blocks"]
        ):
            first_arrivals = []
            arrival_probes = []
            gains_after_switch = {"middle": [], "return": []}
            for run in worlds["a"]:
                key = (run["schedule"], run["order"])
                refs = [anchors[t][key] for t in fixed] if tag == "submitted" else [run]
                arrival_probes.append(
                    run["blocks"][0]["probe"]["adapted"]
                    - np.mean([ref["blocks"][0]["probe"]["frozen"] for ref in refs])
                )
                first_arrivals.append(
                    run["first_clip_adapted"]
                    - np.mean([ref["first_clip_frozen"] for ref in refs])
                )
                for block in run["blocks"][1:]:
                    phase = block["block"].rsplit("_", 1)[-1]
                    gains_after_switch[phase].append(
                        block["adapted"] - block["paused_at_switch_accuracy"]
                    )
            components["arrival_objects"] = float(np.mean(arrival_probes))
            components["first_arrivals"] = float(np.mean(first_arrivals))
            for phase, gains in gains_after_switch.items():
                components["adaptation_after_" + phase] = float(np.mean(gains))
        penalty = max(0.0, max(losses) - 0.02)
        credit = float(np.clip((min(components.values()) - penalty) / 0.10, 0.0, 1.0))
        scores[tag] = {
            "components": components,
            "retention_penalty": penalty,
            "credit": credit,
        }
    return min(v["credit"] for v in scores.values()), scores


@dataclass(frozen=True)
class VerificationContext:
    work: Path
    data: Path
    public: Path
    transfer: bool


# Public report order. Optional label replay is explicitly skipped on earlier protocols.
REQUIREMENTS = (
    "submitted_checkpoint",
    "source_training",
    "source_label_dependence",
    "reproducibility",
    "source_competence",
    "stream_program",
    "deployment_a",
    "deployment_b",
)


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: Mapping[str, float]
    evidence: dict

    def report(self) -> dict:
        """Serialize typed checks and the detailed deployment evidence for Oddish."""
        return {
            **self.evidence,
            "passed": self.passed,
            "metrics": dict(self.metrics),
            "checks": {
                c.requirement_id: {
                    "requirement_id": c.requirement_id,
                    "status": c.status,
                    "detail": c.explanation,
                    "measurements": dict(c.measurements),
                }
                for c in self.checks
            },
        }


def finish(checks: dict[str, CheckResult], evidence: dict) -> VerificationResult:
    """Require all registered outcomes and preserve independent partial measurements."""
    if set(checks) != set(REQUIREMENTS) or any(
        k != c.requirement_id for k, c in checks.items()
    ):
        raise RuntimeError("Incomplete verifier requirement registry")
    return VerificationResult(
        evidence["reward"] >= 1 - 1e-12,
        tuple(checks[k] for k in REQUIREMENTS),
        {"reward": float(evidence["reward"])},
        evidence,
    )


def deployments(context, own):
    work, data, public, transfer = (
        context.work,
        context.data,
        context.public,
        context.transfer,
    )
    common = data / "common.npz"
    results = {}
    starts = [
        ("common", common),
        ("replicate", data / "replicate.npz"),
    ]
    if own is not None:
        starts.append(("submitted", own))
    for tag, path in starts:
        if tag == "submitted" and signature(path) == signature(common):
            results[tag] = results["common"]
            continue
        runs = {}
        for world in ("a", "b"):
            runs[world] = []
            for schedule in ("clips", "switches") if transfer else ("clips",):
                for order in (4201, 7303):
                    try:
                        row = test_online(
                            StreamContext(
                                data,
                                public,
                                work / "online.py",
                                path,
                                world,
                                order,
                                schedule,
                            )
                        )
                    except CandidateFailure as exc:
                        row = {"error": str(exc)}
                    runs[world].append({"order": order, "schedule": schedule, **row})
        results[tag] = runs

    return results


def verify(context: VerificationContext) -> VerificationResult:
    data, public, work = context.data, context.public, context.work
    inventory = json.loads((data / "inventory.json").read_text())
    for name, digest in inventory.items():
        if hashlib.sha256((data / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Deployment fixture mismatch: " + name)
    source_x, source_y = dataset(data, "source_probe")
    anchors = [data / "common.npz", data / "replicate.npz"]
    floor = min(balanced(predict(load(p), source_x), source_y) for p in anchors) - 0.05
    checks: dict[str, CheckResult] = {}
    report = {}
    report.update(
        build="invalid", reward=0.0, common_state_sha256=signature(anchors[0])
    )
    training = test_training(
        TrainingContext(work, data, public, source_x, source_y, floor)
    )
    own = training.own
    checks.update(training.checks)
    report.update(training.report)

    try:
        online = artifact(work, "online.py")
    except CandidateFailure as exc:
        checks["stream_program"] = CheckResult("stream_program", "failed", str(exc))
        for world in ("a", "b"):
            checks["deployment_" + world] = CheckResult(
                "deployment_" + world, "skipped", "Requires an online updater"
            )
        return finish(checks, report)

    checks["stream_program"] = CheckResult(
        "stream_program", "passed", "Updater supplied for isolated replay"
    )
    report["updater_sha256"] = hashlib.sha256(online.read_bytes()).hexdigest()
    runs = deployments(context, own)
    report["runs"] = runs
    complete = {}
    for world in ("a", "b"):
        measured = all(
            "error" not in row for start in runs.values() for row in start[world]
        )
        complete[world] = measured and own is not None
        detail = (
            "Measured both fixed starts and the submitted checkpoint"
            if complete[world]
            else "See available per-checkpoint runs and errors"
        )
        checks["deployment_" + world] = CheckResult(
            "deployment_" + world,
            "passed" if complete[world] else "failed",
            detail,
            {
                "complete_runs": float(
                    sum(
                        "error" not in row
                        for start in runs.values()
                        for row in start[world]
                    )
                )
            },
        )
    report["worlds_complete"] = complete
    quality, breakdown = deployment_credit(runs, transfer=context.transfer)
    report["deployment_credit"] = breakdown
    if own is not None and training.rebuilt:
        report["build"] = "valid" if all(complete.values()) else "partial"
    report["reward"] = float(quality) if training.eligible and complete["a"] else 0.0
    return finish(checks, report)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, default=Path("/app/work"))
    p.add_argument("--data", type=Path, default=HERE / "private")
    p.add_argument("--public", type=Path, default=Path("/opt/core50"))
    p.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = p.parse_args()
    torch.set_num_threads(1)
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ["metrics.json", "reward.txt"]:
        (args.output / name).unlink(missing_ok=True)
    context = VerificationContext(
        args.work,
        args.data,
        args.public,
        (args.data / "transfer-protocol.json").exists(),
    )
    report = verify(context).report()
    (args.output / "metrics.json").write_text(json.dumps(report, allow_nan=False))
    (args.output / "reward.txt").write_text(f"{report['reward']:.9f}\n")
    print(report["build"], report["reward"])


if __name__ == "__main__":
    main()
