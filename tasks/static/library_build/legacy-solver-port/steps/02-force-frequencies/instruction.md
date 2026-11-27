# Step 2: Vibrational analysis

Continue in `/workspace/solver/` from where you left it. A collaborator needs vibrational analysis: PM7 `FORCE` jobs that print the heat of formation, the zero-point energy and the vibrational frequencies of an optimized molecule.

Extend `run.py` so that an input with the `FORCE` keyword writes, in addition to the step-1 fields:

- `zero_point_energy` (kcal/mol)
- `frequencies` (cm-1, the 3N-6 vibrational modes, or 3N-5 for a linear molecule)

The reference is the output of the original program for the same input. Hidden molecules include larger and lower-symmetry species than the examples in `/workspace/examples/`; ions, radicals and triplets are included.

All earlier results must stay the same: the step-1 hidden cases are evaluated again. Update `/workspace/NOTES.md` with what you changed and learned.

Note that the original program's `FORCE` does not always build the full Hessian: it uses the molecule's symmetry to reduce the work, and its frequencies come from that procedure, so reproduce what it prints rather than the exact PM7 Hessian.

Accuracy required: heat of formation 1e-4 kcal/mol, zero-point energy 1e-3 kcal/mol, every frequency (sorted) 0.2 cm-1. A job has 15 minutes.
