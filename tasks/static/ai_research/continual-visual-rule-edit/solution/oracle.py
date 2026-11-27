"""Build a candidate-compatible editor from a public three-field handover."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from read_handover import read


@dataclass(frozen=True)
class OracleContext:
    """Locations of the public scanner work area and public-input numerical editor."""

    work: Path
    editor_source: Path


def oracle(context: OracleContext) -> None:
    """Write and smoke-test the editor for the photograph in the public workspace.

    Args:
        context: Public image, staging calibration, and the location of the
            calibrated NumPy editor. Requires the candidate's
            documented photo layout and stage numbers.

    The source embeds only choices inferred from the supplied image. A missing
    image leaves the scanners unmodified. A public smoke failure propagates.
    """
    image = context.work / "observation.png"
    if image.is_file():
        with np.load(context.work / "calibration.npz", allow_pickle=False) as raw:
            tags = raw["tags"][0]
        fields, rules, _ = read(image, tags[tags[:, 67] == 0])
        stations = (17, 23, 42, 58, 71, 86)
        plans = {
            site: (int(pair[0]), int(pair[1]), recipe.tolist())
            for site, pair, recipe in zip(stations, fields, rules, strict=True)
        }
        template = context.editor_source.read_text()
        marker = "HANDOVER = {}"
        if template.count(marker) != 1:
            raise ValueError("The numerical editor requires a single blank handover")
        program = template.replace(marker, "HANDOVER = " + repr(plans))
    else:
        program = "def edit(W,b,old_readout,patches,tags,bridge):\n    return W,b,old_readout,bridge\n"
    (context.work / "submission.py").write_text(program)
    subprocess.run(["./python", "smoke.py"], cwd=context.work, check=True)


if __name__ == "__main__":
    oracle(OracleContext(Path("/app/work"), Path(__file__).with_name("reference.py")))
