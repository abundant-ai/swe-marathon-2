#!/usr/bin/env bash
# Reference solution for step 5: the step-4 reference solver plus pm7/cosmo.py (COSMO, EPS=). Built by a helper agent from the MOPAC source,
# then checked by the author against the hidden references through the real verifier. Steps 1-4 are unchanged.
set -euo pipefail
mkdir -p /workspace/solver
cp -r /solution/solver/. /workspace/solver/
