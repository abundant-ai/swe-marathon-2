# Weave merge-driver rebuild

A clean-room rebuild of `weave-driver` 0.7.1 (Ataraxy Labs, MIT OR Apache-2.0), an entity-level git
merge driver, for Python, TypeScript, Go, JSON and TOML. The agent gets an execute-only build, our
written specification and an offline Rust registry with the entity extractor the driver is built
on (`sem-core` 0.29.0) and `diffy` 0.5.2. It delivers a Rust project whose binary writes the same
merged file, byte for byte, and exits with the same status. The engine being rebuilt was first
published between August and October 2026: the v2 matching and placement engine on 2026-08-12,
and the fail-closed gate, the region rules and the element union in 0.6.0 on 2026-10-19.

**Status: Phase A (design only), on probation.** Nothing has been downloaded, built or run. The task
becomes the third library-reproduction pick only if a three-day spike passes four checks
(`notes/SPIKE-PLAN.md`). The first upload will be a single step (flat layout); a two-step chain is
designed and is adopted only if the spike's measurements meet the judges' conditions
(`notes/STEPS.md`).

## Where things are

| File | What it holds |
| --- | --- |
| `instruction.md` | Draft request, in the requester's voice |
| `task.toml` | Draft configuration, single step |
| `tests/`, `solution/` | Empty in Phase A; private material goes in their Git-ignored `private/` |
| `notes/DESIGN.md` | What the agent gets and delivers, the hidden original, families and weights, stub filters, determinism, score bands, effort, risks, scope cuts, the specification we must write |
| `notes/STEPS.md` | The panel decision, the step designs, each step's acceptance criteria |
| `notes/VALIDITY.md` | Every claim behind the task re-checked against primary evidence; the failure sentence and its mutant proof plan |
| `notes/QA-PLAN.md` | The 12-item pre-upload gate, coverage inventory, stub zoo, cue-word sweep, 20 QA lenses, post-run checks |
| `notes/SPIKE-PLAN.md` | The probation spike and the exact download list |
| `notes/steps/` | Draft instructions for the candidate two-step chains (proposals, not implemented steps) |
| `notes/PHASE-A-REPORT.md` | Phase A summary |

## Design dimensions (Phase A; ratings unassessed, no `harbor check` run)

### Novelty
No merge engine appears among ProgramBench's targets, FrontierSWE's tasks or the 664 Forge tasks
(local search: the only name matches are `implement-diff`, `bsdiff`, `implement-jsonpatcher` and two
gitleaks tasks; no instruction mentions three-way merges, diff3 or merge drivers). Conflict
datasets (ConGra, Merge-Bench) grade resolving conflicts, not reproducing an engine. Nothing in this
repository is a merge engine. The external comparisons are the deep dive's and were not re-fetched.

### Verifiability
Exact: the output file's bytes and the exit status, per case, against outputs recorded from the
pinned original under a pinned `git`. Partial progress is the per-family pass rate. Determinism is
claimed upstream (law L6, property-tested) and must be shown on the platform (3 runs plus 1
perturbed).

### Realism
Multi-agent coding produces merge conflicts at scale (Cursor's old swarm harness: 68,000 commits in
its first two hours, more than 70,000 conflicts before it was paused). The driver's fail-closed gate
exists because two features that each added `case 3:` to one Go switch "merged clean and broke the
build twice in a multi-agent run". A clean-room rewrite from a specification and a running binary is
how compatible second implementations are made.

### Difficulty
About 16.5-17k code-only lines of merge logic with entity extraction supplied (measured on the
cloned tree); undocumented heuristics that our specification must publish; byte dependence on
`diffy` and `git merge-file`; a gate whose refusals are low-frequency, multi-language and against
the prior that line-disjoint edits merge clean. Sized in Phase B to the owner's target (frontier at
or below about 0.6, mid-tier 0.1-0.4): expected about 0.55 frontier and 0.29 mid-tier, untested
(`notes/DESIGN.md` section 8).

### Initial feasibility
Solvable by construction if the upstream source, built against exactly the agent's crates and
features, reproduces the installed build on every kept case. That is a spike check, not yet run.

## Workload

One step, `timeout_sec` 34,560 (9.6 h); the instruction states no time budget. The two-step chain
drafts in `notes/STEPS.md` were parked by the owner on 2026-11-26 and are kept as history only.

## Verification (planned)

One process per case, with a timeout, in a scratch directory outside any repository, with a fixed
`HOME`, `TMPDIR`, the pinned `git` and no git configuration; the submission is built from source
offline with the same toolchain and registry. A case passes when the exit status and the output
bytes (or the absence of output, for status 2) equal the recorded ones. Details:
`notes/DESIGN.md`.

### Reward formula (draft)

```
p_f = cases passed in family f / cases kept in family f
s_f = the best stub's pass rate in family f (measured at each build)
g_f = max(0, (p_f - s_f) / (1 - s_f))
reward = sum over families f of w_f * g_f
```

