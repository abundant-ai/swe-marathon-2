# Step 4: Input formats

Continue in `/workspace/solver/`. Our collaborators' inputs do not all use Cartesian coordinates. Make `run.py` accept the formats they send:

- Z-matrix (internal coordinates), including dummy atoms (`XX`) and fixed-coordinate flags (a flag of 0 keeps that coordinate fixed during optimization)
- PDB files read through the `GEO_DAT="file.pdb"` keyword

For Z-matrix jobs, also write `internal_coordinates` to `out.json`: one row `[distance, angle, dihedral]` per input atom, dummy atoms included, with the final values (after optimization if the job optimizes). All other output fields are as in the earlier steps and `optimized_geometry` lists the real atoms only. Symbolic variables in Z-matrices are out of scope. The original program optimizes a Z-matrix job in its internal coordinates, and the reference geometries come from that procedure, so optimize in internal coordinates as well; a different coordinate system can stop at a measurably different geometry for soft torsions.

All earlier cases are evaluated again. Examples are in `/workspace/examples/`. Update `/workspace/NOTES.md`.

Accuracy required: the same limits as in steps 1 and 2 except that gradients are not compared. For optimizations, `optimized_geometry` is compared through interatomic distances (3e-3 Angstrom) and `internal_coordinates` row by row (distance 5e-3 Angstrom, angle 0.2 degrees, dihedral 0.5 degrees). Rows that involve a dummy atom, either as the atom itself or as one of its three reference atoms, are not compared. Optimizations that use fixed-coordinate flags stop at `GNORM=0.001`. A job has 15 minutes.
