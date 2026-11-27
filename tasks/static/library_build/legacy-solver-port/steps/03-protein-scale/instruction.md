# Step 3: Protein-size systems

Continue in `/workspace/solver/`. A collaborator wants to run the same PM7 single points on proteins, from about 640 to well over 10,000 atoms, with Cartesian coordinates in a `.mop` file (`PM7 1SCF CHARGE=n`). Write `heat_of_formation` and `atom_charges` to `out.json` as before.

The reference is the original program's MOZYME result for the same input. Each job has a wall-clock limit of 30 minutes on 8 CPU cores and 16 GB of memory. Elements in scope: H, C, N, O, S. The solver must stay correct on the earlier small-molecule cases, which are evaluated again together with the new ones. A job that exceeds the limit or crashes counts as failed. Jobs are run in a clean container with the same Python, numpy and scipy as this one and no compiler: do not rely on compiling code at run time or on shared libraries beyond those packages.

One visible example is in `/workspace/examples/`. The hidden proteins are different structures and charges, including strained geometries with close contacts.

Update `/workspace/NOTES.md`.

Accuracy required: heat of formation within 1.0 kcal/mol and every atomic charge within 0.02 e of the reference.
