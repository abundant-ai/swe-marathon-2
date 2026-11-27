# Step 5: Implicit solvent

Continue in `/workspace/solver/`. A collaborator wants the same PM7 single points in solution. The original program models a solvent with COSMO, switched on by the keyword `EPS=<dielectric constant>`; use its default settings for everything else about the model.

Make `run.py` accept `EPS=` on single-point jobs (`1SCF`, Cartesian coordinates) together with the step-1 keywords `CHARGE=n`, `UHF DOUBLET` and `UHF TRIPLET`. Dielectric constants between 2 and 80 occur. In addition to `heat_of_formation`, `atom_charges`, `ionization_potential` and `dipole`, write:

- `area` (square Angstrom): the surface area the original program reports for the job
- `volume` (cubic Angstrom): the volume it reports for the job

All of these are the values the original program prints for the same input (with the solvent, the heat of formation is the value it prints as the final heat of formation). Gradients are not requested for these jobs.

Accuracy required: heat of formation 0.05 kcal/mol, atom charges 2e-3, ionization potential 2e-3 eV, dipole 2e-3 Debye, area 1e-2 and volume 5e-2. The solvent model builds its surface from a discrete set of points, so a small difference in how the surface is built shows up directly in these numbers.

All earlier cases are evaluated again. Examples are in `/workspace/examples/`. Update `/workspace/NOTES.md`.
