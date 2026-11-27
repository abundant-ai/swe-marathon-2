# Step 1: Port PM7 single points and optimization

Our group inherited MOPAC (`/workspace/mopac-src/`, Fortran 90, about 145k lines). Nobody on the team knows its internals and we cannot ship the Fortran build to our collaborators. We need a Python implementation of its PM7 method that gives the same numbers as the original program.

Write it in `/workspace/solver/` with the entry point `python3 /workspace/solver/run.py NAME.mop out.json`. Python with numpy and scipy and a C compiler (gcc with OpenMP) are available; there is no MOPAC and no Fortran compiler in this environment. Your solver is graded in a container with the same tools, so it may build C code at run time, but nothing else can be assumed to be installed. The input is a MOPAC input file with Cartesian coordinates. The solver must write `out.json` with:

- `heat_of_formation` (kcal/mol)
- `gradients` (flat list, kcal/mol/Angstrom, only for single points)
- `atom_charges`
- `ionization_potential` (eV)
- `dipole` (Debye)
- `optimized_geometry` (flat list of x, y, z in Angstrom, only for optimization jobs)

Scope: PM7; elements H, C, N, O, F, P, S, Cl, Br; neutral molecules and ions (`CHARGE=n`); UHF doublets and triplets; single points (`1SCF GRAD`) and geometry optimizations (`EF`, `GNORM=0.01`); up to about 30 atoms. The reference values are what the original program prints with its default settings, so reproduce its behavior, including how it decides that the SCF has converged. Examples with reference values are in `/workspace/examples/`. The hidden evaluation uses other molecules and perturbed geometries.

We will keep extending, speeding up and migrating this code after the port, and you will be the one working on it. Write what you learned about the method and its numerical behavior in `/workspace/NOTES.md`, so that the next person can build on it.

Accuracy required (every quantity of a case must be within these absolute limits for the case to pass). Single points: heat of formation 1e-4 kcal/mol, gradients 1e-3 kcal/mol/Angstrom, atom charges 1e-5, ionization potential 1e-4 eV, dipole 1e-4 Debye. Optimizations: heat of formation 5e-3 kcal/mol, all interatomic distances of `optimized_geometry` 3e-3 Angstrom, atom charges 1e-3, ionization potential 1e-3 eV, dipole 1e-3 Debye. A job has 15 minutes.
