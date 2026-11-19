"""Run the original (carve-rs), Carve's executable spec model and djot.js over many cases, locally.

The original runs once per case in a new temporary directory holding the case's files, as the
verifier runs a submission (tests/verifier/runcases.py), but without its sandbox. The spec model
and djot.js run in one Node process each (spec_model.mjs) over a batch of sources.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK_ROOT = HERE.parent
MODEL_DIR = TASK_ROOT / "experiment" / "specmodel"
ORIGINAL_DIR = TASK_ROOT / "experiment" / "original"
ENCODING = ("utf-8", "surrogateescape")
ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "NO_COLOR": "1", "TERM": "dumb"}


def local_binary() -> Path:
    """The release build of the original for this machine (scripts/setup_tools.py fetches it)."""
    for name in ("carve-macos", "carve-linux"):
        path = ORIGINAL_DIR / name
        if path.is_file() and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError("run scripts/setup_tools.py first: experiment/original holds no build of the original")


def run_case(binary: Path, case: dict, timeout: float = 20.0) -> dict:
    """One run of `binary` on a case: {"exit", "stdout"} (stdout as text, invalid UTF-8 as
    surrogate escapes), or {"exit": None, "error"}."""
    place = Path(tempfile.mkdtemp(prefix="carve-case-"))
    try:
        for name, text in case.get("files", {}).items():
            target = place / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode(*ENCODING))
        stdin = case.get("stdin")
        done = subprocess.run([str(binary), *case["argv"]], cwd=place, input=(stdin or "").encode(*ENCODING),
                              capture_output=True, timeout=timeout, env=dict(ENV, HOME=str(place), TMPDIR=str(place)))
        return {"exit": done.returncode, "stdout": done.stdout.decode(*ENCODING), "stderr": done.stderr[:2000].decode(*ENCODING)}
    except subprocess.TimeoutExpired:
        return {"exit": None, "error": "timeout"}
    finally:
        shutil.rmtree(place, ignore_errors=True)


def run_many(binary: Path, cases: list[dict], workers: int = 6) -> list[dict]:
    """run_case over `cases`, in order, `workers` at a time."""
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(lambda case: run_case(binary, case), cases))


def node_batch(requests: list[dict], djot: bool = False, timeout: float = 3600.0) -> dict[str, dict]:
    """Replies of spec_model.mjs (the spec model, or djot.js with `djot`) to requests
    {"id", "source", "safe"?}, by id. Lines are split on "\\n" only: a reply may hold U+2028."""
    if not (MODEL_DIR / "node_modules" / "ohm-js").is_dir():
        raise FileNotFoundError("run scripts/setup_tools.py first: experiment/specmodel is not set up")
    payload = "".join(json.dumps(request) + "\n" for request in requests)   # ASCII only: no character can end a line
    command = ["node", str(HERE / "spec_model.mjs"), str(MODEL_DIR)] + (["--djot"] if djot else [])
    done = subprocess.run(command, input=payload.encode("ascii"), capture_output=True, timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError(f"spec_model.mjs failed: {done.stderr[-2000:].decode(errors='replace')}")
    replies = [json.loads(line) for line in done.stdout.decode("utf-8", "surrogatepass").split("\n") if line.strip()]
    return {reply["id"]: reply for reply in replies}
