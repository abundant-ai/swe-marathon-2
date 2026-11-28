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

## Verification

A separate verifier image (no network) builds `/app/driver` with `cargo build --release --offline`
as an unprivileged uid with `no_new_privs` and bounded resources. It then runs every private case
(6,329) once:
- each case runs in a fresh root-owned directory outside any repository, with fixed `HOME` and
  `TMPDIR`, the pinned `git` and no git configuration;
- each case is limited to 10 s and a 4 GB address space;
- a case passes when the exit status and the output digest equal the recorded ones.

Before grading, the verifier makes sure nothing submitted can change the result:
- it checks the delivery against the root collect hook's manifest (`environment/weave-collect/collect`):
  - a file lost in transfer is an evaluation error;
  - files changed after the end are refused;
- it refuses files of the original's own published source or builds, by digest;
- every process of the uid is killed before any result is read;
- root's PATH is checked to hold nothing a non-root user can write;
- `metrics.json` and `reward.txt` are written last, with `O_EXCL`.

Details: `notes/DESIGN.md`, `notes/PHASE-C-REPORT.md`.

### Reward formula

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

Highest unresolved severity: 🟡 YELLOW (row 7 is a stopgap; the real fix is Harbor's; rows 5, 6
and 8 await their image re-runs).

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Read, copy, trace or dump the installed build | File mode, setgid, non-dumpable | Probe as `dev` in the real agent image: read, copy, `/proc/pid/mem`, `/proc/pid/exe`, gdb attach and core dump refused; `LD_PRELOAD` ignored | `root:weaveorig` mode 2711, stripped, no source or cargo cache in the image | Child `git merge-file` command lines are visible in `/proc` (the spec states them anyway) | QA lens | 🟢 GREEN |
| 2 | Deliver a wrapper that calls the installed build | Separate verifier image | A wrapper scores 0.0 | No original in the verifier image; the submission is rebuilt from source | None known | n/a | 🟢 GREEN |
| 3 | Pass cases with trivial programs | Case filter and netting | 15 stub programs net 0.0000; no-op and copy-ours crates score 0.0 through the verifier | Stub-reproduced cases dropped, or kept only where they grade a stated rule and netted; paired accept-duals in the gate family | Combinations of trivial rules not in the zoo | QA lens (cheap partial credit) | 🟢 GREEN |
| 4 | Read recorded outputs or seeds | Verifier image, permissions | The agent image holds no private or recorded file; the leak scan finds nothing in 33 public files | Private inputs only in the verifier image, root 0700 | None known | n/a | 🟢 GREEN |
| 5 | Forge the reward, or force an evaluation error | Dropped uid, kill sweep, root-only logs | A forger (build.rs and runtime writes, links, a FIFO, a daemon) once left `reward.json` behind on the error path; fixed (see the dev log), re-run pending | `/logs/verifier` made root's 0755; thread-aware kills of the uid; every error path clears the reward names; reward written last with `O_EXCL` | None known after the fix | Forger re-run | 🟡 YELLOW until re-run |
| 6 | Root runs a planted `tar`, `gzip` or `su` through PATH | Image PATH | Build-time gate in both images; runtime check in `verify.py`; a plant-tar canary | Explicit `ENV PATH`; `chmod -R go-w` on every PATH directory | None known | Canary run | 🟡 YELLOW until the canary run |
| 7 | A process left behind fetches the original after the turn (egress window) and drops it into `/app/driver` | Root collect hook, tripwire | Window confirmed open on the platform (2026-11-19 canary) | Root hook kills every non-root process and records egress and processes; manifest with ctimes; late files refused; 234 digests of the original's sources and builds refused | A transformed drop-in in the seconds between the turn's end and the hook | Platform fix (keep the agent-phase network policy through collection); trial audit | 🟡 YELLOW |
| 8 | A FIFO, device or outward link truncates the transfer (honest work scores 0) | Root collect hook, manifest | Local test through the pinned Harbor's `tar_transfer.py`: without the hook the tree arrives cut, with it whole | The hook removes such entries; a file missing against the manifest is a lost run, not 0 | Harbor versions differ in their extraction | Hook run in the real image | 🟡 YELLOW until the image run |
| 9 | Infer an evaluation from the text | Instruction, docs, help text, hook | Cue-word sweep: 0 hits | Requester voice; no comparison framing | The harness's own process line | First trajectories | 🟢 GREEN |

