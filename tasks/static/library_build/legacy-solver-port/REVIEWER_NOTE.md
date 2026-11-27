> Superseded 2026-11-26: this document describes the pilot stage (tolerances 0.1 kcal/mol and 0.005 e for step 3, 1BRR in the set, macOS references, no reference solutions for steps 3-4). The current state, the layout and the hackability evidence are in README.md.

# Reviewer note: MOPAC PM7 port (SWE-Marathon 2.0 proposal)

Author: Jack (jkaisun1@gmail.com)

## What the task is
Four dependent steps on MOPAC 23.2.5 (about 145k lines of Fortran 90, Apache-2.0). State carries over between steps and verifiers are cumulative.
1. Port PM7 single points and geometry optimization to a clean Python/numpy implementation.
2. Add FORCE (finite-difference Hessian and frequencies). The reference applies an undisclosed point-group symmetry shortcut.
3. Protein-scale single points (hidden proteins, MOZYME references).
4. Input-format migration (Z-matrix, dummy atoms, fixed flags, PDB).

The original MOPAC binary exists only in the private verifier container. The solver sees source only (test outputs stripped).

## Pilot evidence (fresh general-purpose agents, source tree only, numpy/scipy only)
| Step | Result | Time |
|---|---|---|
| 1 | 45/45 (pilot 4) | about 104 min (later chains 35-60 min) |
| 2 | 21/32 undisclosed shortcut, 30/32 disclosed | |
| 3 | 3/6 hidden proteins (tightened set) | |
| 4 | 74/75 format cases (easy) | |
| 1-4 cumulative | | about 3.8 h |

## Does a weak step 1 hurt step 2? (3 chains per arm)
Arm L: lazy step 1. Arm R: refactored step 1. Hidden FORCE score out of 32:

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| L | 21 | 30 | 5 |
| R | 30 | 29 | 30 |

- All six chains scored 31/31 on step 1 single points; step 1 did not regress after step 2.
- Arm L has one severe failure (5/32, not even the visible examples passed); arm R is consistent.
- Toluene and trimethylphosphine fail in nearly every chain regardless of arm (soft torsions plus symmetry noise).

## What this does and does not show
- Suggestive of a dependency: step 1 fidelity changes the distribution of step 2 outcomes.
- Not proven: n=3 per arm, and the arms also differ in what each agent chose to port (R2/R3 ported MOPAC's EF optimizer; the other four wrote their own). Step 2 wall time does not separate the arms.
- An interim statement of mine that repetition "did not reproduce" the signal was written after 5 chains and is superseded by the sixth.

## Known limits and open items
- Not yet run: Oddish trials, harbor check, hackability review, Linux/pinned-BLAS reproducibility, slower graders.
- Step 3: 1BRR is not solved to 0.1 kcal/mol within time (SCF divergence fixable with damping 0.2 plus Pulay restart, but about 26 min and unconverged); 1AT9 and 1C3W tolerances are borderline. 2AT9 was removed (contains P, out of element scope).
- Step 4 is easy; it mainly tests that the port does not break under input variety.
- Design question for office hours: per-step-as-session vs the 12 h Oddish trial cap, and whether a rescue checkpoint between steps is acceptable.

## Update 2026-11-25: Linux references, reference solutions, and what was changed after seeing results
The numbers above (pilot, 0.1 kcal/mol, 1BRR) are superseded. Current state: references regenerated with MOPAC built on Linux (the verifier platform); all four steps have a reference solution; local Harbor oracle gives reward 1.0 on every step (hidden: step 1 37, step 2 32, step 3 5, step 4 75).

Choices made AFTER looking at the reference solver's results (a possible source of bias; please judge them):
1. Step 3 tolerance relaxed from 0.1 kcal/mol / 0.005 e to 1.0 kcal/mol / 0.02 e. Reason: the pilot found no solver that met the tight target on all proteins.
2. Step 3 `bR_1brr` (11,747 atoms) removed. Reference solver: heat -3.1 kcal/mol, charge 0.10 e off, 708 s, 7.3 GB. The input is strained (168 atom pairs < 1 A); on a 260-atom cut-out the original program's dense PM7 and MOZYME differ by 20 kcal/mol on identical input, so the MOZYME reference is not reproducible by an exact method.
3. Step 4 `fixed_acetic_acid_opt` and `zmat_acetic_acid_opt` removed: the original program stops in a soft methyl-rotor mode, so the final geometry is not determined by the problem statement.
4. Step 4 internal-coordinate rows that involve dummy atoms are not compared (flat directions, optimizer-path dependent); `fixed_*` references use GNORM=0.001.
Details: `tests/refs_excluded/README.txt`, README.md.

Still not verified: 16 GB memory limit (local Docker had 8 GB; largest included case used 3 GB), grader speed (slowest local case 118 s of 1800 s), `harbor check`, Oddish trials. Soft cases (phosphoric acid, methoxy radical, trimethylphosphine, toluene) stay platform-sensitive.