Ten families; the fail-closed gate carries 25%. Denominators are fixed per build. No submission or
a submission that does not build: reward 0. An infrastructure fault is an evaluation error and
leaves no reward file. Weights and families: `notes/DESIGN.md`.

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (Phase A; nothing built).

| # | Attack and impact | Boundary | Evidence | Mitigation (planned) | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read, copy, trace or dump the installed build | File mode, setgid, non-dumpable | None yet | `root:<group>` mode 2711, stripped, no source or cargo cache in the image | Child `git merge-file` command lines are visible in `/proc` (documented instead) | Protection probe as the agent user | 🟡 YELLOW / UNASSESSED |
| 2 | Deliver a wrapper that calls the installed build | Separate verifier image | None yet | No original in the verifier image; the submission is rebuilt from source | None known | Oracle-wrapper probe scores 0 | 🟡 YELLOW / UNASSESSED |
| 3 | Pass cases with trivial programs (take ours, take theirs, `git merge-file`, always one box, always exit 2) | Case filter and stub netting | None yet | Stub-solved cases dropped; per-family netting; paired accept-duals in the gate family | Combinations of trivial rules | Stub zoo at 0.000 | 🟡 YELLOW / UNASSESSED |
| 4 | Read recorded outputs or seeds | Verifier image and permissions | None yet | Private inputs only in the verifier image, root-only | None known | Permission probe | 🟡 YELLOW / UNASSESSED |
| 5 | Tamper with reward files; force an evaluation error | Separate verifier container | None yet | Submitted code runs as a dropped uid; reward written last | None known | Adversarial QA lens | 🟡 YELLOW / UNASSESSED |
| 6 | Infer an evaluation from the text | Instruction, docs, help text | Cue-word sweep of the draft instruction (clean) | Requester voice; no comparison or grading vocabulary | The harness's own process line | First trajectories | 🟡 YELLOW / UNASSESSED |

Licence: upstream is dual MIT OR Apache-2.0 (`weave` and `sem-core`); both licence files ship
with the documentation and the solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| Claims re-checked against primary evidence | 2026-11-26 | `notes/VALIDITY.md` |
| Builds, cases, mutants, oracle, determinism | none | not run (Phase A) |
| `harbor check` | none | not run |

## Remaining work

The probation spike (`notes/SPIKE-PLAN.md`) after the owner approves the download list; then the
specification, the case generator and filters, the mutants, the verifier, the images, QA
(`notes/QA-PLAN.md`) and the platform baselines.

## Development log

### 2026-11-26

Phase A design. What was done:

- Read the coordinator's brief, the library-picks report, the Weave deep dive, the grading guide
  (sections 12-13) and the sizing note.
- Read the deep dive's shallow clones read-only (`weave` at `e52ba82`, `sem` at `e98c27d`); nothing
  was built or run. Re-checked dates, tags, releases and file histories through the GitHub API,
  crate versions and sizes through the crates.io API, and the Hacker News and Cursor figures.
- Findings that change the plan: the gate shipped in 0.6.0, not 0.7.1, so the suggested split
  "0.6 engine, then 0.7.1's gate" has almost nothing in its second step (about 120 merge-path lines
  in 0.7.0, none in 0.7.1); the deep dive read a commit nine commits after the v0.7.1 tag whose
  `verify.rs` differs for TypeScript, so the specification must come from the tag (527ccb3);
  crates.io stops at 0.7.0; a refusal whose fallback is git's own conflict is reproducible by a
  trivial stub, so the gate family is made of whole-file refusals plus paired accept-duals; one
  more undocumented matching constant (`REHOME_MIN_OVERLAP` = 0.6). Details in `notes/VALIDITY.md`.
- A three-judge panel (opus C, sonnet B, haiku A) split three ways; the tie rule gives a single
  step first, with the chain decided on measured evidence
  (harbor-lh `ops/swe-marathon-v2/decisions/2026-11-26-weave-merge-driver-rebuild-steps-DECISION.md`).
- Wrote this skeleton: the draft instruction, the draft `task.toml` and the ignore rules.

Not done: no download, build, run, case, mutant or platform action. Next: the owner's approval of
the spike's download list.

Later the same day, the Phase A deliverables were completed:

| Commit | Deliverable |
| --- | --- |
| `0135866` | `notes/DESIGN.md` |
| `3ab158a` | `notes/STEPS.md` and the chain drafts |
| `03cb1e9` | `notes/VALIDITY.md`: 43 claims, 21 verified, 14 corrected, 1 invalid, 7 unverified |
| `5dca4a2` | `notes/QA-PLAN.md` |
| `a1c992d` | `notes/SPIKE-PLAN.md`: 222 crates, 50.3 MB in all; the agent's registry is 82 crates, 14.5 MB |

`notes/PHASE-A-REPORT.md` summarises them. Checks actually run:

- the instruction and all four step drafts were swept for cue words, with zero hits;
- `task.toml`, and a chain fragment, were parsed with Harbor's `TaskConfig`;
- the crate closures were computed from the clone's `Cargo.lock`, and their sizes looked up on
  crates.io.
