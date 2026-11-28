# Phase A report: HarfBuzz forward-port, 14.3.0 → 15.2.0 (2026-11-26)

> **Superseded in part, 2026-11-26:** the owner parked multi-turn, so the three-step layout below became the
> single-step task (one instruction, one 34,560 s session, graded as step 3). See the README and notes/DESIGN.md.

Phase A delivered the design, the three-step plan with its acceptance criteria, the claim check, the QA plan and the
spike plan with its download list. Nothing was downloaded, built or run, and neither Oddish nor Docker was used. The
upstream clone was read with lazy fetching disabled. The pick survives the claim check, but three findings make the
build harder than the report assumed: fontTools cannot write `kerx`, upstream generated its Unicode 18 tables from
pre-release data, and the new API needs declarations the notes do not give. The spike has to retire the first two
before anything is built.

## Panel decision

Three judges (opus, sonnet, haiku) voted independently on one brief. Votes and decision are in harbor-lh,
`ops/swe-marathon-v2/decisions/2026-11-26-harfbuzz-forward-port-steps-{BRIEF,opus,sonnet,haiku,DECISION}.md`.

| Question | Votes | Decision |
| --- | --- | --- |
| Layout | A, A, A | **Three steps by release window**, flat single-step bundle as the fallback |
| Reward strategy | final ×3 | **`final`**: the trial reward is step 3's, equal to the flat score |
| Platform proof before any model run | C, B, B | **B**: the oracle chain with every step held to its cap, all three steps graded 1.0 |

Ten guards from the votes were adopted (decision file). The main ones: the release is read from the step's
verifier environment, never from the tree; the three `tests/` are byte-identical; every instruction repeats the
earlier notes; and the switch rule moves to two steps or flat if non-agent time exceeds half the 8,640 s margin.

## Steps and acceptance criteria