Licence: upstream is dual MIT OR Apache-2.0 (`weave` and `sem-core`); both licence files ship
with the documentation and the solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| Claims re-checked against primary evidence | 2026-11-26 | `notes/VALIDITY.md` |
| Determinism 3+1, stub filter and netting, mutants, oracle, amd64 sample | 2026-11-27 | 0 of 3,910 unstable; 2,388 kept; 11 stubs net 0; M-gate 0.75 (gate family only); oracle 3,910/3,910; amd64 200/200 (`notes/PHASE-B-REPORT.md`) |
| Specification accuracy | 2026-11-27 | 16 chapters, 14,964 words; three independent reviews of every chapter against the tag, all findings fixed (harbor-lh `ops/swe-marathon-v2/qa/weave/`) |
| First build milestone (agent and verifier images, reference 1.0, empty 0) | 2026-11-27 | reached: agent image builds the original from the pinned tag; verifier gives the upstream solution 1.0 and an empty submission 0; core-dump route refused (`notes/PHASE-B-REPORT.md`) |
| Phase C gate (inventory, kill matrix, stub zoo, determinism, sweeps, leak scan, calibration, preflight) | 2026-11-28 | 6,329 kept of 8,990; 0 unstable; 15 stubs net 0; M-gate 0.75 (F8 only); 22 of 23 features moved by their mutant in 3+ cases; every case tied to a stated rule; preflight passes; closing image checks pending (`notes/PHASE-C-REPORT.md`, `notes/COVERAGE.md`) |
| `harbor check` | none | not run |

## Remaining work

The closing Docker checks of Phase C, queued behind the shared lock (`notes/PHASE-C-REPORT.md`
section 6):
- the image sweep;
- the hook on a cluttered delivery, through a `filter="data"` extraction;
- the forger, hostile-submission, plant-tar and non-UTF-8 re-runs;
- the relaxed-superset mutant.

Then the 20+ independent QA passes (`notes/QA-PLAN.md`), and Oddish oracle and nop baselines and
pre-trial QA before any agent trial.

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

### 2026-11-27

Phase B: downloads, the probation spike and the first build milestone (`notes/PHASE-B-REPORT.md`).

- Downloads with checksums: the v0.7.1 tag source, the official x86_64 release binary, Rust 1.100.0
  for arm64 and `sem-core` 0.29.0's source. The crates come from the tag's lock, verified by cargo.
- The four probation checks pass:
  - the 3+1 runs are byte-identical on 3,910 candidates;
  - 2,388 cases are kept and all 11 stubs net 0;
  - M-gate scores 0.75 and moves only the gate family;
  - the specification has 16 chapters in 14,964 words (29.9 pages).
- The oracle, the upstream source built only from the agent's 64 crates, matches the reference on
  every candidate.
- The owner parked the chains (single step) and asked for the difficulty sizing in
  `notes/DESIGN.md` section 8.

### 2026-11-28

Phase C (`notes/PHASE-C-REPORT.md`).

- The generator gained 51 recipes. There are 8,990 candidates and 6,329 kept cases, and 0 are
  unstable across 3+1 runs.
- 30 feature-removal mutants were built and run; the kill matrix is in `notes/COVERAGE.md`.
- The stub zoo grew to 15 programs, all at 0 net.
- The brief was rewritten in the requester's voice and the sweeps are clean.
- The verifier was hardened.
- From Dogwood's QA: the root PATH gate, a root collect hook with a manifest and a tripwire,
  thread-aware kills, `/proc` read as bytes, and iterative trees.
- A hostile run found that a forger's reward files survived on the evaluation-error path; that is
  fixed.
- The flat bundle passes `oddish preflight`.
- The closing image checks wait for the shared lock.

