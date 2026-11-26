# Weave merge-driver rebuild: QA plan (Phase A, 2026-11-26)

Author notes. Nothing here has run. Every check below is scripted under the task's `checks/` (run
locally, never shipped), blocks upload when it fails, and writes its output into the README's
Validation table, so a reviewer finds evidence rather than a claim. QA reports go to harbor-lh
(`ops/swe-marathon-v2/qa/weave/`), never into this repository.

## 1. The 12-item pre-upload gate, mapped to this task

| # | Gate | Pass criterion for Weave | How |
| --- | --- | --- | --- |
| 1 | Inventory | `features.yaml` lists every rule of the specification (one id per rule, about 150-250), every flag and exit status, and every stated restriction (section 2); a diff of the specification's rule markers against it shows nothing unlisted | rule markers in the specification's source; `checks/test_inventory.py` |
| 2 | Kill matrix | every feature killed by at least 3 cases in its own family; every restriction by at least 1 case or an enforcing check (2 by different routes where possible); a violating build fails as a case, never crashes the runner | mutants from patched tag source (DESIGN.md section 3); `kill_matrix.json` |
| 3 | Stub zoo | after filtering and netting, Z1-Z6 and N1-N4 each score 0.000; every stub's raw pass rate per family recorded | `checks/test_stubs.py` against the built verifier |
| 4 | Oracle and nop | the oracle (tag source patched to the agent's crates) 1.0 in two runs; nop 0 in two runs; a wrapper around the installed build scores 0 in the verifier | local, then the platform's baselines |
| 5 | Determinism | 3 runs plus 1 perturbed give byte-identical verdicts; the agent, verifier and recording images report the same `git --version` and produce the same bytes on a fixed sample | `recording.json` |
| 6 | Cue-word sweep | zero hits (section 4) on every agent-visible surface | `checks/test_cue_words.py` |
| 7 | Protection probe | as `dev`, inside the real image: read, copy, `ptrace`, `strace`, `gdb`, core dump, `LD_PRELOAD`, `/proc/<pid>/mem` and `/proc/<pid>/exe` all fail on the installed build; `id -u` is not 0; no `weave-*` source or crate anywhere readable | `probe.sh` written to the agent log by the oracle run |
| 8 | Verifier robustness | the verifier image builds in under 15 minutes; the offline build of the oracle plus every case finishes in under 30 minutes on 4 CPUs; a forced runner exception leaves no reward file | timing in `recording.json`; `checks/test_evaluation_errors.py` |
| 9 | Isolation | a submission that hangs on one case, forks without limit, prints 10 GB, writes outside its scratch directory, or plants files for the next case loses only those cases; `build.rs` and proc macros in the submission run as the dropped uid with no network and no view of private files | `checks/test_isolation.py` with hostile fixtures |
| 10 | No early stops | grep shows no task-side timer, kill or deadline before `timeout_sec` | `checks/test_no_timers.py` |
| 11 | Leak scan | no private case's inputs appear in any agent-visible file; no specification example is a private case or one edit away from one; no recorded output in the agent image | `checks/test_leaks.py` |
| 12 | Band check | M-gate scores 1 - w_F8 = 0.80 with only F8 moving; each other mutant moves only its own family; the duals keep the "always one box" stub at 0 net | `band.json` |

## 2. Coverage inventory: every documented feature and stated restriction gets cases that fail without it

**Features.** One id per rule of the specification (DESIGN.md section 7, chapters 1-15). Each id
records its family, the languages it applies to, and the mutant that removes it. The generator
targets at least 3 kept cases per id per applicable language; ids that apply to one language get at
least 3 in that language. A case lists every id it exercises; the matrix is checked both ways
(every case maps to ids; every id has its cases) at every build.

**Stated restrictions.** Each sentence with "only", "never", "at most", "must not" or an explicit
limit, in the instruction or the specification, becomes a restriction id with a case or an
enforcing check:

| Restriction (where stated) | Killed by |
| --- | --- |
| Called as `BASE OURS THEIRS -o OUT -l 7 -p PATH` (instruction) | every case uses that form; `-p` varies by case, so a driver that ignores it fails the hint and test-file cases |
| Exit 2 writes nothing (instruction, spec ch. 1) | binary and non-UTF-8 cases check that `OUT` does not exist |
| Binary means a NUL in the first 8,192 bytes of any input (spec ch. 1) | a NUL at byte 8,191 (status 2) and at byte 8,193 (merged) |
| Non-UTF-8 input is status 2 (instruction) | an invalid byte in ours only, in base only |
| Markers in an input: that input is the answer, status 1 (spec ch. 2) | markers in theirs only (take-theirs-like answer, but status 1, so Z2 fails) |
| Files up to 2 MB; the 1,000,000-byte route (instruction, spec ch. 2) | files just under the limit whose entity merge differs from git's; two cases near 2 MB |
| 10 seconds per merge (instruction) | the runner's limit; a slow-build check in `checks/` (a submission that sleeps 11 s fails the case, not the run) |
| Must not call the installed build (instruction) | the verifier image has no build; a wrapper scores 0 (gate 4) |
| Builds with `cargo build --release --offline` from the given crates (instruction) | the verifier builds offline with the same registry; a project that needs another crate fails to build |
| Standard error is free (instruction) | a stub that floods stderr passes the same cases as without it |
| No `WEAVE_*`, no git configuration, outside any repository (instruction) | the runner's environment; a case where a global `merge.conflictStyle` would change git's bytes shows that the runner really has none |
| Only `.py`, `.ts`, `.go`, `.json`, `.toml` (instruction) | no case uses another type; stated as a scope limit, not a restriction to kill |
| The rename constants and the 0.15 margin (spec ch. 4) | rename and non-rename duals on each side of each constant, at least 0.15 away |

**Stated but not graded.** "We will maintain this code for years: keep it modular" is a quality
request, worded as in Carve and BasedPL; it carries no credit. If the audit treats it as an
unchecked promise, the remedy is to keep it as context only, not to grade it.

## 3. The stub zoo

| Stub | Behaviour | Role |
| --- | --- | --- |
| Z1, Z2, Z3 | copy ours, theirs, or base; exit 0 | filter: drop every case any of them solves |
| Z4 | `git merge-file -p OURS BASE THEIRS`; exit 0 if clean, else 1 | filter |
| Z5 | `git merge-file -p --diff3 -L ours -L base -L theirs`, plus the hint on the first closing marker | filter |
| Z6 | `diffy` 0.5.2 diff3, plus the hint | filter |
| N1 | one whole-file box, frame cut, hint, exit 1 | net per family |
| N2 | nothing written, exit 2 | net |
| N3 | status 2 on a NUL or invalid UTF-8, else Z5 | net |
| N4 | Z5's text with exit 0 | net |
| N5 | Z5 with the hint dropped (a git merge without the driver's line) | net |
| V1 | v1-style engine: `sem-core`'s matcher, ours-skeleton placement, `diffy` inside definitions | calibration only (real partial work) |

The red-team lens (section 5, lens 5) adds any cheaper strategy it finds to the zoo before upload.

## 4. Cue-word sweep

**Surfaces:** `instruction.md`; every file under `/app/docs`; file and directory names in the agent
image (`find / -xdev` as `dev`); `weave-driver --help`, `--version` and the messages of every exit-2
path; the hint line; environment variables of `dev`'s login shell; the offline registry's
directory and file names; `task.toml` comments; the specification's examples. Not agent-readable
and so out of the sweep: the installed build's bytes, the verifier image.

**Word classes:** evaluat-, benchmark, grade/grader/graded/grading, score, test case, hidden,
held-out, reference, oracle, gold/golden, "told apart", indistinguishable, "exactly as", "identical
to", "behave exactly like", budget, deadline, session, verifier, corpus, rubric, probation, spike.

**Known residue and whitelist:**
- the installed build's `--help` says "verified" (exit 0's meaning) and the hint line says "'weave
  check' to verify your resolution": the product's own words, kept;
- "test files" in the element-union rule (`_test.go`, `test_*.py`, `.test.`, `.spec.`): domain
  sense, kept in the specification only;
- upstream's README, `docs/benchmarks.html`, `llms.txt` and CHANGELOG never ship (the README uses
  "benchmark" nine times);
