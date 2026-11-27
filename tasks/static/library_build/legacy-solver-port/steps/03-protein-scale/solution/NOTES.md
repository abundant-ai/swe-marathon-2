# Step 3 notes: protein-size PM7 single points (pm7/scale.py, pm7/scale_corr.py)

Routing (run.py): a Cartesian job with `1SCF`, more than 250 atoms, closed shell, no FORCE goes to
`pm7.scale.single_point_big`; everything else runs the unchanged dense code (outputs byte-identical to the
step-4 solver on the small cases I compared, same run time).  Before numpy is imported, run.py sets
OPENBLAS/OMP/MKL/VECLIB threads = 1 for big jobs (the big path is task-parallel with 8 Python threads;
a threaded BLAS under each would oversubscribe: measured 6 min instead of 35 s on a 3.6k-atom case).
Limitation: for big jobs given as GEO_DAT=pdb the atom count is not known before numpy is imported, so BLAS
threads are not limited there (works, but slower).

## Physics (same as the dense code)
Same pair integrals (`twocenter.pair_integrals`), resonance integrals (`overlap.h1elec`), one-center tensors,
core-core terms and post-SCF corrections.  Differences are only organisational:
* r < 7 A (TRUNC_1): exact NDDO integrals, stored per atom-pair class (W4 tensors), multiprocessing (fork).
* r >= 7 A: PM7 feathering makes every two-centre quantity a point charge.  Verified numerically (C-C, O-H,
  N-O, S-S, H-H, C-H at 6.9..12 A): W, V and the core-core repulsion equal the point-charge values to 1e-12 eV
  for r >= 7 A, except the O-H core-core term (exp(-2*par4*r), 8e-6 eV at 7 A), which is added from a tabulated
  `ccrep` tail out to 16 A.  So beyond 7 A: Coulomb = dense atom-atom 1/R matrix times populations (exact), plus the point-charge
  exchange -pt*P_mu,la on the sparsity pattern out to RK=10 A, and the resonance integral out to RH=9 A.
  Neglected: exchange beyond 10 A, resonance integrals beyond 9 A (< 1e-7 eV).  Check on crambin: dense solve
  inside this framework vs the step-4 dense solver: 0.0005 kcal/mol.
* Corrections (`scale_corr.py`): dispersion (vectorised, all pairs < 100 A), H-bond list/DH+ setup, N-H-C=O term,
  connectivity: same formulas and loop order as `corrections.py` with k-d-tree candidate lists
  (checked equal to 1e-12 kcal/mol on crambin and 1AP9).

## SCF
* H, F, P in one block-sparse pattern (CSR data arrays, pair blocks + diagonal blocks).
* Density: divide and conquer.  Cores of <= 30 atoms (recursive bisection), subsystem = core + all atoms within
  `buffer` A of a core atom; each subsystem Fock matrix is diagonalised densely (numpy eigh, GIL released,
  8 threads); core rows of P are assembled; one global Fermi level (kT = 0.05 eV) fixes the electron count.
  Only states within +-1 eV of the previous mu are kept for the final occupation fix (single eigh pass per iteration);
  falls back to a two-pass scheme if the window misses.
* Energy: Harris-Foulkes form E = 2 F[P_in].P_out - P_in.G[P_in] (+nuclear +atomic terms).  The plain
  energy P.(H+F) of a DC density is first-order in the SCF residual (noise of ~10 kcal/mol at |dP|=1e-5);
  the HF form is second order and converges monotonically.  This is what made loose convergence (|dP| 5e-4) safe.
* Mixing: damped linear mixing (0.3) while far from converged (|dP|>0.1 and E still moving > 100 kcal/mol/it),
  then Pulay (6 vectors, float32 history).  History restart if the residual doubles.
  Needed for 1BRR (see below): Pulay from the start diverges.
* Two levels: converge with buffer 6 A (about 5x cheaper), then continue the same SCF with buffer 9 A
  (3-10 iterations).  Exit: |dP|<5e-4, or E_HF stagnated (|dE|<0.03 kcal/mol twice with |dP|<5e-3), or
  time budget 1300 s.  Systems with <= 2600 orbitals use dense diagonalisation of the full matrix instead
  (both crambins).
* Charges from P_out of the last big-buffer step.  Open-shell / odd-electron large jobs: not supported by this
  path (NotSupported -> falls back to the dense code, which would be very slow).

## Error budget (buffer error dominates)
DC heat error vs buffer, crambin-1CBN against dense (kcal/mol): b=6 1.2, 7 0.16, 8 0.045, 9 0.004, 10 0.001.
1AP9 vs reference: b=7 0.78, 8 0.63, 9 -0.038, 10 -0.033.  Error is extensive, so 9 A is used for all sizes.
Remaining difference to the MOZYME references (-0.02 .. -0.07 kcal/mol on the five smaller proteins) is the
MOZYME approximation itself (dense PM7 vs MOZYME on crambin is also -0.023).  Charge errors are 1e-3..1e-2
(largest 1.1e-2 on 1C3W, 9.6e-3 on 1AT9; limit 0.02); they are dominated by MOZYME-vs-exact differences, not by DC.

