# HarfBuzz forward-port, 14.3.0 → 15.2.0

**Status: Phase A, design only.** Nothing here is runnable yet: no environment, verifier, oracle or case exists,
and nothing has been built, downloaded or run for this task. Category: Library Reproduction
(`tasks/static/library_build/`). Branch `neel/harfbuzz-forward-port`.

A product ships HarfBuzz 14.3.0 and has frozen that build. The agent brings it forward to the shaping, layout,
metrics and API behaviour of upstream's next eight releases (14.3.1 to 15.2.0, 2026-08-13 to 2026-11-19), release
window by release window, working from the release notes, the specifications and its own test fonts. It never sees
a 15.x tree or binary. A separate verifier compiles the delivered tree and compares integer shaping and API outputs
on private fonts and strings with the upstream releases. Only behaviour a listed note changed is credited; behaviour
no note changed must stay as it was, and that is where agents are expected to fail.

| Document | Contents |
| --- | --- |
| [notes/DESIGN.md](notes/DESIGN.md) | What the agent gets and delivers, the hidden reference, cases and attribution, families, reward, stub filters, determinism, expected scores, effort, risks |
| [notes/STEPS.md](notes/STEPS.md) | The three-step chain, each step's acceptance criteria, timeouts, reward strategy, the single-step fallback, the panel decision |
| [notes/CLAIMS.md](notes/CLAIMS.md) | Every claim behind the task checked against primary evidence; the item inventory; the failure sentence and its proof plan |
| [notes/QA-PLAN.md](notes/QA-PLAN.md) | The 12-item pre-upload gate for this task, coverage inventory, stub zoo, cue-word sweep, 20 QA lenses, post-run checks |
| [notes/SPIKE.md](notes/SPIKE.md) | The spike that must pass before the build, and the exact download list |
| [notes/PHASE-A-REPORT.md](notes/PHASE-A-REPORT.md) | Phase A summary |

## Design dimensions (proposal stage)

| Dimension | Argument | Evidence so far | Open |
| --- | --- | --- | --- |
| Novelty | First SWE-M2 task that changes an existing C++ library, first text-shaping task, first forward-port. Release-notes upgrades exist (SWE-EVO, SWE-Chain, RoadmapBench) but on pre-cutoff Python releases graded by upstream tests; this one is post-cutoff, in OpenType and AAT shaping, graded by differential execution on private fonts | No shaping task among Forge's 664 tasks or this repository's tasks (read 2026-11-26) | Public-benchmark comparisons are second-hand (CLAIMS.md C9, C11) |
| Verifiability | Outputs are integer sequences; per-item upstream revert mutants prove each graded case belongs to one note; the unmodified base scores 0 by construction | Commit-level evidence in CLAIMS.md | Case yield per item, revert cleanliness, determinism: all spike items |
| Realism | Frozen, certified builds that take upstream fixes as their own changes are common practice; the notes are upstream's own, the specs are the ones a maintainer reads | Upstream's notes state rules as conditions precise enough to implement (CLAIMS.md C29) | The "no upstream diff" story has to read as natural (QA lens 1) |
| Difficulty | About 57 changes across 8 families in C++, AAT and `kern` fonts the agent must build itself, Unicode 18 tables to regenerate, no oracle for the new behaviour, and a gate that punishes over-broad fixes | Report's estimate: frontier 0.35-0.65, mid-tier 0.10-0.30 | Unmeasured; mid-tier floor risk |
| Initial feasibility | Every in-scope note is either stated precisely by upstream or restated by us as a behaviour rule; the base tree, its own tests and fontTools let the agent check its work against 14.3.0 for everything the notes leave alone | Example: the Khmer fix is a one-token change whose rule is quoted from Microsoft's spec in the 14.3.0 source itself | E-item restatements; fontTools has no `kerx` writer (our assembler) |

## Steps

Three steps in one sandbox, decided unanimously by a three-judge panel (notes/STEPS.md): 14.3.0 → 15.0.0 (9 units,
7,200 s), → 15.1.0 (13 new units, 7,200 s), → 15.2.0 (35 new units, 20,160 s). Each step's verifier re-checks every
unit released so far against that release, and the trial reward is the last step's (`final`). By design,
`hb_font_set_face()` changes between steps: step 1 asks for 15.0.0's behaviour (reset the font functions), step 3 for
15.2.0's (do nothing), so step 3 grades the later behaviour and does not count the change as a regression. A flat
single-step bundle with step 3's verifier is the fallback for harnesses that cannot run steps.

