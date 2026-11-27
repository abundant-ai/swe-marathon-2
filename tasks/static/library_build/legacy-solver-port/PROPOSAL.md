> Superseded 2026-11-26: this document describes the pilot stage (tolerances 0.1 kcal/mol and 0.005 e for step 3, 1BRR in the set, macOS references, no reference solutions for steps 3-4). The current state, the layout and the hackability evidence are in README.md.

# SWE-Marathon 2.0 idea proposal: MOPAC legacy-code port, extension, speed-up and migration

Family: scientific computing. Working name: `abundant/swe-m2_scicomp_mopac-port`. Author: Jack (jkaisun1@gmail.com). Status: idea stage. Everything under "Verified" was measured on 2026-11-18 and 2026-11-19; everything under "Not verified" is a gap, not a conclusion.

## One-paragraph pitch

An agent inherits MOPAC, a roughly 145k-line open-source (Apache-2.0) Fortran 90 semiempirical quantum-chemistry program with years of undocumented numerical behavior, and works on it through four dependent steps: port a core subset, extend it, make it fast, migrate its file formats. Each step starts from the workspace the agent left at the end of the previous step, and every verifier re-runs all earlier hidden cases. The original program is the oracle, available only in the private verifier container.

## Why this base problem (evidence from two pilots)

