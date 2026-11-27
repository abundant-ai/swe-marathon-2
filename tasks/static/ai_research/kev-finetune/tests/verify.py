"""Stage /app/model, score it and the released Kev-0.8B with Kev's benchmark as an unprivileged uid, and write the reward:
clip((S - S_released) / (TARGET - S_released), 0, 1), S = mean accuracy over transfer-v4 test and decision-v7 test."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

APP_MODEL = Path("/app/model")
APP_TRAIN = Path("/app/train")
APP_REPORT = Path("/app/REPORT.md")
TARGET = 1.0
GRADED = ("transfer_test", "decision_test")
TESTS = Path("/tests")
WORK = Path("/var/lib/kev-verifier")
LOGS = Path("/logs/verifier")
VENV_PYTHON = "/opt/kev/.venv/bin/python"
GRADER_UID = 10021

CHECKPOINT_FILES = {
    "adapter_config.json": 1 << 20,
    "adapter_model.safetensors": 4 << 30,
    "head.pt": 256 << 20,
}
GRADER_TIMEOUT_SEC = 5400


class CandidateError(Exception):
    """The delivered checkpoint cannot earn credit; the message says why."""


def copy_regular_file(src: Path, dst: Path, limit: int) -> None:
    try:
        before = os.lstat(src)
    except FileNotFoundError:
        raise CandidateError(f"{src} is missing") from None
    if not stat.S_ISREG(before.st_mode):
        raise CandidateError(f"{src} is not a regular file")
    fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise CandidateError(f"{src} changed while it was opened")
        if opened.st_size > limit:
            raise CandidateError(
                f"{src} is {opened.st_size} bytes, over the {limit}-byte limit"
            )
        with os.fdopen(fd, "rb", closefd=False) as reader, open(dst, "xb") as writer:
            copied = 0
            while chunk := reader.read(1 << 20):
                copied += len(chunk)
                if copied > limit:
                    raise CandidateError(f"{src} grew past the {limit}-byte limit")
                writer.write(chunk)
    finally:
        os.close(fd)


def stage_checkpoint(dst: Path) -> None:
    try:
        info = os.lstat(APP_MODEL)
    except FileNotFoundError:
        raise CandidateError("/app/model does not exist") from None
    if not stat.S_ISDIR(info.st_mode):
        raise CandidateError("/app/model is not a directory")
    dst.mkdir(parents=True)
    for name, limit in CHECKPOINT_FILES.items():
        copy_regular_file(APP_MODEL / name, dst / name, limit)


def check_records() -> None:
    try:
        report = os.lstat(APP_REPORT)
    except FileNotFoundError:
        raise CandidateError("/app/REPORT.md is missing") from None
    if not stat.S_ISREG(report.st_mode) or report.st_size == 0:
        raise CandidateError("/app/REPORT.md is not a non-empty regular file")
    try:
        train = os.lstat(APP_TRAIN)
    except FileNotFoundError:
        raise CandidateError("/app/train is missing") from None
    if not stat.S_ISDIR(train.st_mode):
        raise CandidateError("/app/train is not a directory")
    for root, dirs, files in os.walk(APP_TRAIN):
        for name in files:
            info = os.lstat(os.path.join(root, name))
            if stat.S_ISREG(info.st_mode) and info.st_size > 0:
                return
    raise CandidateError("/app/train holds no non-empty regular file")


def improvement(suites: dict) -> dict:
    score = sum(suites[n]["acc"] for n in GRADED) / len(GRADED)
    released = sum(suites[f"released_{n}"]["acc"] for n in GRADED) / len(GRADED)
    reward = min(1.0, max(0.0, (score - released) / (TARGET - released)))
    return {"score": score, "released": released, "target": TARGET, "reward": reward}


def read_report(path: Path) -> dict:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise CandidateError(f"{path.name} was not written") from None
    if not stat.S_ISREG(info.st_mode) or info.st_size > (64 << 20):
        raise CandidateError(f"{path.name} is not a usable report")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        return json.loads(handle.read())


def run_grader(model: Path, out: Path) -> subprocess.CompletedProcess:
    env = {
        "PATH": "/opt/kev/.venv/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(out / "home"),
        "HF_HOME": "/opt/hf",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    def drop() -> None:
        os.setgroups([])
        os.setgid(GRADER_UID)
        os.setuid(GRADER_UID)

    return subprocess.run(
        [VENV_PYTHON, "-I", str(TESTS / "grader.py"), str(model), str(out)],
        cwd="/opt/kev",
        env=env,
        preexec_fn=drop,
        check=False,
        capture_output=True,
        text=True,
        timeout=GRADER_TIMEOUT_SEC,
    )


def summary(report: dict) -> dict:
    clean = report["clean"]
    return {
        "n": clean["n"],
        "acc": clean["acc"],
        "brier": clean["brier"],
        "ece": clean["ece"],
        "by_task": {
            task: {"n": v["n"], "acc": v["acc"]}
            for task, v in report.get("tasks", {}).items()
        },
    }


def write_reward(reward: float, metrics: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "metrics.json").write_text(json.dumps(metrics, indent=1))
    (LOGS / "reward.txt").write_text(f"{reward:.6f}\n")
    print(
        json.dumps(
            {"reward": reward, **{k: v for k, v in metrics.items() if k != "suites"}},
            indent=1,
        )
    )


def main() -> int:
    started = time.time()
    check = subprocess.run(
        [
            VENV_PYTHON,
            "-I",
            "-c",
            "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)",
        ],
        check=False,
        capture_output=True,
        timeout=600,
    )
    if check.returncode != 0:
        print("verifier environment has no usable GPU", file=sys.stderr)
        return 1
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(mode=0o711, parents=True)
    model, out = WORK / "model", WORK / "out"
    metrics: dict = {"suites": {}}
    try:
        check_records()
        stage_checkpoint(model)
        for path in [model, *model.iterdir()]:
            os.chown(path, 0, 0)
            os.chmod(path, 0o755 if path.is_dir() else 0o644)
        out.mkdir(mode=0o700)
        (out / "home").mkdir(mode=0o700)
        for path in (out, out / "home"):
            os.chown(path, GRADER_UID, GRADER_UID)
        result = run_grader(model, out)
        (LOGS).mkdir(parents=True, exist_ok=True)
        (LOGS / "grader.log").write_text(
            result.stdout[-200_000:] + "\n--- stderr ---\n" + result.stderr[-200_000:]
        )
        if result.returncode == 3 or result.returncode < 0:
            print(
                f"verifier problem (grader exit {result.returncode}); no reward written",
                file=sys.stderr,
            )
            return 1
        if result.returncode != 0:
            raise CandidateError(
                f"Kev could not load or score the checkpoint (grader exit {result.returncode}); see grader.log"
            )
        for name in (*GRADED, *(f"released_{n}" for n in GRADED)):
            metrics["suites"][name] = summary(read_report(out / name / "report.json"))
        try:
            metrics["suites"]["transfer_dev"] = summary(
                read_report(out / "transfer_dev" / "report.json")
            )
        except (CandidateError, KeyError, ValueError):
            metrics["suites"]["transfer_dev"] = None
        metrics["improvement"] = improvement(metrics["suites"])
        reward = metrics["improvement"]["reward"]
        metrics["checkpoint"] = read_report(out / "checkpoint.json")
    except CandidateError as exc:
        reward = 0.0
        metrics["error"] = str(exc)
    except subprocess.TimeoutExpired:
        print(
            f"scoring did not finish within {GRADER_TIMEOUT_SEC} s; no reward written",
            file=sys.stderr,
        )
        return 1
    metrics["seconds"] = round(time.time() - started, 1)
    write_reward(reward, metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