## Reward formula

Per step, over the units released up to that step: reward = D · G, where D is the mean over units of each unit's
pass fraction on its changed cases, and G = max(0, 1 − 0.25·(1 − h_d) − 0.10·(1 − h_b)) with h_d the pass fraction of
the held-fixed duals and h_b that of the broad held-fixed cases. The trial reward is the last step's
(`final`). A tree that does not build scores 0; a verifier fault leaves no reward. Details and rationale:
[notes/DESIGN.md](notes/DESIGN.md#6-reward).

## Hackability assessment

Phase A: no boundary has been tested. Every row is 🟡 YELLOW / UNASSESSED until the protection probe and the
stub zoo run (QA gate items 3 and 7).

| Attack | Boundary | Mitigation (designed, untested) | Severity |
| --- | --- | --- | --- |
| Read gold or case files from the tree's build scripts or library code during grading | Verifier container | Build and driver run as an unprivileged user; gold is root-only; comparison after the driver exits | 🟡 YELLOW / UNASSESSED |
| Obtain 15.x code or a newer HarfBuzz binary in the agent container | Agent image | Leak scan for every HarfBuzz library, header and version string; no network | 🟡 YELLOW / UNASSESSED |
| Earn credit without implementing anything (nop, stubs) | Reward | Held-fixed sets only gate; stub zoo must score 0.000 | 🟡 YELLOW / UNASSESSED |
| Key outputs on private fonts | Cases | The agent never sees them; fonts are Noto or ours | 🟡 YELLOW / UNASSESSED |
| Hang, fork or flood the verifier | Verifier | One process per font batch with limits and timeouts | 🟡 YELLOW / UNASSESSED |

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (all boundaries).

## Layout

```
README.md            this file (never shipped)
task.toml            draft: three steps, final reward (no step is implemented yet)
notes/               design documents (never shipped)
steps/<step>/        instruction.md (draft), tests/ and solution/ (empty until Phase B)
.gitignore           private material, generated oracle patches, experiments
```

Private material (cases, seeds, gold outputs, private fonts, the duals catalogue) lives in the git-ignored
`private/` working copy and is backed up as a git bundle in harbor-lh,
`ops/swe-marathon-v2/next-tasks/harfbuzz-forward-port-private/`.

## Development log

### 2026-11-26

- Phase A started from the library-picks brief and the forward-port research note. Created the branch from
  `origin/main` (`ff9359f`).
- Re-checked the research claims against the research clone of upstream, with lazy fetching disabled so nothing
  was downloaded: tags and dates, commit counts, AI-assistance trailers, the named revert commits, the test-line
  counts, the Khmer fix and its spec quote, the Unicode table generators and their inputs, the `fonupa` mapping,
  the new API declarations, and fontTools' table support (read from an installed copy's source, not run).
  Results and corrections in notes/CLAIMS.md.
- Wrote notes/DESIGN.md. Remaining Phase A deliverables are added in the entries below as they land.
- notes/CLAIMS.md: 40 claims; 22 verified (2 partly), 11 corrected, 6 unverified, 1 estimate. The 57-unit
  inventory with candidate upstream commits; the failure sentence's proof plan.
- notes/SPIKE.md: what is built where, the download list (nothing downloaded; every item needs the owner's OK),
  eleven pass/fail spike checks and a go/no-go rule.
- Three-judge panel (opus, sonnet, haiku): three steps by release window and the `final` reward, both unanimous;
  by majority, a capped oracle chain on the steps bundle before any model run. notes/STEPS.md, a draft `task.toml`
  (parses with Harbor's `TaskConfig`; every step sets its verifier timeout because Harbor otherwise defaults it to
  600 s), three draft instructions (cue-word sweep clean, ASCII only), and ignore rules in each step's `tests/`
  and `solution/`.
- notes/QA-PLAN.md: the twelve-item gate for this task, the coverage inventory, the stub zoo, the sweep, twenty QA
  lenses and the post-run checks.
- Private store started (git-ignored `private/`, the duals catalogue) and backed up as a bundle in harbor-lh.
- notes/PHASE-A-REPORT.md. Next: the owner's OK for the downloads and a Linux x86_64 build host, then the spike.
