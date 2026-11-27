#!/usr/bin/env bash
# Reference solution for step 6: the step-5 reference solver plus COSMO gradients (pm7/cosmo.py, driver.py, run.py). Built by a helper agent from the MOPAC source,
# then checked by the author against the hidden references through the real verifier. Steps 1-4 are unchanged.
set -euo pipefail
mkdir -p /workspace/solver
cp -r /solution/solver/. /workspace/solver/
