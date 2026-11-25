"""Build the same runtime bundle without the steps wrapper.

Some harnesses on Oddish accept only tasks that declare no `[[steps]]`. This
writes step 1's instruction, verifier and solution at the task root, drops the
step tables from task.toml and gives the task its own name, so it is uploaded as
a separate task and never becomes a new version of the multi-step one.
Content is otherwise identical to the bundle from package_step.py. With
--keep-name the task keeps its own name: that is the bundle uploaded as the
task itself, for harnesses that run single-step tasks only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from package_step import selected_files
from task_paths import EXPERIMENT_ROOT, STEP, TASK_ROOT

NAME_SUFFIX = "-single"


def flat_task_toml(text: str, suffix: str = NAME_SUFFIX) -> str:
    """Return task.toml without step tables and with the single-step task name.

    Args:
        text: The multi-step task configuration.
        suffix: Appended to the task name; empty keeps the name.

    Returns:
        A configuration for a task with one implicit step and, unless the suffix
        is empty, a distinct name.

    Raises:
        ValueError: The step tables or the task name are not where expected.
    """
    head, _, _ = text.partition("\n[[steps]]")
    head = re.sub(r"^multi_step_reward_strategy\s*=.*\n", "", head, flags=re.MULTILINE)
    renamed, count = re.subn(
        r'^(name = "abundant/[^"]+)"',
        rf'\1{suffix}"',
        head,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("task.toml has no [task].name to rename")
    return renamed.rstrip("\n") + "\n"


def package_single_step(
    task_root: Path, destination: Path, keep_name: bool = False
) -> dict[str, Any]:
    """Stage the single-step bundle, named after its own task slug.

    Args:
        task_root: Authoring source directory with prepared inputs in place.
        destination: Local output directory; private verifier inputs are included.
        keep_name: Keep the task's own name instead of the single-step one.

    Returns:
        The staged task path, its content hash and its file count.

    Raises:
        ValueError: Inputs are unprepared or task.toml has an unexpected shape.
    """
    prefix = f"{STEP}/"
    inputs = selected_files(task_root)
    config = flat_task_toml(
        (task_root / "task.toml").read_text(encoding="utf-8"),
        "" if keep_name else NAME_SUFFIX,
    )
    slug = re.search(r'^name = "abundant/([^"]+)"', config, flags=re.MULTILINE).group(1)
    names = {(name.removeprefix(prefix)): path for name, path in inputs.items()}
    if len(names) != len(inputs):
        raise ValueError(
            "A step file would overwrite a root file in the single-step layout"
        )
    hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in names.items()
        if name != "task.toml"
    }
    hashes["task.toml"] = hashlib.sha256(config.encode()).hexdigest()
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = destination / "single-step" / digest[:12] / slug
    if staging.exists():
        shutil.rmtree(staging)
    for name, path in names.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == "task.toml":
            target.write_text(config, encoding="utf-8")
        else:
            shutil.copy2(path, target)
    (staging.parent / "BUNDLE_MANIFEST.json").write_text(
        json.dumps({"sha256": digest, "files": hashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "task_path": str(staging.resolve()),
        "content_sha256": digest,
        "files": len(names),
    }


def main() -> None:
    """Package the single-step variant and print the result as JSON.

    Raises:
        ValueError: Runtime inputs or the task configuration are invalid.
        OSError: A source cannot be read or an output cannot be written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "dist")
    parser.add_argument(
        "--keep-name", action="store_true", help="keep the task's own name"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            package_single_step(TASK_ROOT, args.output.resolve(), args.keep_name),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