## Results (aarch64 Linux container, python 3.11.18, numpy 1.26.4, scipy 1.13.1, --cpus 8, env -i)
| case | atoms | wall s | peak GB (cgroup) | heat err kcal/mol | max charge err |
|---|---|---|---|---|---|
| crambin_1cbn | 648 | 18 | 0.5 | -0.023 | 2.0e-3 |
| crambin_1ejg | 642 | 18 | 0.4 | -0.020 | 1.7e-3 |
| bR_1brx | 3351 | 99 | 2.6 | -0.008 | 3.1e-3 |
| bR_1ap9 | 3578 | 88 | 2.7 | -0.048 | 3.3e-3 |
| bR_1at9 | 3667 | 73 | 2.6 | -0.067 | 9.6e-3 |
| bR_1c3w | 4542 | 120 | 3.0 | +0.126 | 1.1e-2 |
| bR_1brr | 11747 | 708 | 7.3 | **-3.10** | **0.102** |
(Mac, 8 threads, same code: see the MAC section at the end.)

## Why bR_1brr fails (accuracy, not time or memory)
Time 708 s (of 1800) and 7.3 GB (of 16) are fine.  The heat is 3.1 kcal/mol below the MOZYME reference and the charges
of the retinal region (atoms ~10920-11020) differ by up to 0.10 e.
* The input has 168 atom pairs < 1 A (H-H down to 0.76 A) and three C-C bonds of 1.16 A (C#C correction = 36 kcal/mol)
  in the retinal chromophore (charge +2, Schiff base).  The Fermi level sits in a near-degenerate region there, the SCF
  has several solutions, and the first iterations are a charge-sloshing/level-crossing problem (S of sulfate ions and
  retinal C oscillate by 0.3 e per iteration).  What worked: damping 0.3 before Pulay; with 0.5 or Pulay from the
  start the density diverges (E -> -1e8).
* The result is not a DC-buffer artefact: b=9 and the earlier b=10 prior-art run both land at -49315.4..-49315.8
  (b=6: -49288, so the buffer matters at the 20 kcal level, but 9 vs 10 for the other proteins moves < 0.01).
  After convergence there is a soft mode (E drifts -0.03..-0.08 kcal/mol per iteration at |dP| 1e-3; I stop at the stall criterion).
* Evidence that the reference is the odd one: I cut a 260-atom cluster (H-capped) around the worst retinal atom
  and ran the original MOPAC (Mac build) on it: dense PM7 333.7 kcal/mol, MOZYME 353.4 kcal/mol (+19.7 kcal/mol, same
  input).  My dense solver (and the step-4 solver) finds yet another state (188.9 kcal/mol, charges differing by
  up to 1.4 e from MOPAC dense), i.e. on this geometry the SCF solution is not unique and MOPAC dense,
  MOPAC MOZYME and a ground-state solver disagree by far more than 1 kcal/mol.  Reproducing MOZYME's 3 kcal/mol there would
  mean reproducing its localized-orbital iteration path, which this solver does not do.
  On the five well-behaved proteins MOZYME and an exact SCF agree to 0.02-0.13 kcal/mol.
Conclusion: 1BRR runs well inside 30 min / 16 GB and gives a physically sensible, lower-energy answer but does not pass
(heat 3.1 > 1.0; charge 0.10 > 0.02).  I did not special-case it.

## What I did not do / risks
* Open-shell and PDB-input big jobs: no special path (see above).  Only H, C, N, O, S were exercised.
* Hidden inputs with strained retinal-like geometry may show the same non-uniqueness.
* Timings: the grader machine may be slower; margin on the five passing proteins is >= 7x (<= 120 s of 1800 s).
* Memory of 1BRR 7.3 GB peak (Linux); Mac ru_maxrss 9.5 GB.
* Tuning knobs via env (PM7_VERBOSE, PM7_ALPHA, PM7_PDE, PM7_STALL, PM7_DEADLINE, PM7_DELTA=1 selects an unused
  frozen-correction two-level variant that was less stable on 1AT9: error 1.6 kcal/mol).

## Regression
Old (step-4) vs new solver on step1 hidden alanine, benzene, cysteine, hydronium, methylene_triplet, nitrogen_dioxide,
dmso, phenol, glycine_opt, dimethyl_disulfide, step2 alanine (FORCE), step4 dummy_benzene, dummy_cysteine:
output JSON byte-identical, run times unchanged (0.1-0.25 s; glycine_opt 2.3 s).

## MAC (macOS arm64, python 3.13 / numpy 2.4.3, 14 cores, big path uses 8 threads), same code, env -i
crambin_1cbn 5.3 s 0.66 GB err -0.020 dq 2.6e-3 | crambin_1ejg 5.3 s 0.74 GB -0.017 2.0e-3 | bR_1ap9 60 s 4.0 GB -0.043 2.9e-3 |
bR_1at9 43 s 4.0 GB -0.059 9.8e-3 | bR_1brx 56 s 4.2 GB +0.022 3.1e-3 | bR_1c3w 79 s 4.4 GB +0.136 1.0e-2.
bR_1brr on the Mac (development runs of the same algorithm, 8 threads): ~420-550 s to the stall criterion, ru_maxrss 9.5 GB,
heat -49315.5..-49315.8.  The Linux container run (above) is the measured final number.
