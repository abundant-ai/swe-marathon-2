"""Lists the features OpenFOAM reports about itself (boundary conditions, turbulence models,
function objects, fvOptions) and which of them no tutorial mentions.
Run inside the agent image. usage: features.py <out.json>"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SOLVERS = ["simpleFoam", "rhoSimpleFoam", "buoyantSimpleFoam", "interFoam", "chtMultiRegionFoam",
           "reactingFoam", "solidDisplacementFoam", "pimpleFoam"]
OPTIONS = ["-listScalarBCs", "-listVectorBCs", "-listSphericalTensorBCs", "-listSymmTensorBCs",
           "-listTensorBCs", "-listFunctionObjects", "-listFvOptions", "-listTurbulenceModels"]
BLOCK = re.compile(r"^([A-Za-z][\w ]*)\n(\d+)\n\(\n(.*?)\n\)", re.S | re.M)


def lists(solver, option):
    p = subprocess.run([solver, option], capture_output=True, text=True, cwd="/tmp")
    body = p.stdout.split("// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //", 1)[-1]
    return {m.group(1).strip(): m.group(3).split() for m in BLOCK.finditer(body)}


def main():
    features = defaultdict(set)
    for s in SOLVERS:
        for o in OPTIONS:
            for name, items in lists(s, o).items():
                features[name].update(items)
    words = set()
    root = os.environ["FOAM_TUTORIALS"]
    for d, _, files in os.walk(root):
        for f in files:
            try:
                words.update(re.findall(r"[\w:.<>-]+", open(os.path.join(d, f), errors="ignore").read()))
            except OSError:
                pass
    report = {}
    for name, items in sorted(features.items()):
        unused = sorted(i for i in items if i not in words)
        report[name] = {"total": len(items), "unused": unused}
        print(f"{name:32s} {len(items) - len(unused):4d} / {len(items):<4d} used by tutorials")
    json.dump(report, open(sys.argv[1], "w"), indent=1)


if __name__ == "__main__":
    main()
