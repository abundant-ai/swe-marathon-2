"""Add the stock-output head, photographic manifest, and stock-aware reference to a camera task."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def install_inventory(root: Path, data: Path, arm: str) -> None:
    """Install the stock-specific runtime and pin its protocol fixtures in the staged release."""
    shutil.copy2(HERE / "README.md", root / "README.md")
    shutil.copytree(HERE / "reviews", root / "reviews")
    shutil.copy2(HERE / "check_scoring.py", root / "check_scoring.py")
    if arm == "correct":
        shutil.copy2(HERE / "task.toml", root / "task.toml")
    public = root / "environment/public"
    for folder in (public, root / "tests/public"):
        with (folder / "core_model.py").open("a") as out:
            out.write("\n\n" + (HERE / "model.py").read_text())
    if arm != "none":
        shutil.copy2(
            data / f"inventory_{'a' if arm == 'correct' else 'b'}.png",
            public / "inventory.png",
        )
    (root / "tests/private/label-replay.json").write_text(
        '{"seed":7129,"source_floor_margin":0.15}\n'
    )
    (root / "tests/private/stock-service.json").write_text(
        '{"protocol":"two-stations"}\n'
    )
    solution = root / "solution"
    (solution / "oracle.py").rename(solution / "camera_oracle.py")
    for name in ("gallery.py", "oracle.py"):
        shutil.copy2(HERE / name, solution / name)
    with (solution / "online.py").open("a") as out:
        out.write("\n\n" + (HERE / "updater.py").read_text())
    private = root / "tests/private"
    inventory = private / "inventory.json"
    files = json.loads(inventory.read_text())
    for path in sorted(private.glob("*.json")):
        if path != inventory:
            files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    inventory.write_text(json.dumps(files, sort_keys=True) + "\n")
