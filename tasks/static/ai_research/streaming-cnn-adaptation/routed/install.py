"""Assemble the self-contained trusted CNN module and its commissioning reference."""

from pathlib import Path
import shutil


def install(root: Path, task: Path) -> None:
    source = task / "routed"
    public, runtime = root / "environment/public", root / "tests/public"
    # A standalone core_model.py is also what the submitted trainer receives on clean replay.
    core = (task / "public/core_model.py").read_text()
    adapter = (source / "adapter.py").read_text()
    core += (
        "\n\n"
        + adapter
        + """

class ServiceClassifier(Classifier):
    def __init__(self):
        super().__init__()
        with torch.random.fork_rng(devices=[]):
            self.adapter = CameraAdapter().requires_grad_(False)

    def forward(self, image):
        return super().forward(self.adapter(image))


Classifier = ServiceClassifier
"""
    )
    for folder in (public, runtime):
        (folder / "core_model.py").write_text(core)
    shutil.copy2(source / "practice.py", public / "practice.py")
    for stem, target in (
        ("oracle", "oracle"),
        ("commission", "commission"),
        ("multifeed", "online"),
    ):
        code = (
            (source / (stem + ".py"))
            .read_text()
            .replace(
                "from adapter import camera_signature",
                "from core_model import camera_signature",
            )
        )
        (root / "solution" / (target + ".py")).write_text(code)
    (root / "tests/private/routed-protocol.json").write_text('{"modes":2}\n')
