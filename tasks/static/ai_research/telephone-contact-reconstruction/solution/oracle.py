"""Write a standalone RGB reconstruction program for the telephone desk."""

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OracleContext:
    solution: Path
    work: Path


def oracle(context: OracleContext) -> None:
    """Assemble readable geometry routines, public pixel picks and the camera rasterizer."""
    solution, work = context.solution, context.work
    modules = (
        "optics",
        "visibility",
        "room",
        "multiview",
        "stereo_bodies",
        "surfaces",
        "scene_program",
    )
    traces = {
        key: json.loads((solution / f"{key}.json").read_text())
        for key in ("i1", "i4", "input-object-contours", "public-traces")
    }
    chunks = [
        '"""Recover a metric mesh using the public telephone-desk recording."""',
        "TRACES = " + repr(traces),
        "RASTER_SOURCE = " + repr((solution / "render.c").read_text()),
    ]
    for module in modules:
        source = (solution / f"{module}.py").read_text()
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module in (
                *modules,
                "__future__",
            ):
                for index in range(node.lineno - 1, node.end_lineno):
                    lines[index] = ""
        chunks.append("\n".join(lines))
    (work / "submission.py").write_text("\n\n".join(chunks) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/app/work"))
    oracle(OracleContext(Path(__file__).resolve().parent, parser.parse_args().work))
