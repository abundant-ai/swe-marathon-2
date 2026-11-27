"""Adapt the public RGB reconstruction pipeline to Harbor's single submitted-source artifact."""

from __future__ import annotations

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
    """Write reproducible triangulation, surface-fitting and RGB sampling code into submission.py."""
    traces = json.loads((context.solution / "input-parts.json").read_text())
    chunks = [
        '"""Reconstruct workspace A from its calibrated real RGB views."""',
        "INPUT_TRACES = " + repr(traces),
    ]
    module_names = (
        "camera",
        "photo_fit",
        "context_geometry",
        "part_fit",
        "scene_program",
    )
    for name in module_names:
        source = (context.solution / f"{name}.py").read_text()
        lines = source.splitlines()
        for node in ast.parse(source).body:
            if isinstance(node, ast.ImportFrom) and node.module in (
                *module_names,
                "__future__",
            ):
                lines[node.lineno - 1 : node.end_lineno] = [""] * (
                    node.end_lineno - node.lineno + 1
                )
        chunks.append("\n".join(lines))
    chunks.append("def scene():\n    return reconstruct_scene(INPUT_TRACES)")
    (context.work / "submission.py").write_text("\n\n".join(chunks) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/app/work"))
    args = parser.parse_args()
    oracle(OracleContext(Path(__file__).resolve().parent, args.work))