- the harness's own process line, which no task can hide.

## 5. Twenty independent QA lenses

Each lens is a separate agent with its own brief and no other lens's findings, run after the first
local build, reports in harbor-lh. A must-fix from any lens blocks upload.

| # | Lens | Question | Pass when |
| --- | --- | --- | --- |
| 1 | Spec accuracy | does each rule match the tag's code? | a reader of `527ccb3` finds no wrong rule in a 60-rule sample and in all of chapter 12 |
| 2 | Spec sufficiency | can each kept case's answer be derived from the specification plus probing? | 50 random cases derived blind, every derivation path written |
| 3 | Inventory | is every rule an id, every id covered? | two-way matrix clean |
| 4 | Restrictions | is every stated limit killed or enforced? | section 2 table complete |
| 5 | Stub red team | can a cheap program earn credit? | best new stub nets 0.000 |
| 6 | Gate fairness | is every F8 refusal derivable, every dual valid, no case near an under-specified rule? | 100% of F8 reviewed |
| 7 | Heuristics | are constants published, margins at least 0.15, separator ties and box refinement stated exactly? | no case within the margin; every tie rule has a worked example |
| 8 | Layout | does a layout slip stay in F1's layout sub-family? | M-layout moves only that sub-family |
| 9 | Determinism | same bytes across runs, images, CPU counts and paths? | 3+1 identical; cross-image identical |
| 10 | Protection | can `dev` reach the build's bytes? | every route fails; `/proc` child lines noted as documented residue |
| 11 | Leaks | can a visible file reveal a case or its answer? | none |
| 12 | Awareness | does anything read as a test, by text or by setting? | a solver simulation reading only agent-visible text writes no assessment words |
| 13 | Instruction contract | is every requirement stated by what depends on it, consistent with the specification, without an unchecked promise? | no contradiction; no ungraded "must" |
| 14 | Verifier robustness | long offline build, hostile submissions, evaluation-error paths | no stale reward; no wrong 0 |
| 15 | Isolation and tampering | can submitted code, `build.rs` included, touch private files or the reward? | no |
| 16 | Oracle | does the patched upstream build reproduce the installed build on every kept case? | 100%, the patch documented |
| 17 | Difficulty | do mutants, proxies and V1 put F8 hardest and the total in band? | M-gate 0.80; F8 hardest per case; V1 well under the frontier band |
| 18 | Platform | preflight, content hash, idle full-length canary | graded within 43,200 s |
| 19 | Realism and provenance | would a lab reviewer find the story and the target credible? | no must-fix; licence notices shipped |
| 20 | End-to-end red team | one adversarial session trying every route to credit without a merge engine | reward 0 |

## 6. Post-run "good failure" checks (every model trial, before a score is reported)

1. The original scores 1.0 and every stub 0.000 on the same build (from `recording.json`).
2. No infrastructure error, no task-side stop, and no evaluation-awareness finding (read the
   verdict and, for any flag, the trajectory). A capped trial has a reward about 15 minutes after
   the cap; one without a reward is reported as lost, never as 0.
3. The agent was still working on merge rules when the turn ended (last hour of the trajectory),
   or ended by itself with the work stated as finished.
4. Failures cluster in named families; F8 is the lowest net family in most trials, and most failed
   F8 refusals were written as exit 0 (the sentence's mechanism), not as a wrong box.
5. Every failed case traces to a documented rule, and at least one other run or the oracle passes
   it; any case that no run passes and that QA cannot derive from the specification is re-examined
   before the score stands.
6. The delivered project built offline in the verifier; build failures are read before scoring
   (a candidate defect, but worth one look for an environment cause).