| Step | Units | Agent / verifier `timeout_sec` | Oracle | Nop | Other must-pass items |
| --- | --- | --- | --- | --- | --- |
| `01-releases-14.3.1-to-15.0.0` | 9 (window A) | 7,200 / 2,400 | 15.0.0 tree, 1.000 ×2 | 0.000 ×2 | Stub zoo 0; each R_k ≥3 own kills, 0 elsewhere; 3+1 determinism; fail-soft on an unbuildable tree |
| `02-release-15.1.0` | 22 (9 re-checked + 13) | 7,200 / 2,400 | 15.1.0 tree, 1.000 ×2 | 0.000 ×2 | As step 1, plus the carry-over stub (15.0.0 tree) at its predicted ≈0.41; API units isolated in their own driver |
| `03-release-15.2.0` | 56 (47a's cases move to 47b) | 20,160 / 2,400 | 15.2.0 tree, 1.000 ×2 | 0.000 ×2 | As step 1, plus carry-over ≈0.375; mutant W in 0.60-0.85 with a single-family signature; flat parity |

Expected agent rewards (estimates): step 3, the trial reward, is about 0.35-0.65 for frontier models and 0.10-0.30
for mid-tier. Steps 1 and 2 are diagnostics. Details: [STEPS.md](STEPS.md).

## Claim validity

40 numbered claims in [CLAIMS.md](CLAIMS.md), C40 raised by the panel's opus judge and checked the same day:

- **22 verified**, 2 of them partly;
- **11 corrected**;
- **6 unverified**, all external pages or files not on disk, each with a named check;
- **1 estimate** (horizon, score bands and build cost).

The corrections that matter:

| Claim | Correction |
| --- | --- |
| C5 cutoff gap "2 to 5.6 months" | 1.3-4.7 months if Claude's "June 2026" means the end of June; graded commits run 2026-08-09 to 2026-11-19 UTC |
| C6 "about 45 gradable items" | 50 in-scope notes, 57 units; 45 is a floor the spike may reach, not a count |
| C7 "pinned by the notes" | Not for the three new-API notes; the instructions now carry their declarations |
| C10 "five expectation lines changed" | Two are expectations; three are comments or directives |
| C15 "first C++ task" | First task that changes an existing C++ library (`openfoam-rebuild` is a C++ rebuild) |
| C28 fontTools AAT support | `morx`, `mort` and `trak` yes; **no `kerx` module**, and `kern` beyond format 0 is raw bytes, so we need our own assembler |
| C30 `CBDT` format 19 out | Back in: a public `CBDT` format that fontTools writes |
| C33, C40 Unicode 18 "P with UCD" | Upstream used pre-release 18.0 files plus `DerivedCoreProperties` 17.0.0, and changed Microsoft's USE override files. Ship those versions, or drop the code points that differ |
| C34, C39 toolchain | packTab is required; ragel 6.10 regenerates machines at build time when present, so both images need it |

New finding: upstream's 14.3.0 root has `CLAUDE.md`, `AGENTS.md` and `CODE_OF_AI_CONDUCT.md`. claude-code loads
`CLAUDE.md` as instructions, so these are read and judged before shipping (QA lens 19).

## Failure sentence and its proof plan

"Agents reproduce each release note's new behaviour on the sequences it describes but apply the rule beyond its
stated condition, so neighbouring sequences that upstream left unchanged regress."

- **Documented.** The conditions are verbatim in the notes. The instruction says unchanged behaviour stays. The
  agent's own 14.3.0 build is an oracle for every neighbour case. Item 4's spec rule is even quoted in the 14.3.0
  source.
- **Plausibly missed.** The fixes are narrow: #6735 is one token, and 8 of its 16 upstream cases passed before it.
  No oracle exists for the new behaviour, and checking neighbours needs a second build and a diff. Later steps
  revise earlier code.
- **Provable.** Mutant W widens 16 conditional units' guards. Before any run it must score D ≥ 0.98 and h_d ≤ 0.5,
  keep h_b and every family ≥ 0.95, and land in 0.60-0.85 with a signature no revert shares.
- **After runs.** The sentence holds if the dual failure rate on implemented units is at least 15% and at least
  three times the rate on untouched ones, in two of the first three accepted runs.

**Verdict: valid as a hypothesis, not yet established.** The competing explanation is throughput: agents may never
reach the AAT and `kern` units, which need self-built fonts. The fallback sentence for that case is written, with
F4 as its B family and R_F4 as its mutant (about 0.84).

## Download list (all pending the owner's OK)

| Group | Items |
| --- | --- |
| HarfBuzz | Release tarballs 14.3.0, 15.0.0, 15.1.0 and 15.2.0 (~20 MB each); history from 14.3.0 to 15.2.0 (~100-300 MB, build host) |
| Fonts (OFL) | Noto Sans and Serif Khmer, Myanmar, Devanagari, Bengali, Balinese, Javanese, Tai Tham, KR (subset), Hebrew, Syriac, Naskh and Sans Arabic, Sans and Serif variable (~15-25 MB) |
| Python | fontTools (~5 MB), packTab (<0.1 MB), meson (~2 MB); never uharfbuzz or anything bundling HarfBuzz |
| System | `ubuntu:24.04` at Goose's digest (~30 MB); gcc/g++ 13, pkg-config, ninja, Python, git (~250 MB); ragel 6.10 (~1 MB); GLib development files for the agent (~10 MB) |
| Documents | Unicode 18.0.0 UCD (~7 MB) at upstream's versions plus `DerivedCoreProperties` 17.0.0; `ucd.nounihan.grouped.zip` (~1.5 MB); emoji 18.0 data (~1 MB); IANA subtag registry (~0.9 MB); OpenType language tags (~0.3 MB); the OpenType pages (~5-10 MB); Microsoft's script documents (~2 MB); Apple's AAT table pages (~1-2 MB); UAX #29 (~0.3 MB); Microsoft's USE override files at `cdbe72ca` (~10 KB) |

URLs, reasons and where each is used: [SPIKE.md](SPIKE.md). All builds of downloaded code run on a Linux x86_64
build host in the verifier's pinned image, never on the laptop.

## Commits on `neel/harfbuzz-forward-port`

| Commit | Deliverable |
| --- | --- |
| `9e926bd` | DESIGN.md, README with development log, ignore rules |
| `b4059bd` | CLAIMS.md: validity table, item inventory, failure-sentence proof plan |
| `ab1d2f3` | SPIKE.md: spike checks and download list; claim C40 |
| `8005db9` | STEPS.md, draft `task.toml`, three draft instructions, `tests/` and `solution/` ignore rules |
| `e082e7b` | QA-PLAN.md |
| this commit | PHASE-A-REPORT.md and the README's log |

In harbor-lh's ops folder: the panel brief, three votes and the decision, and the private store's backup bundle
(`next-tasks/harfbuzz-forward-port-private/`, holding the duals catalogue).

## Notes for the coordinator

- `task.toml` is a draft listing three planned steps. The repository's rule that only implemented steps belong
  there applies from Phase B; nothing packages this task yet.
- The task name `swe-m2_software-engineering_harfbuzz-forward-port` follows Goose and BasedPL; the owner may prefer
  another field.
- The author entry matches the other tasks on `main`. The notes name no individual.
- Open before Phase B: the owner's OK for the downloads, a free Linux x86_64 build host, and the v2 tracker entry
  (left to the coordinator).
