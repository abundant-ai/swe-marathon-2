# legacy-solver-port (MOPAC 23.2.5, PM7)

Family: scientific-computing. Proposed name: `abundant/swe-m2_scicomp_legacy-solver-port`.
Author: Jack (jkaisun1@gmail.com). Status (historical line from 2026-11-17; see the sections dated 2026-11-25 for the current state): idea-stage; pilots only, no harness task built. Full evidence: `PROPOSAL.md`, `DESIGN.md` (section 17 = pilots).

## One-line pitch
An agent inherits real legacy code, MOPAC (about 145k lines of Fortran 90, Apache-2.0), and re-implements a growing subset of it in Python across four dependent steps. State carries over (each step starts from the agent's own code), verifiers are cumulative, later requirements are not disclosed earlier, and the original program exists only inside the private verifier container as the oracle.

## Steps
1. Port PM7 single points and EF optimization (H, C, N, O, F, P, S, Cl, Br; charged, UHF doublet/triplet).
2. Extend: FORCE (vibrational frequencies, ZPE), with MOPAC's symmetry-based Hessian shortcut left undisclosed in the task text but part of the oracle's output.
3. Scale: protein-size single points (about 640 to 12,000 atoms), 30 min, heat 1.0 kcal/mol, charge 0.02 e (relaxed from 0.1 / 0.005 on 2026-11-25; see the last section).
4. Format migration: Z-matrix (dummy atoms, fixed-coordinate flags) and PDB input, final internal coordinates.

## Pilot results (single fresh agent per step, numpy/scipy only, no MOPAC binary)
| Step | Result | Agent time |
|---|---|---|
| 1 | 45/45 hidden | ~104 min |
| 2 | 21/32 undisclosed (30/32 once the symmetry shortcut is disclosed) | ~42 min (11 min disclosed) |
| 3 (loose, 1 kcal/mol) | 4/4 hidden | ~58 min |
| 3 tightened | 3/6 hidden; 1BRR (11,747 atoms) diverges, fixable by damping but still 28x off the target and too slow | ~25 min with step 4 |
| 4 | 74/75 hidden | (included above) |

Steps 1 to 4 total about 3.8 h of agent time. The pilots do **not** support a week-long horizon; difficulty sits in the undisclosed step-2 shortcut and in step 3 at scale.

## Not verified
Lazy-vs-refactored step-1 dependency test; harbor check; Oddish trials and hackability; Linux/pinned BLAS; slower graders; per-step-as-session design versus the 12 h trial cap; FrontierSWE overlap sources. See `PROPOSAL.md` "Not verified".

## Scripts
`scripts/make_pilot{3,4,5,6,6b,7}.py`, `scripts/zmat.py`, `scripts/eval_pilot{3,4,5,6,7}.py` build references with the MOPAC binary and score a candidate solver directory.

## Layout (2026-11-24)
- `steps/01-port-pm7`, `02-force-frequencies`, `03-protein-scale`, `04-input-formats`: `instruction.md` (what the solver sees) and `tests/test.sh` (runs in the private verifier container).
- `common/verifier/verify_core.py` (was `common/verify.py`): cumulative verifier. `--step N` scores hidden cases of steps 1..N against MOPAC-generated references in `/refs/step1..4` (fixed denominators; only hidden cases count). (2026-11-24 note, superseded: it has since been run on Linux MOPAC references in Docker, see the 2026-11-25 sections.)
- `scripts/make_pilot*.py`, `zmat.py`: build the references (needs the original MOPAC binary). The pilot reference files were wiped from the scratch area on 2026-11-23. On 2026-11-24 I rebuilt MOPAC (Apple Accelerate, from a pilot source copy) and regenerated step 1 (8 visible / 37 hidden), step 2 (6 / 32) and step 4 (4 / 77) references. Check run of `verify.py --step 2` with the pilot-10R3 solver: step 1 hidden 37/37, step 2 hidden 31/32 (it scored 30/32 in the original pilot; reward 0.9855). Step 3 references were regenerated too (1 visible, 6 hidden, from a fresh clone of openmopac/mopac at 5bbea09; 1BRR heat -49312.60 matches the earlier reference). `verify.py --step 3/4` has still not been run on a real solver.
- (Superseded 2026-11-25: the agent image, verifier images and `[verifier]` fields now exist; see Layout after the restructure.)
- `legacy/steps_old_nsflow/`, `legacy/`, `legacy2/`: earlier flow-solver draft, kept for history only.

## Harbor/Oddish layout (2026-11-25)
Converted to Harbor multi-step format: `task.toml` with `[[steps]]`, `environment/` (Dockerfile + vendored `mopac-src/`, 72 MB, no tests/build/outputs/git history), `steps/*/{instruction.md,tests/test.sh,solution/solve.sh,workdir/examples}`, root `tests/{verify.py,refs/}`. `oddish preflight .` passes (oddish 0.1.55). (Superseded: oracle run and reference solutions for steps 3-4 are done; Oddish trials still open.) The task name is `abundant/legacy-solver-port` because preflight requires it to match the directory name (or `name-<8 hex>`).

## Linux references (2026-11-25)
`tests/refs` steps 1, 2, 4 and step-3 (5 of 6 hidden + the visible one) were regenerated with MOPAC built in a Debian container (gfortran + system OpenBLAS, from `environment/mopac-src`, `-DTESTS=OFF`). Step-3 `bR_1brr` (11,747 atoms) was NOT regenerated: it is OOM-killed in an 8 GB Docker; it is still the macOS (Accelerate) reference. Counts are unchanged: step1 8/37, step2 6/32, step3 1/6, step4 4/77 (visible/hidden). Local Harbor oracle (steps 1-2 only) with the Linux refs: 37/37 and 32/32, reward 1.0, 0 exceptions.
Findings: (a) Linux MOZYME runs are thread-count independent (1 vs 4 threads, bR_1ap9: -15600.33594 vs -15600.33595). (b) Step-3 inputs from `ADD-H` differ between macOS and Linux (hydrogen placement), so heats differ by 0.3-1.5 kcal/mol for different structures, not numerical noise; ship each input with the reference computed from it. A Cartesian bR_1ap9 input gave the same heat on both platforms. (c) Soft cases differ between platforms beyond tolerance (phosphoric acid gradient 0.47, methoxy radical frequency 7 cm-1), so the references are platform-specific and must be generated on the verifier's platform.

## Step 4 reference solution (2026-11-25)
`steps/04-input-formats/solution/solver` = step 1-2 solver + `pm7/formats.py` (Z-matrix with dummy atoms and fixed flags, internal-coordinate BFGS optimisation, PDB via GEO_DAT, `internal_coordinates` output). Check on Linux Docker (Harbor oracle, steps 1, 2, 4; step 3 removed from the test copy): step 1 37/37, step 2 32/32, step 4 75/76 before excluding one case. Changes made while building it, all in the verifier/references:
- Z-matrix frame: MOPAC puts atom 2 on the x axis and atom 3 in the xy plane; the loose 1SCF stop is orientation dependent (zmat_hydrogen_sulfide charges differ by 7e-5 in another frame), so the solver uses the same frame.
- Dihedral rows whose atom or reference atoms include a dummy are not compared (flat directions; the final values depend on the optimizer path). `verify.py: dummy_rows`.
- `fixed_*` optimisation references now use GNORM=0.001 (visible example updated).
- Excluded (see `tests/refs_excluded/README.txt`): fixed_acetic_acid_opt and zmat_acetic_acid_opt. The reference stops in a soft methyl-rotor mode; step-4 hidden = 75.

## Step 3 tolerance relaxed (2026-11-25)
Step-3 targets are now heat 1.0 kcal/mol and charge 0.02 e (`SCALE` in `tests/verify.py`; was 0.1 / 0.005). Reason: no solver meeting 0.1 kcal/mol on all six proteins exists (pilot: 3/6). A reference solution for step 3 is being built; until it is verified, `steps/03-protein-scale/solution/solve.sh` still exits 1. 1BRR may be dropped if it cannot be met within 30 min and 16 GB.

## Full oracle run, all four steps (2026-11-25)
Step 3 reference solution added (`steps/03-protein-scale/solution/`, notes in `NOTES.md` there; steps 3 and 4 ship the same solver). Local Harbor oracle in Linux Docker (8 CPUs, 7 GB because this machine's Docker has 8 GB; the 16 GB limit was NOT tested): 0 exceptions, reward 1.0 for every step, no FAIL line. Hidden cases: step 1 37, step 2 32, step 3 5, step 4 75. Step-3 protein runs took 16-118 s.
Excluded (see `tests/refs_excluded/README.txt`): step 3 bR_1brr (solver -3.1 kcal/mol, 0.10 e off; MOZYME reference not reproducible by an exact SCF on that strained input) and two step-4 acetic acid cases. Still open: tolerance/exclusion choices were made after seeing the reference solver's results; `harbor check`; Oddish trials; grader machine speed; 16 GB.


## Development log

### 2026-11-25
- Moved under `tasks/static/library_build/` after main split static and usersim tasks (branch `jack/legacy-solver-port`, local only, not pushed).
- Sections above (dated 2026-11-25) record the Linux references, the step 3/4 reference solutions, the local oracle run and the tolerance and exclusion choices.
- Remaining: `harbor check`, Oddish trials, 16 GB memory test, grader speed, reviewer-note refresh.


## Task design dimensions (requirement.md) - first pass, none validated by trials
- **Novelty.** Capability added: numerical-parity port of a real scientific code (145k lines Fortran 90) to Python, then re-engineering the port for new requirements (new output, 20x scale, new input formats) with state carried across steps. Closest tasks in this repository: [`openfoam-rebuild`](../../app_clone/openfoam-rebuild/) rebuilds a scientific code too, but from the running binary and its docs and scores recorded runs; here the agent has the source and a numeric ground truth it cannot run, and the later steps change the problem rather than widen coverage. [`sympy-restoration`](../sympy-restoration/) restores removed function bodies in a library with visible tests; here nothing is removed and the work is a cross-language port. [`goose-compiler-rebuild`](../../app_clone/goose-compiler-rebuild/) is output-matching of a compiler from an execute-only binary. Difference that matters: the reference is a numerical result (tolerances, platform-dependent soft cases), so the difficulty is fidelity of numerics and scaling, not coverage of behaviours. External comparisons (Frontier SWE, Multi-Step SWE, SWE-Marathon v1) are unverified.
- **Verifiability.** Hidden references from the original program (MOPAC 23.2.5, Linux build), fixed denominators, per-quantity tolerances in `tests/verify.py`. Limit: agreement with one implementation; soft cases are platform-dependent.
- **Realism.** Re-hosting a legacy computational-chemistry code in Python and scaling it to proteins is real work. Evidence: pilots only.
- **Difficulty.** Pilot agents needed 11 min to 2 h per step (about 3.8 h in total), far below the 5-day target. Hard parts: the undisclosed step-2 symmetry shortcut, step 3 at 12,000 atoms. The pilots do not support a week-long horizon.
- **Initial feasibility.** A reference solution exists for every step (see below); it is not an independent rollout for steps 3-4 (step 3 was written by a helper agent and checked by me).

## Reward formula
`reward = (sum over steps 1..N of hidden cases passed) / (sum of hidden cases of steps 1..N)`, fixed denominators (hidden: 35, 32, 5, 75). A case passes only if every quantity is within tolerance (`SP`, `OPT`, `FORCE`, `SCALE` in `tests/verify.py`). Crashes and timeouts count as failures; a harness error exits non-zero and writes no reward. `multi_step_reward_strategy = "mean"` averages the per-step cumulative rewards. Visible cases are reported only. Implementation: `tests/verify.py`, `main()`. Boundary tests: none beyond the oracle run.

## Oracle status
Reference solutions for steps 1-4 pass the real verifier in local Harbor/Docker (reward 1.0 per step, 2026-11-25). Not yet run through Oddish or in a separately built verifier container. Provenance: steps 1-2 and 4 are agent-written (pilot agents and me); step 3 by a helper agent, reviewed by me.

## Hackability assessment (author-only)
Highest unresolved severity: 🟡 YELLOW / UNASSESSED (items marked below). Evidence below was executed on 2026-11-26 against the packaged bundle in local Docker (separate verifier image built from `steps/01-port-pm7/tests`).

| # | Attack | Result | Severity |
|---|---|---|---|
| 1 | Solver reads the references from the verifier filesystem and returns them (`/tests/private/**.json`) | **Succeeded (reward 1.0) in the first bundle**: the verifier ran the candidate's `run.py` as root next to the references. Fixed: `verify_core.run_case` now runs the solver as uid 10001 (`SOLVER_UID`), references are `0700 root`. Retest with the same solver: reward 0.0, `PermissionError` on `/tests` and `/tests/private`. Legitimate step-1 solver still 1.0. | 🔴 before fix, 🟢 after (this vector) |
| 2 | Solver overwrites `/logs/verifier/reward.json` or escalates (`setuid(0)`) | Both `PermissionError`; reward stays 0.0 for an empty solver. | 🟢 |
| 3 | Agent builds the original MOPAC (source is in `/workspace/mopac-src`) | The agent image has no gcc/cc/gfortran/clang/make/cmake. The agent network is `no-network` in `task.toml`; my `docker run` check had network and `pip download cmake` worked, so the block depends on Harbor enforcing `no-network` (not verified here). Even with cmake, there is no Fortran compiler. | 🟡 UNASSESSED (network enforcement) |
| 4 | Agent reads the references from its own container | The agent image has no `/tests`, no `/solution`, no references (listing checked). Visible examples include their references by design. | 🟢 |
| 5 | Hard-code outputs of the visible examples | Checked 2026-11-27 by comparing the coordinate blocks of all `.mop` files: no hidden case has the same coordinates as a visible one. One molecule name, `methanethiol`, is a visible step-1 single point and a hidden step-2 FORCE case, at a different geometry and with different quantities, so the visible answer does not give the hidden one. PDB inputs (coordinates in separate `.pdb` files) were not compared. A solver that memorizes visible answers was not built. | 🟡 UNASSESSED for PDB inputs, otherwise 🟢 |
| 6 | Candidate solver leaves files in `/tmp` that a later case uses | **Reproduced and fixed (2026-11-27).** A solver that fails if `/tmp/stamp` exists scored 0.0 under the old verifier (the first visible case left the stamp) and 1.0 under the new one, which gives each case a fresh `TMPDIR` and `HOME` and removes the solver's files from `/tmp` after each case. Other shared locations (for example `/var/tmp`, `/dev/shm`) are not cleaned. | 🟢 for `/tmp`, 🟡 UNASSESSED for other shared folders |
| 7 | Solver uses the verifier machine for something else (CPU, memory) | Timeouts per case (900 s, 1800 s for step 3); no memory cap beyond the container's. | 🟢 within scope |
Residual risk: whether Harbor copies only the declared artifacts to the verifier container, and no-network enforcement for the agent, depend on the runner; both are untested here. Next validation: repeat items 1-2 through Oddish, and item 3 with network enforced.

## Layout after the 2026-11-25 restructure
- `common/verifier/verify_core.py`: shared cumulative verifier. Each `steps/<step>/tests/verify.py` is a thin adapter (`--step N`).
- `steps/<step>/tests/{Dockerfile,test.sh,verify.py}`: dedicated verifier image (`verifier.environment_mode = "separate"`); the agent's `/workspace/solver` and `/workspace/NOTES.md` are copied over as artifacts.
- `steps/<step>/tests/private/{visible,hidden}`: that step's references. Git-ignored by the repository (`steps/**/tests/private/`), so they are NOT in the repo. `scripts/package_task.py` stages them into the step-N verifier build context (steps 1..N). Backup copy of the references: the author's original working directory only. To regenerate them: build MOPAC with `scripts/linref/Dockerfile` (vendored source from `environment/mopac-src`, `-DTESTS=OFF`) and run `scripts/make_pilot*.py` against that binary.
- `scripts/refs_excluded/`: the three excluded cases and the reasons.
- Packaging: `python3 scripts/package_task.py` writes `experiment/dist/swe-m2_scientific-computing_legacy-solver-port/`; `oddish preflight` on that folder passes. The bundle contains no README, scripts, checks or experiment files.

## Review against requirement.md (2026-11-25) and status
1. Tolerances now stated in each step's `instruction.md` (done; I appended an "Accuracy" paragraph to each brief at the author's request). Step 2 brief now also says that the original FORCE uses symmetry to reduce work. This changes the briefs, so pilot results above (written before the change) are not comparable; the symmetry disclosure in particular removes the difficulty the pilot measured (21/32 undisclosed vs 30/32 disclosed).
2. Separate verifier image: done in the bundle. Boundary not attacked yet.
3. Per-step `tests/verify.py`, shared code in `common/`, packager: done.
4. Private references no longer committed: done (Git-ignored location).
5. Step 2 shortcut disclosed (see 1).
6. `harbor check` NOT run: it needs model credentials that are not available in this session, and it would send the task files, including the private references, to a model provider. `[metadata.task_rating]` therefore not written.
7. Task name is now the packaged form `abundant/swe-m2_scientific-computing_legacy-solver-port`.
Still open: 5-day workload target (pilots about 3.8 h), Oddish trials, hackability boundaries, 16 GB limit.

### 2026-11-25 (restructure)
- Executed: moved the task under `tasks/static/library_build/`; restructured as above; appended accuracy paragraphs to the four briefs; built the bundle; `oddish preflight` on the bundle passed; local Harbor oracle on the bundle (Docker, 8 CPUs, memory lowered to 7000 MB for this machine): see the result entry below.
- Result of the local Harbor oracle on the packaged bundle (Docker, separate verifier containers, 8 CPUs, memory 7000 MB instead of 16384 because this machine's Docker has 8 GB): reward 1.0 on all four steps (cumulative step1..step4 scores all 1.0). Not tested: 16 GB, other hardware, Oddish, hackability boundaries, `harbor check`.

### 2026-11-26
- Executed: adversarial check of the verifier. A solver that copies the references from `/tests/private` scored 1.0 because the verifier ran candidate code as root. Fixed by running solvers as uid 10001; the same attack now scores 0.0 and the legitimate solver still 1.0 (details in Hackability assessment). Other probes (reward-file write, setuid, compilers in the agent image) recorded there.
- Written: novelty comparison with three tasks in this repo; refreshed stale lines in earlier sections.
- Full Harbor oracle on the rebuilt bundle: see the next entry.
- Result (2026-11-26): full local Harbor oracle on the bundle rebuilt after the uid-10001 fix (Docker, separate verifier containers, 8 CPUs, memory 7000 MB): reward 1.0 on all four steps, 0 errors, no FAIL line. Same untested items as before: 16 GB, other hardware, Oddish, `harbor check`, no-network enforcement.
- Oddish baselines (2026-11-26, task `swe-m2_scientific-computing_legacy-solver-port-88f97f31`, task version 2, experiment ed2e77b6, Modal): nop reward 0.0 (expected), oracle reward 1.0 (about 45-50 minutes for the four steps). Version 1 failed the nop baseline: with no `run.py` the verifier exited 2 without a reward; fixed so a missing solver scores 0. Two default LLM trials (codex, antigravity) that Oddish queued on each submission were cancelled by me before completing. Still open: model trials, `harbor check`, no-network enforcement for the agent, hackability repeat on Oddish.

### 2026-11-27 (first model trial: claude-opus-5 on Oddish)
- Run: trial `swe-m2_scientific-computing_legacy-solver-port-88f97f31-11`, task version 2, experiment 1cf491c7, Modal, claude-code agent, one attempt, 260 steps, cost $194.36, about 10.4 h wall clock (20:58 to about 07:20 UTC). Oddish reward 0.88 = mean of the four cumulative step rewards.
- Per step (hidden cases passed, cumulative): step 1 35/37 (reward 0.946); step 2 24/32 on top of 35/37 (0.855); step 3 1/5 on top (0.811); step 4 75/75 on top (0.906).
- Step 1 failures: `acetic_acid_opt`, `dimethyl_sulfide_opt`, both geometry. Possibly the same soft methyl-rotor issue that made me exclude two step-4 acetic acid cases; not checked, so these two references may not be reproducible either.
- Step 2 failures (8): acetate, dimethyl_sulfide, dmso, methanethiol, methoxy_radical, methylene_triplet, toluene, trimethylphosphine (zero-point energy and frequencies). Brief disclosed the symmetry shortcut in this version.
- Step 3: crambin_1ejg passed (30 s). bR_1ap9 and bR_1brx ran 1715-1729 s and failed heat and charges; bR_1at9 and bR_1c3w hit the 1800 s timeout. The agent's own check passed all its local references.
- Probable cause of the step-3 slowness (hypothesis from reading the submitted code, not reproduced): the solver builds a C/OpenMP kernel with `gcc` at run time and otherwise falls back to a much slower SciPy path. The agent had a compiler (it compiled), but the verifier image (`python:3.11-slim`) has neither `gcc` nor `libgomp` (checked in a local build of the verifier image), so the prebuilt `.so` cannot load and the fallback runs. The brief says only numpy and scipy are available, so relying on gcc was outside the stated environment; but the environment the agent actually ran in evidently had a compiler, which contradicts the brief. I have NOT verified what the Modal agent image contains. Open design decision: make the agent environment match the brief (no compiler) or the verifier match the agent.
- Not an indicator of difficulty by itself: the run needed 10 h and $194, scored 0.88, and its weak points are fidelity on soft cases and speed on large proteins.

### 2026-11-27 (are the two step-1 failures reference problems?)
- Executed in the `mopac-linref` container (original MOPAC, Linux) with `scripts/check_opt_reproducibility.py`: for every step-1 `opt` case (6 hidden, 1 visible) the original MOPAC was rerun on 4 randomly rotated and translated copies of the input, and the final interatomic distances were compared with the stored reference (verifier tolerance 3e-3 A).
- Result: MOPAC disagrees with its own stored result by 0.0223 A for `acetic_acid_opt` and 0.0076 A for `dimethyl_sulfide_opt`; all other cases are within 3e-4 A (chlorobenzene 0.0000, glycine 0.0001, pyridine 0.0000, urea 0.0001, methanol 0.0003). Exactly the two cases claude-opus-5 failed are the ones whose reference depends on the orientation of the input: the loose default stop (GNORM=0.01) lands at a different point of a soft methyl-rotor mode.
- For both, the opus solver's geometry is inside the spread that MOPAC itself produces (acetic acid 0.0205 A vs MOPAC rotated 0.0209-0.0223; dimethyl sulfide 0.0078 vs 0.0076), and its heat equals MOPAC's own rotated-input heat (acetic acid -102.246016 vs -102.246013; stored reference -102.245685). Rerunning MOPAC with GNORM=0.001 stops at the same point as GNORM=0.01 (identical to the stored reference), so a tighter setting does not help.
- Conclusion: the two failures are a reference-reproducibility defect, not an agent error. Same class as the two step-4 acetic acid cases excluded earlier. NOT applied yet: removing them from step-1 hidden (37 -> 35) changes the denominators; pending the author's decision. The same test has not been run on step-4 optimization cases (Z-matrix inputs) or on step-2 FORCE cases.

- Applied 2026-11-27 at the author's request: `acetic_acid_opt` and `dimethyl_sulfide_opt` removed from hidden step 1 (37 -> 35; hidden denominators now 35, 32, 5, 75, total 147). Files moved to `scripts/refs_excluded/step1/` (the `private/` folders are Git-ignored). The claude-opus-5 trial above was scored with 37, so its numbers are not directly comparable: with the two cases removed its step 1 would be 35/35 (the other cumulative step scores would change accordingly; not recomputed). Oddish task version 2 still holds the old reference set; a new version has to be uploaded for the change to take effect there. Not re-run on Oddish. Local check of the rebuilt bundle: step-1 verifier image with the step-1 reference solver gives reward 1.0 on the 35 remaining hidden cases, and `oddish preflight` passes; the full four-step oracle was not re-run after this change.

### 2026-11-27 (step-2 failures of the claude-opus-5 trial: reference problem or agent error?)
- Executed in the `mopac-linref` container with `scripts/check_force_reproducibility.py`: every step-2 FORCE case (32 hidden, 6 visible) was rerun with the original MOPAC on 3 rotated and translated copies of the input and compared with the stored reference (tolerances: heat 1e-4, ZPE 1e-3, every sorted frequency 0.2 cm-1). The same script ran the opus step-2 solver (the artifact saved at the end of its step 2) on the original inputs.
- Result: all 38 references are reproducible by MOPAC itself (heat to 1e-9, frequencies to 0.000 cm-1; the largest deviation is methylammonium, 0.02 cm-1). FORCE results do not depend on the orientation of the input, unlike the step-1 `opt` cases. So none of the 8 failures is an orientation-instability artefact; they are differences between the opus solver and the original program.
- Opus solver, largest frequency error versus the reference for the 8 failed cases (cm-1): dimethyl_sulfide 313, dmso 150, acetate 50, toluene 24, methoxy_radical 15, trimethylphosphine 1.5, methanethiol 0.73, methylene_triplet 0.26. The first five are large and look like a different treatment of the symmetry-reduced Hessian; the last three are close to the 0.2 cm-1 tolerance. Passing cases that are close to the limit: aniline 0.149, phosphine 0.155, benzene 0.132, hydronium 0.110.
- Caveats: (a) the earlier macOS-versus-Linux comparison showed methoxy_radical and phosphoric_acid references moving by several cm-1 between BLAS builds (platform sensitivity), a different effect from orientation; the methoxy_radical reference may therefore be fragile on other machines. (b) I did not investigate why the opus solver is wrong on each case. No change made to the step-2 set.

### 2026-11-27 (step-4 optimization references: reproducibility)
- Scope: the 12 hidden step-4 optimization cases (5 `fixed_*`, 5 `zmat_*`, 2 `dummy_*`; all are Z-matrix inputs, the `fixed_*` ones with fixed-coordinate flags) plus the 2 visible ones. claude-opus-5 passed all 75 hidden step-4 cases, so this checks the references, not an agent failure. Executed in the `mopac-linref` container (original MOPAC).
- Test 1 (`scripts/check_zmat_opt_stop.py`): rerun with GNORM divided by 10 and by 100. Every case gives exactly the stored heat and geometry (differences 0.0). A Z-matrix input has no orientation freedom, so the rotation test used for step 1 does not apply.
- Test 2 (`scripts/check_zmat_opt_cartesian.py`): convert each non-fixed Z-matrix input to its Cartesian start geometry and optimise in Cartesian with the same keywords (a different optimizer path to the same minimum). 7 of 8 cases agree with the stored reference (heat <= 6e-7 kcal/mol, distances <= 3e-4 A). `zmat_dimethyl_sulfide_opt` does not: heat 5.8e-5 kcal/mol, distances 0.0072 A (tolerance 3e-3 A). Same soft methyl-rotor mode as the step-1 dimethyl sulfide case. The `fixed_*` cases were not tested this way (constraints live in internal coordinates).
- Reading: the step-4 references are stable under the stop criterion, and 7 of 8 testable ones are reproducible by an independent optimizer path. `zmat_dimethyl_sulfide_opt` is reproducible only by optimizing in internal coordinates like MOPAC does; opus did that and passed. The brief does not say to optimize in internal coordinates, so a Cartesian solver could miss it for a reason not stated in the task. Not changed; for the author to decide (keep, exclude, or state it in the brief). Not tested: `pdb_*` and the single-point step-4 cases (no optimization).

- Decision 2026-11-27 (author): keep `zmat_dimethyl_sulfide_opt` in hidden step 4 and state the requirement in the brief. Added to `steps/04-input-formats/instruction.md`: Z-matrix jobs are optimized in internal coordinates, like the original program. This changes a candidate brief after the claude-opus-5 trial, which saw the earlier wording (that run already optimized in internal coordinates and passed all 75), so the trial remains valid for step 4 but the brief differs from what it saw. Oddish task version 2 holds the old brief; upload a new version to take effect.

### 2026-11-27 (repository checks before the PR)
- Executed: `ruff format` on all Python files of the task (including the agent-written reference solutions and pilot scripts, which changes formatting only) and `ruff check --fix`; added a task-level `ruff.toml` that does not enforce lint rules on `steps/*/solution/**` and `scripts/**`; fixed the lint findings in `common/verifier/verify_core.py` (dict literals, `Path` file access, `check=False`, a documented broad `except`, no shebang). Re-checked in Docker with the step-1 verifier image: reference solver reward 1.0, copy-the-references solver 0.0, empty solver 0.0 (exit code 0, reward file written). A full four-step oracle on the formatted bundle was started afterwards; result in the next entry or absent if not recorded.

### 2026-11-27 (local hardening before the Oddish QA run)
- Step-3 brief: now states that jobs run with the same Python, numpy and scipy and no compiler (the claude-opus-5 solver relied on `gcc` and OpenMP at run time, which the verifier image does not have). The agent image on Modal evidently has a compiler despite that, so the brief is the only guard; whether the Modal agent image should lose it is a runner question not settled here.
- Verifier: fresh `TMPDIR` and `HOME` per case and removal of the solver's files in `/tmp` after each case (see hackability row 6). Re-tested in Docker with the step-1 verifier image: stamp solver 1.0 (old verifier: 0.0), reference solver 1.0.
- Boundary tests: `checks/test_verify_core.py` (6 tests with synthetic references: correct solver 1.0, missing solver 0 with a reward file, crashing solver 0 with the denominator unchanged, one wrong case costs exactly its share, visible cases do not count, no hidden references is an error without a reward file). Added the folder to `pyproject.toml` `testpaths`. `uv run --frozen pytest tasks/static/library_build/legacy-solver-port/checks`: 6 passed.
- `task.toml`: `difficulty_explanation` now cites the claude-opus-5 trial instead of "TODO".
- Result (2026-11-27): full local Harbor oracle on the final bundle (all changes above; Docker, separate verifier containers, 8 CPUs, memory 7000 MB): reward 1.0 on all four steps, 0 errors, no FAIL line. Not yet run on Oddish: this bundle is a newer version than Oddish task version 2.
