"""Check clean public RGB access, scratch extraction and failures on undeclared authoring files."""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

PUBLIC = Path(__file__).resolve().parents[1] / "environment/public"
sys.path.insert(0, str(PUBLIC))
from clean_rebuild import run_clean


def run_checks(public, launch=run_clean):
    manifest = json.loads((public / "public-inputs.json").read_text())
    inputs = manifest["required"] + [name for name in manifest["optical"] if (public / name).is_file()]
    with tempfile.TemporaryDirectory() as folder, tempfile.NamedTemporaryFile() as old:
        work = Path(folder)
        for name in (*inputs, "smoke.py"):
            shutil.copyfile(public / name, work / name)
        (work / "development.helper").write_text("author workspace")
        source = work / "submission.py"
        code = """
from pathlib import Path
from zipfile import ZipFile
import numpy as np
from PIL import Image


def scene():
    media = Path("/app/work/observation.png")
    pixels = []
    for path in (media, Path("observation.png"), Path(__file__).with_name("observation.png")):
        with Image.open(path) as image:
            pixels.append(image.getpixel((20, 20)))
    assert pixels[0] == pixels[1] == pixels[2]
    with ZipFile("frames.zip") as archive:
        archive.extract("0000.png", "decoded")
    assert Path("/app/work/decoded/0000.png").is_file()
    Path("/tmp/clean-scratch.txt").write_text("scratch")
    return (np.eye(3), np.array([[0, 1, 2]]), np.asarray(pixels), np.array([1]), np.array([1]))
"""
        source.write_text(code)
        launch(work, inputs)
        assert (
            json.loads((work / "test_receipt.json").read_text())["details"]["triangles"]
            == 1
        )
        for dependency in (
            "development.helper",
            "/app/work/development.helper",
            old.name,
        ):
            source.write_text(code + f"\nPath({dependency!r}).read_bytes()\n")
            try:
                launch(work, inputs)
            except RuntimeError:
                pass
            else:
                raise AssertionError(f"Clean source unexpectedly read {dependency}")
            assert not (work / "test_receipt.json").exists()
        assert (work / "development.helper").read_text() == "author workspace"
        assert Path(old.name).is_file()
    print(
        "Verified canonical RGB, writable extraction, and three missing undeclared dependencies."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, default=PUBLIC)
    run_checks(parser.parse_args().public)
