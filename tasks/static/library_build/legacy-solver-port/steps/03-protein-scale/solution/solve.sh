#!/usr/bin/env bash
# Reference solver: dense PM7 for small molecules (steps 1-2), Z-matrix/PDB input (step 4), and a
# divide-and-conquer PM7 SCF with neighbour-list corrections for protein-size single points (step 3).
set -euo pipefail
mkdir -p /workspace/solver
cp -r /solution/solver/. /workspace/solver/
