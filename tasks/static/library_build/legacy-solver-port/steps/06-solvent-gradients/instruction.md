# Step 6: Gradients in solution

Continue in `/workspace/solver/`. The collaborator now needs the forces for the solvated molecules of step 5, to feed their own optimizer. Make `run.py` accept `1SCF GRAD EPS=<dielectric constant>` jobs (Cartesian coordinates, the same keywords as in step 5) and write `gradients` (flat list in kcal/mol/Angstrom, as in step 1) together with everything step 5 asks for. The gradients are the ones the original program prints for the same input.

Accuracy required: gradients within 5e-3 kcal/mol/Angstrom, all other quantities as in step 5. A job has 15 minutes.

All earlier cases are evaluated again. Examples are in `/workspace/examples/`. Update `/workspace/NOTES.md`.
