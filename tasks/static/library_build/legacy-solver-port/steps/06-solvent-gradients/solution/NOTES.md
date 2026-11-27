# Step 6 - gradients of COSMO-solvated PM7 (`1SCF GRAD EPS=`)

Continues `NOTES5.md` (cavity, SCF, bit-level tie emulation are unchanged).  Changes:

| file | change |
|---|---|
| `pm7/cosmo.py` | `_ansude` also returns the distance derivatives of the two ring areas; `_surclo` records `isude/sude` (rings with `sumphi>1e-10`); `Cavity.isude/sude`; new `CosmoModel.gradient(p)` (port of DIEGRD) |
| `pm7/driver.py` | `single_point_cosmo` adds `gradients` when `GRAD` is present |
| `run.py` | `kind` is `"cosmograd"` for EPS+GRAD jobs |

Jobs without `EPS=` and EPS jobs without `GRAD` give byte-identical `out.json` (32 jobs compared with the finished step-5 solver:
single points with GRAD/UHF/charge, optimisation, FORCE, Z-matrix, dummy atoms, 14 EPS jobs; `w4/`).  The energy of a job is
the same with and without `GRAD` in the original, so all step-5 quantities are unchanged.

## How the original builds the gradient (compfg -> deriv -> dcart)

`gradient = DCART + DIEGRD`, there is no response of the SCF/screening charges (no CPHF):
1. **DCART** (forces/dcart.F90) is the usual MOPAC finite-difference of the *pair energies with the final density held
   fixed* (`dhc`), forward difference 1e-4 A (central with PRECISE) - the existing `gradient.cartesian_gradient`.  It sets
   `useps=.false.` first, so no COSMO operator appears in it, but the density is the *solvated* one (second SCF).
   It works on a fresh `gmetry` geometry (without the 3e-9 A cavity asymmetry); the post-SCF corrections (dispersion, H-bond ...)
   are added by `deriv` exactly as in vacuum.  For the solvated gradient `cartesian_gradient(z, job.coords, el, scf2, precise)`.
2. **DIEGRD** (solvation/cosmo.F90), added at the end of DCART with `useps` restored; `fact = -ev*a0*fpc_9`;
   segment charges `qsc = QSCNET(:,3) = q_nuc + q_el` are those of the final Fock build = final density, `qdenet(:,3)` = electron
   density `gden*P` + core charges at the s-s element, `qscat(atom) = sum qsc`, `arat(atom) = sum area of its segments`:
   * (a) segment-segment: for every pair (k,l), l<k, on *different* atoms `ff = qsc_k qsc_l fact r^-3 / fepsi`,
     `d(atom_k) -= (x_l-x_k) ff`, `d(atom_l) += (x_l-x_k) ff` - plain point charges at the segment centres, which move rigidly with their atom.
     (`fepsi` is divided out because `qsc` already contains `-fepsi`.)  The A-matrix itself (including its near-field and ring terms) is NOT differentiated.
   * (b) closure rings: for each ring `i` (`nipc` of them, only rings with `sumphi>1e-10`):
     `deab = -0.25 (qscat_a^2 sude1/arat_a + qscat_b^2 sude2/arat_b)/|x_b-x_a|`, `sude = d(area)/d(distance) * sumphi/2pi` from
     the analytic derivative in ANSUDE (`arad`, `arbd`); `d(a) -= (x_b-x_a) deab`, `d(b) += ...` (the `bsurf` term is 0).
   * (c) segment charge vs. electrons/cores of every other atom i (not the segment's own atom): multipole derivative of B:
     `ff0 = -qsc_k fact r^-3`, per packed density element j (1..10): `dx = (xx*db0_j - db_j) * (-ff0*qden_j)` with the s-p (`dd`)
     and p-p (`qq`) terms of MKBMAT differentiated; for d-orbital atoms (idel=9) the five d diagonal densities are added to the
     s-s element (`j==1`) and nothing else about d orbitals is differentiated.  `d(seg atom) += dx`, `d(atom i) -= dx`.
   The derivatives of the surface point positions with respect to the atoms (switching of grid points, segment re-assignment,
   the discrete part of the cavity) are neglected, which is why the gradient is smooth even though the energy is not.
3. `deriv` then maps the Cartesian derivative to the free coordinates (identity for XYZ input with all flags 1); output order as in step 1.

## Accuracy against the original (`mopac-linref`), `check6.py`

Test sets in `g/`: a (89: all small molecules of steps 1/2 perturbed, EPS 2-80, ions, UHF doublets/triplets, 30 complexes 15-30 atoms),
b (95, other seed), c and d (2 x 54: trimers up to 45 atoms, tight and compressed complexes), e (24: four ~80-atom clusters, ten
24-45-atom tetramers, tiny systems Cl-, Br-, HCl, N2, CO2, HCN, CS2, F2, exactly symmetric benzene); every input has `GRAD`, references
are the `GRADIENTS` and the step-5 quantities from the AUX of the original run (`w2/run_ref.py`).  316 generated inputs + 4 examples.

| quantity | tolerance | worst error | case |
|---|---|---|---|
| gradient component (kcal/mol/A) | 5e-3 | 2.4e-4 | `q4_03` (24 atoms; the 4 examples: <= 4e-8; typical 1e-7..1e-5) |
| heat | 5e-2 | 4.7e-6 | `big8_00` |
| charges | 2e-3 | 1.1e-6 | `q4_03` |
| IP (eV) | 2e-3 | 3.5e-7 | `q4_03` |
| dipole (D) | 2e-3 | 2.6e-6 | `q4_03` |
| area / volume | 1e-2 / 5e-2 | 5e-12 / 2.3e-9 | |

The 2.4e-4 gradient error of `q4_03` comes with charge errors of 1e-6 (heat error only 6e-8), which points to a density that differs by ~1e-6 (SCF stopping
point; not investigated further) rather than to the COSMO formulas; every other case is below 2e-5.
The worst case in terms of the formulas themselves is therefore ~1e-5, 500x below the tolerance.

Runtime (Python start included): 0.3-0.6 s up to ~15 atoms, ~1.1 s for 24 atoms, 4-5.5 s for 68-89 atoms.

## Uncertainties
* Single-atom jobs: the original writes no `GRADIENTS` entry; the solver writes `[0,0,0]`.
* `GRAD` with Z-matrix input (internal-coordinate gradients), PRECISE variants beyond what `cartesian_gradient` already did, EPS with
  optimisation / FORCE / PDB / MOZYME are not implemented or tested.  EPS+GRAD+PRECISE only differs by the DCART stencil (not compared against the original).
* The gradient inherits the step-5 bit-level cavity emulation; a different build of the original (no FMA) could change a tie in the
  surface and thereby the charges at the 1e-3 level for rare H-rich geometries; the gradient formula itself does not depend on it
  (the gradient is continuous in the cavity, see the "smooth" check of the task: 1e-6 A noise changes components by ~2e-3..6e-3).