I first built small synthetic Fortran flow solvers (400 to 600 lines) and tested whether they make a long task. They do not. A fresh agent reproduced a textbook-scheme solver to about 1e-16 on 7 of 8 hidden decks, and a non-textbook scheme bit-for-bit on 9 of 9 hidden decks (28 tool calls, about 9 minutes; it disassembled the binary). Hiding the source or inventing a new scheme did not add horizon. The root cause is scale: a few hundred lines is not a week of work. MOPAC addresses this directly. (Pilot numbers are from my own runs; the agents' self-reports were not independently verified except the evaluated outputs.)

## Steps (revised 2026-11-19 after pilot 4: the horizon sits in steps 2 to 4)

Pilots 3 and 4 show step 1 (PM7 SCF, gradients, optimization, 9 elements) is a bounded transcription of about 100 min. It is kept as the starting state that later steps build on, not as the hard part. Steps 2 to 4 must be behavior that is not a copy of one routine.

| # | Step | Graded on (hidden cases) | Depends on |
|---|---|---|---|
| 1 | Port PM7 single point, gradient and optimization (H,C,N,O,F,P,S,Cl,Br; ions; radicals) | As pilot 4 | none |
| 2 | New physics on the ported core: vibrational analysis (`FORCE`: finite-difference Hessian, mass weighting, translation/rotation projection, frequencies, ZPE, thermodynamics) and transition-state location (`TS`); optionally COSMO | Frequencies (0.2 cm-1), ZPE, heat; MOPAC's symmetry shortcut is part of the reference and is NOT named in the task text (see Pilot 5 decisions), plus all step-1 cases | agent's step-1 code (needs its gradient to be accurate and fast) |
| 3 | Scale: protein-size systems (PDB input, Lewis-structure perception, MOZYME-style localized SCF) on hidden sizes of several hundred to a few thousand atoms | Heat and gradient vs original MOZYME result at stated tolerance, wall-clock gated on correctness, plus earlier cases | agent's step-2 code |
| 4 | Migration (as piloted in Pilot 7): input-format support: Z-matrix / internal coordinates, dummy atoms, fixed-coordinate flags, PDB via `GEO_DAT`; results and final internal coordinates compared with the original. (`.arc`/`.res` continuation from the earlier design was not piloted.) | Heat, charges, IP, dipole, optimized geometry and final internal coordinates, plus all earlier cases | agent's step-3 code |

Evidence for steps 2 to 4 (2026-11-19, reference build, macOS): `FORCE` runs and prints frequencies (water test: 1414.6, 2801.0, 2855.3 cm-1). MOZYME and PDB handling ship with the source and tests (Crambin, 642 atoms: 11.2 s MOZYME). Dense PM7 on the same atoms took 14 s, so dense SCF is not slow at 640 atoms; step 3 needs larger sizes to force a real algorithmic change. The two heats differ by about 109 kcal/mol (MOZYME -2992.04 vs dense -2883.10), most likely a charge or Lewis-structure difference, NOT yet understood; the tolerance and what counts as the reference must be fixed before step 3 is gradable.

Open choices (to settle with organizers): target language, whether the agent receives the Fortran source or only a binary and manual, exact element set, whether step 3 is CPU-only, whether later steps are disclosed up front.

## Dependency mechanism

State carries over between steps; verifiers are cumulative; the fixed-denominator reward counts earlier cases in every later step. Honest caveat: on the small synthetic code a literal port absorbed steps 2 and 3 cheaply, so the dependency was not supported there. For MOPAC the dependency is a hypothesis that rests on scale, not yet validated. Validation plan: build a lazy (literal) and a refactored step-1 solution on a reduced subset, run steps 2 to 4 on both, and compare agent effort and score. If the gap is small the multi-step claim is dropped.

## Design dimensions (separate, no weighted score)

- Novelty: PARTIAL. Overlaps in pattern with FrontierSWE's Quantum ESPRESSO `pw.x` Rust port; differs in domain (semiempirical chemistry), a four-step carryover structure, and scale evidence. Not found in SWE-Marathon v1 (20 tasks) or the v2 repo. Primary sources for FrontierSWE not read; brainstorming sheet not accessible to me.
- Verifiability: numerical agreement with the original at tolerances set from measured spread; speed-up measured in the verifier container; partial credit per molecule and per step.
- Realism: labs inherit legacy chemistry codes and must port, extend, speed up and migrate them.
- Difficulty: a pilot of step 1 on a deliberately narrow subset (PM7, H/C/N/O, neutral closed-shell single points, source provided) was solved by one agent in about 21 minutes (see Pilot 3 below). As scoped, step 1 is NOT a week-long task; the horizon has to come from a much wider scope. Pilot 4 widened the scope (9 elements, ions, radicals, optimization) and was still solved in about 104 min (see Pilot 4); so scope alone does not make it week-long.
- Initial feasibility: builds and runs (below). Oracle exists. Whether a subset port is a week of agent work is UNVERIFIED.

## Verified (2026-11-18)

- License Apache-2.0 (LICENSE file read). 432 `.F90` files, 207k lines; about 145k excluding parameter tables, `copyc6.F90` data and `blas.F90`.
- Builds with CMake, Ninja, gfortran and OpenBLAS (801 targets). Sample inputs run in 0 to 3 seconds.
- Two 14-thread runs of SALT, port and erratic1 differ only in timestamps and per-cycle timing.
- Outputs of six sample inputs (Locate_TS, SALT, IONIZE, port, erratic1, Test_XENO) are identical across 1, 4 and 14 OpenMP threads (diff after removing timestamps and timing lines). erratic1 repeated 20 times in fresh directories gave one identical result.
- **The linked BLAS/LAPACK changes results.** The same erratic1 input gave a final heat of -167.67452 with Apple Accelerate and -167.67828 kcal/mol with conda OpenBLAS (difference 0.004 kcal/mol, about 2e-5 relative, 255 vs 249 optimizer cycles). `port` (single point) matched to 5 decimals in both. So the reference build, BLAS/LAPACK and platform must be pinned in the verifier, and tolerances on optimized quantities must exceed this spread.
- Heaviest shipped example run: Crambin MOZYME single point (about 650 input lines), 12 s. Several other shipped inputs are PDB-processing jobs with no heat of formation.
- Fresh-directory runs need only the input file. Some jobs write side files (for example a generated Fortran parameter file), so the verifier should run in an empty working directory and collect outputs explicitly.
- `port` final heat of formation matches the shipped reference to 5 decimals; `erratic1` differs by 0.012 kcal/mol from the shipped output (platform/compiler effect), so tolerances must come from measured spread.

## Pilot 3: step 1 on a narrow subset (2026-11-18)

Setup: one fresh agent, MOPAC source provided, Python with numpy/scipy only, no Fortran or MOPAC binary (enforced by instruction, not by sandbox; I found no build artifacts and no subprocess calls in its code). Six visible molecules, 14 hidden neutral CHNO molecules (2 to 11 heavy-plus-H atoms, perturbed geometries). The reference was the original program, built with Apple Accelerate.

Result, independently evaluated on the hidden set (agent copied alone into a clean directory):
- Heat of formation, gradients, charges, ionization potential, dipole: 14/14 within the targets (heat error at most 3.6e-7 kcal/mol, gradient at most 2.1e-7, targets 1e-4 and 1e-3).
- Eigenvalues: values agree to about 2e-9 eV on all 14, but my strict check passed only 9/14, because for larger molecules MOPAC writes only the highest levels (for example 18 of 20 for acetic acid, 20 of 25 for glycine) and the agent returned all levels. That print-limit rule never appears in the six visible examples. It is a small hidden-output-format behavior, not a numerical error.
- Size and effort: about 1,700 lines of Python; 21 minutes; the agent reported about 65 tool calls, the harness counted 105. Agent self-reports have been unreliable in earlier pilots, so treat the 65 as unverified.
- Notable behavior the agent had to find in the source: PM7 blends two-center integrals and core terms toward point charges beyond about 7 Angstrom; the SCF final density is not fully converged, so the iteration path (level shift, damping, convergence tests) had to be copied; MOPAC's gradient here is a finite difference with 1e-4 Angstrom steps.
- Not exercised by hidden molecules: the intermolecular hydrogen-bond and C-triple-bond corrections (checked only on the agent's own inputs without reference values).

Interpretation: with the source in hand and a narrow scope, the port is a transcription job that a strong agent finishes in minutes to an hour. This repeats the lesson of pilots 1 and 2 at a larger codebase: scope of the deliverable, not size of the repository, sets the horizon. A task that is a week long needs a much wider required behavior (more elements and methods, open-shell and charged systems, geometry optimization and its optimizer paths, solvation, linear-scaling MOZYME, input-format coverage), hidden behavior that is not recoverable by reading one code path, or withheld source.

## Pilot 4: step 1 on a wide subset (2026-11-19)

- Scope: PM7; H, C, N, O, F, P, S, Cl, Br (d-orbital integrals for P/S/Cl/Br); charged ions, UHF doublets and triplets; single points with gradients and geometry optimizations (EF, GNORM 0.01); up to about 30 atoms. 8 visible molecules, 37 hidden (31 single points, 6 optimizations).
- Result: the agent passed ALL quantities on ALL 45 jobs: visible 8/8, hidden sp 31/31, hidden opt 6/6. Single-point errors are 1e-6 or better (tolerance 1e-4 for heat); worst optimization geometry error 2.0e-3 A (dimethyl sulfide, tolerance 3e-3). Runtime per job 0.1 to 5 s.
- Effort: one agent, source provided, no Fortran run, 6.26e6 ms (about 104 min) and 212 tool uses by the harness (the agent said about 165). About 3600 lines of Python. Parameters were extracted by a generator script from the Fortran sources.
- Caveat on leakage: the agent also validated against reference outputs shipped in mopac-src/tests/ (e.g. erratic1.out). A real task must remove those, and the oracle-in-the-repo problem generally.
- Implication: widening the PM7 single-point plus optimization scope only raised the effort from about 20 min to about 100 min. With the readable source and a self-consistent reference in hand, step 1 is a bounded transcription job. Long horizon cannot come from scope alone. It must come from (a) withholding source or oracle, (b) steps 2 to 4 that depend on step 1 state, (c) much larger systems and performance targets, or (d) behavior not documented in source (e.g. MOPAC features beyond PM7 SCF, COSMO, MOZYME, solids, other methods).
- Caveats: one run, one agent, macOS Accelerate reference, no Linux/pinned-BLAS check, hidden set built by us (small organic molecules).

## Pilot 5: step 2 (FORCE vibrational analysis) on the step-1 code (2026-11-19)

- Setup: same agent type, started from its own pilot-4 solver, source provided (test outputs removed). New requirement: PM7 `FORCE` jobs (heat, zero-point energy, 3N-6 frequencies). 38 reference molecules (6 visible, 32 hidden; ions, radicals, triplets, P/S/Cl/Br/F, up to 15 atoms). References were made by optimizing then running FORCE with the real MOPAC. Tolerances: heat 1e-4, ZPE 1e-3 kcal/mol, frequencies 0.05 cm-1.
- Effort: 2.55e6 ms (about 42 min), 64 tool uses by the harness.
- Result: visible 6/6. Hidden 20/32 all quantities (heat 32/32, ZPE 24/32, frequencies 20/32). Step-1 regression on the pilot-4 hidden set: none (45/45 still pass).
- Initial failures listed below (12; see Diagnosis): acetate, dimethyl_sulfide, DMSO, methoxy radical, trimethylphosphine, toluene (ZPE errors 9e-3 to 0.29 kcal/mol, frequency errors 8 to 150 cm-1), chloroethane (2.4 cm-1), methanethiol (0.9), benzene and phosphine and hydronium (0.07 to 0.15 cm-1, near the tolerance), methylene triplet (no valid frequency list). The agent's own notes predicted the cause class: MOPAC's point-group detection and symmetry-equivalent-atom Hessian shortcuts were re-implemented with a brute-force detector; floppy/imaginary modes (methyl rotors) are sensitive. Large errors are most likely wrong symmetry or a soft mode, not yet diagnosed by me.
- Diagnosis of the 12 failures (2026-11-19):
  - 1 was my reference bug: methylene triplet is linear (3N-5 = 4 modes) and my builder kept 3N-6; the agent's four values are right. After fixing the reference the score is hidden 21/32 (frequencies 21/32, ZPE 24/32, heat 32/32).
  - 1 is a genuine agent miss: methoxy radical has a Jahn-Teller-distorted Cs geometry; the agent's brute-force detector with a 0.1 A tolerance finds C3v (6 operations) while MOPAC reports Cs (2).
  - 7 are floppy species (acetate, dimethyl sulfide, DMSO, toluene, trimethylphosphine, chloroethane, methanethiol). MOPAC's own symmetry shortcut changes its answer relative to the same job with NOSYM by 127 cm-1 (acetate), 92 (toluene), 48 (DMS), 19 (trimethylphosphine), even with the geometry re-optimized to GNORM 0.0005 (LET). Toluene's lowest mode is -77 cm-1 with symmetry and +16 cm-1 without. So the reference value of these cases is partly an artifact of MOPAC's symmetrized-Hessian code path, not physics. With NOSYM the agent matches MOPAC's NOSYM output to 0.2 to 1.1 cm-1 (14.5 for acetate, a very soft 8.7 vs 23.2 cm-1 torsion, and 6.5 for methoxy). The agent reproduces MOPAC's rule only approximately (operation order, which atoms are skipped).
  - 3 are near-tolerance noise (benzene 0.13, phosphine 0.15, hydronium 0.065 cm-1 vs the 0.05 tolerance): MOPAC sym-vs-nosym differs by 0.25 cm-1 for them; the agent's NOSYM match is 0.03 to 0.09 cm-1. The tolerance for such cases is simply too tight for finite-difference emulation.
- Consequence for the task design: a FORCE verifier that asks to reproduce MOPAC to 0.05 cm-1 on low-symmetry floppy molecules rewards imitating a buggy shortcut. Either restrict the hidden set to molecules where MOPAC sym and NOSYM agree to within the tolerance (rigid molecules), set per-mode tolerances from the sym/NOSYM spread, or deliberately make symmetry emulation part of the task and say so. This must be settled before step 2 is gradable.
- Decision (2026-11-19, author): reproducing MOPAC's symmetry-based Hessian shortcut is part of step 2's grading. Superseded by the later decision below: the task text will NOT name the symmetry shortcut. It says only that the reference is the original program's output. The hidden set deliberately includes low-symmetry floppy molecules where that shortcut changes MOPAC's own answer by tens of cm-1 relative to `NOSYM`. Frequency tolerance becomes 0.2 cm-1 (finite-difference emulation floor; the agent's NOSYM match was 0.03 to 0.09 on rigid molecules, so 0.05 was below the noise floor); ZPE tolerance stays 1e-3 kcal/mol.
- Rescoring the existing pilot-5 output at 0.2 cm-1: hidden 24/32 all quantities (frequencies 24/32, ZPE 24/32, heat 32/32); at 1.0 cm-1 frequencies 25/32. The 8 remaining failures are exactly the symmetry-emulation gap: acetate, dimethyl sulfide, DMSO, methoxy radical (wrong point group), toluene, trimethylphosphine, chloroethane, methanethiol. Not yet re-run with the changed task text, so whether an agent told about the requirement closes the gap is UNVERIFIED.
- Honest risk: grading on a vendor shortcut that gives unphysical values (toluene -77 vs +16 cm-1) is a design choice that some reviewers may reject as oracle-fitting; the argument for it is that faithful porting of legacy code means preserving its observable behavior, and a faithful port is detectable only by such cases. It also makes the step depend on deep, source-level reading, which is the intended horizon driver.
- Interpretation: unlike step 1, step 2 is not saturated by one 40-min run. The agent had to discover hidden behavior (tighter SCF criterion in FORCE, internal-coordinate frame round trip, symmetry handling) that is only visible by reading deep in the source or comparing against the oracle. The partial result gives a usable graded signal (20/32), which is the desired property. Not yet tested: whether a longer run, or a second try with the failure data, closes the gap.
- Caveats: one run, one agent; hidden set built by me (small molecules, no large symmetric clusters); frequencies printed to 0.01 cm-1; failure causes not diagnosed; no lazy-vs-refactored step-1 comparison, so the dependency claim between steps is still unvalidated.

- Decision 2 (2026-11-19, author): do NOT disclose the symmetry requirement in the task text. Step-2 task text states only that references are the original program's output and that hidden molecules include larger and lower-symmetry species. Visible FORCE examples stay the 6 rigid molecules (no floppy low-symmetry example). Expected signal, from pilot 5 (undisclosed): about 21/32 at 0.05 cm-1 or 24/32 at 0.2 cm-1 with a 42-min agent run; the remaining gap is discoverable only by comparing with the oracle or by reading MOPAC's point-group code. Pilot 5b (disclosed, extra examples) reached 30/32 in 11 min, which is why disclosure is rejected. Tolerances: frequencies 0.2 cm-1, ZPE 1e-3 kcal/mol, heat 1e-4 kcal/mol.
- Consequence for fairness: undisclosed requirements are only acceptable if the agent can get the oracle's behavior somehow (original program in the verifier only means the agent cannot run it). That is an office-hours question: whether the agent may see any reference outputs beyond the visible examples, and whether the visible set may be richer. If not allowed, the undisclosed behavior must be derivable from the source, which it is here (pilot 5b agent derived it from the Fortran).

### Pilot 5b: rerun with the symmetry requirement stated (2026-11-19)

- Setup: fresh agent, clean step-1 solver (no FORCE code), source provided without test outputs. Task text now says the reference includes MOPAC's point-group detection and symmetry shortcut and warns about distorted geometries; 9 visible examples (added ethanol, propene, acetone, none in the hidden set). Hidden set unchanged (32), frequency tolerance 0.2 cm-1, ZPE 1e-3 kcal/mol, heat 1e-4.
- Effort: 667 s (about 11 min) and 61 tool uses by the harness. New files: force.py, symm.py (MOPAC point-group detection, with a table generated from the Fortran), symdata.py.
- Result: visible 9/9 (max frequency error 0.005 cm-1). Hidden 30/32 all quantities (heat 32/32, ZPE 30/32, frequencies 30/32). Step-1 regression: none (45/45 still pass). No subprocess or ctypes use in the solver.
- The 2 misses: methoxy radical (8.2 cm-1, ZPE 1.4e-2; the distorted-Cs case the task text warned about) and trimethylphosphine (9.4 cm-1, ZPE 6.1e-2).
- Interpretation: once the hidden behavior is named in the task text and a few low-symmetry visible examples are given, step 2 is solved in about 11 min. The 42-min first run was mostly discovery of the symmetry effect itself. Naming the requirement removes the horizon. Whether to disclose it is therefore a real design lever: undisclosed, the step gave a graded signal (21/32 at 0.05, 24/32 at 0.2); disclosed, it is nearly saturated.
- Caveat: one run each, the first and second runs differ in more than the text (visible set, tolerance, clean start), so the comparison is indicative only.

## Pilot 6: step 3 (protein-size scaling) on the step-2 code (2026-11-19)

- Setup: agent starts from its step-2 solver, source provided (test outputs removed). Job: `PM7 1SCF CHARGE=n` single point on Cartesian proteins, outputs heat and atomic charges. 30-minute wall limit per job (stated as 8 cores, 16 GB; the evaluation ran on a 14-core Mac). Reference: MOPAC MOZYME (dense PM7 is impractical at 3500+ atoms). Visible: crambin 1CBN (648 atoms). Hidden: crambin 1EJG (642), bacteriorhodopsin 1AP9 (3578), 1AT9 (3667, charge +1), 1C3W (4542, charge +1). Tolerances: heat 1.0 kcal/mol, charges 0.01 e. Calibration: dense PM7 vs MOZYME differ by 0.02 kcal/mol and 0.002 e on the two crambins.
- Effort: 3.50e6 ms (about 58 min), 92 tool uses by the harness.
- Result (our own evaluation): visible 1/1, hidden 4/4. Heat errors 0.020 to 0.109 kcal/mol, max charge errors 0.0014 to 0.0070 e, wall time 6 s (650 atoms), 156 s (3667), 162 s (3578), 269 s (4542). Step-1 regression: none (45/45). Step-2 regression: hidden FORCE 30/32 at 0.2 cm-1, same as before; visible 6/6. No subprocess or ctypes use.
- How it was solved (agent report, not independently reviewed): exact pair integrals within 10 A, block-sparse H/F/P, divide-and-conquer density matrix with buffered groups and one Fermi level per spin, Pulay mixing, dense diagonalization up to 2600 orbitals, O(N^2) correction routines rewritten with neighbour lists. Not a MOZYME-style localized-orbital solver.
- Interpretation: step 3 as I specified it is solved in under an hour with a 10x time margin and a 10x accuracy margin. The 1.0 kcal/mol / 0.01 e tolerances and the 30-minute limit are too loose to discriminate; 0.1 kcal/mol would make the largest case borderline. Hidden proteins are two families (crambin and bacteriorhodopsin) and charges only 0 and +1.
- Cumulative effort of steps 1 to 3 by one agent: about 104 + 42 + 58 min, roughly 3.4 h of agent time, far below the 12 h Oddish cap. The pilots do NOT support a week-long horizon for the four-step task as specified. Step 4 (format migration) is not piloted.
- Caveats: one run per step, agent runs are serial and each starts from the previous agent state; MOZYME is a reference with its own approximation; hidden set small; the scoring machine may be slower (the agent's own estimate: 2x for UHF); the agent warned that odd-electron states and small-gap systems may converge to different states (these did not fail here).

## Pilot 7 (tightened step 3 + step 4, 2026-11-20)

Same method as the earlier pilots (fresh agent, source only, numpy/scipy, own evaluation against private MOPAC references; `scripts/make_pilot6b.py`, `make_pilot7.py`, `zmat.py`, `eval_pilot7.py`). The agent started from the pilot-6 solver and worked ~25 min wall, ~50 tool calls.

* **Step 3 tightened**: hidden set 6 proteins (642 to 11,747 atoms, charge 0 to +2; bR_2at9 was first included, then deleted because it contains P outside the H/C/N/O/S scope), heat 0.1 kcal/mol, charge 0.005 e, 30 min. Result 3/6: crambin_1ejg, bR_1ap9, bR_1brx pass; bR_1at9 (charge error 7.0e-3) and bR_1c3w (heat 0.11) fail narrowly; bR_1brr (+2, 11,747 atoms) returns a diverged result (heat ~1e9, charges -12..6), diagnosed below. The agent's own 12,000-atom test used synthetic crambin tiles, so it never saw this failure.
* **Step 4 (formats)**: Z-matrix, dummy atoms, fixed-coordinate flags, PDB via GEO_DAT; symbolic variables deliberately left out (MOPAC syntax unreliable to reference). Visible 6/6, hidden 74/75 (miss: acetic_acid_opt Z-matrix optimisation reached another conformer, distance error 0.017 A). About 25 min of agent time for steps 3b and 4 together. **Step 4 as built is easy**; it adds breadth, not length.
* **Diagnosis of the diverged case (2026-11-20)**: **bR_1brr** (all CHNOS, +2, 11,747 atoms) has 168 atom pairs closer than 1.0 A after ADD-H (H-H down to 0.76 A); the first SCF energy is 5.6e6 eV and the density mixing never recovers (|dP| stays ~0.9 for 80 iterations), whereas MOZYME reaches a converged answer. This is a real robustness gap in the pilot solver (SCF start/damping on strained geometries), not a spec error, but it comes from one input with clashing hydrogens, so it is one data point.
* **1BRR convergence experiment (2026-11-20)**: on a copy of the pilot solver, changing only the density mixing (0.5 -> 0.2) and restarting the Pulay history when the residual grew removed the divergence: energy fell into the physical range within ~10 iterations and settled near -49315.4 kcal/mol (reference -49312.6, error 2.8 kcal/mol, still 0.1 target missed by 28x). But phase 2 (buffer 10 A) costs ~41 s per iteration at 11,747 atoms on this 14-core Mac, so the run hit the 1500 s hard stop at ~26 min with max|dP| 6.8e-4 (not converged), which would exceed 30 min on 8 cores. So the divergence is a fixable SCF-robustness bug in the pilot solver, but 1BRR stays out of reach at 0.1 kcal/mol within the time limit; it is a good hard case, and it is not evidence the task is impossible.
* Cumulative agent time for steps 1 to 4 is about 3.8 h. This still does not support a week-long horizon.

## Pilot 8: lazy step-1 contrast (2026-11-21)

Goal: the dependency-validation requirement (two equally correct step-1 solutions, a lazy literal port and a refactored one, then run step 2 on both). Setup: fresh agent, pilot-4 step-1 task plus a "Work style" paragraph asking for the least effort, smallest code, literal translation, no abstraction for later steps, finite-difference gradients allowed, ~120 tool calls (`pilot8/`). The refactored arm is the pilot-4 solver.

* **Result: the pair is not neutral, so the dependency test is inconclusive.** The lazy solver took about 1.5 h / 132 harness tool calls (agent claimed ~85) and scores on the hidden step-1 set: single points all-quantities 1/31 (heat 29/31, gradients 1/31, charges 6/31, IP 26/31, dipole 20/31); optimizations 4/6. It converged the SCF fully, while MOPAC's default 1SCF stops loosely, so charges, dipole, IP and gradients carry reference noise that only a faithful port of the SCF stopping logic reproduces. The pilot-4 solver matched all 45. Step 2 was not run on the lazy solver, since a comparison from an unequal step 1 would not isolate the dependency.
* What this does show: shortcuts in step 1 are punished within step 1 itself (SCF-termination fidelity), not only later. That makes step 1 a strong filter but does not demonstrate the claimed cross-step dependency.
* **Leak found**: the `mopac-src/` tree given to the pilot-4 and pilot-8 agents still contained MOPAC's `tests/*.out` files (29) and `examples/*_output`; I had stated that test outputs were removed. The pilot-8 agent read `tests/erratic1.out` (31-atom PM7 energy breakdown) and `examples/example_scf.mop_output` to validate components. Pilot 4 (step 1, 45/45) may have had the same access (not checked in its transcript). Pilots 6 and 7 trees had them removed (checked). Step-1 results should be treated as measured with test outputs available; a real task must strip them from the agent's workspace.

## Pilot 9/10: corrected lazy-vs-refactored dependency test (2026-11-22)

Setup: two fresh agents did step 1 from a source tree with all test outputs removed (0 `.out`/`*_output` files), both with a fidelity note (reference charges/gradients come from MOPAC's default SCF termination, so reproduce the SCF loop); arm L told "least effort, literal port, minimal code, few notes", arm R told "extensible and maintainable: separate modules, explicit state, documented notes". Then a fresh agent per arm did step 2 (FORCE, symmetry shortcut undisclosed, identical to pilot-5 text).

* **Step 1 is neutral**: both 31/31 hidden single points and 4/6 hidden optimizations (the same class of miss: their optimizers converge tighter than MOPAC's EF/GNORM 0.01, so floppy geometries differ). L: ~35 min, ~2,900 lines; R: ~37 min, ~4,300 lines (final: L 3,191, R 5,467 lines after step 2). Both far faster than pilot 4 (104 min); the fidelity note and the stripped tree are the likely causes, so earlier step-1 durations overstate difficulty.
* **Step 2 differs**: arm L 21/32 hidden FORCE (heat 32/32, ZPE 24/32, freq 21/32), ~22 min, ~97 tool calls; arm R 30/32 (fails: benzene, hydronium), ~50 min, ~87 tool calls. Both 6/6 visible and no step-1 regression (rescored: identical to before step 2). Arm L's 11 failures: acetate, chloroethane, dimethyl_sulfide, DMSO, hydronium, methanethiol, methoxy_radical, methylene_triplet, phosphine, toluene, trimethylphosphine. Both agents ported MOPAC's symmetry-skipping Hessian even though it was not disclosed.
* **Reading**: a pattern consistent with the claimed dependency (a more careful, modular step 1 led to a better step 2: 30/32 against 21/32), but it is **one run per arm**. The 21/32 of arm L equals the pilot-5 baseline score, so run-to-run agent variance (e.g. quality of the point-group detection each agent wrote) is not excluded and is a plausible alternative explanation. It is not evidence that a lazy step 1 makes step 2 slower: arm L finished step 2 in less time. Needs repeated runs per arm (at least 3) before being stated as a result.

## Pilot 9/10 repeated (3 chains per arm, 2026-11-22)

Two more chains per arm, same setup as the first (fresh agent for step 1 from a tree with all test outputs removed, fidelity note, arm L "least effort, literal port", arm R "extensible, modular, documented"; then a fresh agent per chain for step 2, identical undisclosed FORCE task). All scoring by `scripts/eval_pilot4.py` and `scripts/eval_pilot5.py` on the hidden sets, run by me.

| Chain | Step 1 hidden sp / opt | Step 2 hidden FORCE (of 32) | Step 2 agent time, tool calls | Step-1 regression after step 2 |
|---|---|---|---|---|
| L1 | 31 / 4 of 6 | 21 | ~22 min, ~97 | none |
| L2 | 31 / 4 | 30 | ~1.5 h, ~79 | none |
| L3 | 31 / 4 | **5** (visible 0/6; frequency errors 0.06-1.2 cm-1, SCF path not reproduced; 14/32 at 0.2 cm-1) | ~55 min, ~114 | none |
| R1 | 31 / 4 | 30 | ~50 min, ~87 | none |
| R2 | 31 / 6 | 29 | ~23 min, ~61 | none |
| R3 | 31 / 6 | 30 | ~15 min, ~71 | none |

* Step 1 is the same on single points (31/31 in all six chains); optimization differs: L1-L3 and R1 wrote their own optimizer and miss 2 floppy molecules; R2 and R3 ported MOPAC's EF optimizer and pass 6/6.
* Step 2: arm L scored 21, 30 and 5 (mean 18.7); arm R scored 30, 29 and 30 (mean 29.7). Failures common to every chain that reached 29-30: toluene and trimethylphosphine (soft torsions and MOPAC's symmetry-dependent noise), sometimes hydronium or benzene.
* **Reading (replaces the earlier note that the repetition did not reproduce the signal, written when only 5 chains were scored)**: arm L has much higher variance, including one chain (L3) that failed to reproduce MOPAC's SCF path in the FORCE loop and scored 5/32 and one that matched arm R. Arm R was consistent. This is suggestive of the claimed dependency (a careful modular step 1 makes step 2 more reliable) but n = 3 per arm, the arms differ also in what the agent decided to port (R2/R3 ported EF, L never did), and the instruction wording itself may steer how closely the agent reads the Fortran. It is not a result that a lazy step 1 makes step 2 slower: step 2 time does not separate the arms (L 22 min to 1.5 h, R 15 to 50 min, with noisy clocks). A reasonable statement for the proposal: a spread in step-2 outcome that depends on step-1 fidelity, in 1 of 3 lazy chains severe.

## Hidden items and process reward (proposal, 2026-11-24)

The SWE-Marathon 2 planning doc defines process reward as hidden items discovered / total hidden items. The behaviors below are ones the pilots showed an agent must find by reading the Fortran or comparing with the oracle; none is stated in the task text. Each maps to hidden cases that fail if the item is missed. The list comes from pilot observations; the mapping to scored cases and the per-item discovery rates are NOT yet implemented or measured (the pilots scored whole cases, not items).

| # | Step | Hidden item | Evidence in pilots |
|---|---|---|---|
| 1 | 1 | MOPAC's default 1SCF stops the SCF loosely; charges, dipole, IP and gradients carry that noise, so the stopping logic must be reproduced | Pilot 8: tighter-converged lazy port scored 1/31 sp |
| 2 | 1 | PM7 blends two-center integrals and core terms toward point charges beyond about 7 A | Pilot 3 |
| 3 | 1 | Gradient is a finite difference with 1e-4 A steps | Pilot 3 |
| 4 | 1 | Eigenvalue print limit: only the highest levels are written for larger molecules | Pilot 3 (5 of 14 failed a strict check) |
| 5 | 1 | EF optimizer path and GNORM 0.01 stopping decide the final geometry of floppy molecules | Pilots 9/10: own optimizers 4/6, ported EF 6/6 |
| 6 | 1 | Intermolecular H-bond and C-triple-bond corrections | Pilot 3 (not exercised by hidden cases; needs cases) |
| 7 | 2 | FORCE uses a tighter SCF criterion and carries density/shift state between displaced SCFs | Pilot 5 |
| 8 | 2 | MOPAC reorientation frame (atom 1 origin, atom 2 +x, atom 3 xy) round trip | Pilot 5 |
| 9 | 2 | Point-group detection, skipping of symmetry-equivalent atoms and Hessian symmetrization | Pilots 5, 5b, 9/10 |
| 10 | 2 | Distorted (Jahn-Teller) geometry gets a lower point group than a tolerance-based detector finds | Methoxy radical, pilots 5, 5b |
| 11 | 2 | Linear molecules have 3N-5 modes | Methylene triplet (my reference bug, found in pilot 5) |
| 12 | 3 | SCF robustness on strained geometries (clashing hydrogens): damping 0.2 and Pulay history restart | 1BRR, pilot 7 |
| 13 | 3 | Divide-and-conquer density with buffered groups, Pulay mixing, neighbour lists for the O(N^2) terms | Pilot 6 (agent's solution) |
| 14 | 4 | Z-matrix free format needs nine columns with `0.0 0` placeholders; flag 0 means fixed; dummy atoms `XX` | Pilot 7 setup |
| 15 | 4 | PDB read through `GEO_DAT` rounds to 3 decimals and takes the element from columns 77-78 | Pilot 7 setup |

Items 6 and 14 to 15 are the least evidenced: 6 has no hidden case, and 14 to 15 are format syntax that the step-4 task text may state. Treat them as candidates.

## Extension left to the team

The planning doc also wants simulated users and multi-round feedback during development. This proposal does not include that: step 4 is a fixed format-migration step. The team will add user simulation and multi-turn feedback later; step 4 can be replaced by a simulated-user round without changing steps 1 to 3 or the oracle.

## Not verified

Runtime of molecules much larger than Crambin; determinism on Linux with a pinned BLAS (all measurements here are macOS); hidden-case construction and license of any extra test data; whether the reference runs in a clean verifier container; a pilot of any wider step-1 scope or of steps 2 to 4; FrontierSWE overlap; reward formula numbers.

## Hackability (all UNASSESSED / YELLOW until tested)

| Attack | Mitigation idea |
|---|---|
| Call or wrap the original program | Original binary and compiler absent from the candidate image; forbidden-call scan; fresh verifier container |
| Hardcode outputs for visible molecules | Hidden, randomized molecules; geometries perturbed at verification time |
| Read private references | References outside the candidate image |
| Speed by lowering accuracy | Speed gated on correctness at fixed tolerances |
| Overwrite state between steps | Lineage hashes of the carried workspace |
| Disassemble or inspect a provided binary | Pilot 2 showed this works; if source is withheld it remains a risk |

## Questions for contributor office hours (Thursday 10 to 11 am PST)

1. Is a 145k-line base appropriate, and what horizon and hardware (CPU or GPU) does Oddish give a trial?
2. Is it acceptable that the original program runs in the private verifier but not in the candidate image?
3. May later steps' requirements appear only at those steps, given the rule against undisclosed grading?
4. Preferred target language and whether providing the source is expected.

## Next steps if accepted

Pilot step 1 on a reduced subset; measure tolerances across thread counts; build hidden molecule set; lazy-vs-refactored validation; write verifiers and the reward formula; `harbor check`; Oddish trials; PR with the template.
