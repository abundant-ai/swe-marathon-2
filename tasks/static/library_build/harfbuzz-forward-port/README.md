# HarfBuzz forward-port, 14.3.0 → 15.2.0

**Status: Phase B done, spike go, first build milestone reached (2026-11-27).** The task is single-step (owner,
2026-11-26). The pipeline builds every release, revert and mutant; the verifier image builds a delivered tree and
scores the first three families (11 units, 1,802 cases): upstream 15.2.0 scores 1.0, 14.3.0 and the pruned starting
tree 0.0. Not yet: the other 45 units' cases, the agent image build, the oracle patch. Category: Library
Reproduction (`tasks/static/library_build/`). Branch `neel/harfbuzz-forward-port`.

A product ships HarfBuzz 14.3.0 and has frozen that build. The agent brings it forward to the shaping, layout,
metrics and API behaviour of upstream's next eight releases (14.3.1 to 15.2.0, 2026-08-13 to 2026-11-19), in one
session, working from the release notes, the specifications and its own test fonts. It never sees a 15.x tree or
binary. A separate verifier compiles the delivered tree and compares integer shaping and API outputs
on private fonts and strings with the upstream releases. Only behaviour a listed note changed is credited; behaviour
no note changed must stay as it was, and that is where agents are expected to fail.

| Document | Contents |
| --- | --- |
| [notes/DESIGN.md](notes/DESIGN.md) | What the agent gets and delivers, the hidden reference, cases and attribution, families, reward, stub filters, determinism, expected scores, effort, risks |
| [notes/STEPS.md](notes/STEPS.md) | History: the three-step plan, parked by the owner on 2026-11-26; its step 3 is the task's grading |
| [notes/CLAIMS.md](notes/CLAIMS.md) | Every claim behind the task checked against primary evidence; the item inventory; the failure sentence and its proof plan |
| [notes/QA-PLAN.md](notes/QA-PLAN.md) | The 12-item pre-upload gate for this task, coverage inventory, stub zoo, cue-word sweep, 20 QA lenses, post-run checks |
| [notes/SPIKE.md](notes/SPIKE.md) | The spike that must pass before the build, and the exact download list |
| [notes/PHASE-A-REPORT.md](notes/PHASE-A-REPORT.md) | Phase A summary |
| [notes/PHASE-B-REPORT.md](notes/PHASE-B-REPORT.md) | Phase B: downloads, spike results (go), yield per unit, milestone, resource use |

## Design dimensions (proposal stage)

| Dimension | Argument | Evidence so far | Open |
| --- | --- | --- | --- |
| Novelty | First SWE-M2 task that changes an existing C++ library, first text-shaping task, first forward-port. Release-notes upgrades exist (SWE-EVO, SWE-Chain, RoadmapBench) but on pre-cutoff Python releases graded by upstream tests; this one is post-cutoff, in OpenType and AAT shaping, graded by differential execution on private fonts | No shaping task among Forge's 664 tasks or this repository's tasks (read 2026-11-26) | Public-benchmark comparisons are second-hand (CLAIMS.md C9, C11) |
| Verifiability | Outputs are integer sequences; per-item upstream revert mutants prove each graded case belongs to one note; the unmodified base scores 0 by construction | Commit-level evidence in CLAIMS.md | Case yield per item, revert cleanliness, determinism: all spike items |
| Realism | Frozen, certified builds that take upstream fixes as their own changes are common practice; the notes are upstream's own, the specs are the ones a maintainer reads | Upstream's notes state rules as conditions precise enough to implement (CLAIMS.md C29) | The "no upstream diff" story has to read as natural (QA lens 1) |
| Difficulty | About 57 changes across 8 families in C++, AAT and `kern` fonts the agent must build itself, Unicode 18 tables to regenerate, no oracle for the new behaviour, and a gate that punishes over-broad fixes | Report's estimate: frontier 0.35-0.65, mid-tier 0.10-0.30 | Unmeasured; mid-tier floor risk |
| Initial feasibility | Every in-scope note is either stated precisely by upstream or restated by us as a behaviour rule; the base tree, its own tests and fontTools let the agent check its work against 14.3.0 for everything the notes leave alone | Example: the Khmer fix is a one-token change whose rule is quoted from Microsoft's spec in the 14.3.0 source itself | E-item restatements; fontTools has no `kerx` writer (our assembler) |

## One step

The owner parked multi-turn on 2026-11-26, so the task is a single step: one instruction listing every note from
14.3.1 to 15.2.0, one 34,560 s session, and one verifier run at the end that checks all 56 units against 15.2.0
(the 15.0.0 note on `hb_font_set_face()` is superseded by 15.2.0's, so only the final behaviour counts). The
three-step plan the panel chose in Phase A stays in notes/STEPS.md as history; its step 3 is exactly this grading.

## Reward formula

reward = D · G, where D is the mean over the 56 units of each unit's pass fraction on its changed cases, and
G = max(0, 1 − 0.25·(1 − h_d) − 0.10·(1 − h_b)) with h_d the pass fraction of the held-fixed duals and h_b that of the
broad held-fixed cases. A tree that does not build scores 0; a verifier fault leaves no reward. Details and rationale:
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
task.toml            single step, 34,560 s, separate verifier checking RELEASE=15.2.0
instruction.md       the request, every note from 14.3.1 to 15.2.0
tests/               verifier skeleton: Dockerfile, test.sh, verify.py, driver/hbdrv.c
                     (private/, inputs/ and wheels/ are staged by packaging and git-ignored)
solution/            solve.sh applies the generated upstream patch (solution/private/, git-ignored)
scripts/             development tooling, never shipped: fetch_inputs.sh, pipeline/
notes/               design documents (never shipped)
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

### 2026-11-27

- Phase B started (owner's approval of the Phase A download list, relayed by the coordinator): every pinned input
  fetched into the durable cache by `scripts/fetch_inputs.sh`, 121 MB, with size and SHA-256 per file in the
  cache's `MANIFEST.tsv` (the emoji test file moved to `/Public/18.0.0/emoji/`; the script has both URLs).
- **Single step.** The owner parked multi-turn ("we dont have to promote multi-turn as well so make stuff
  likewise"). The `steps/` layout and the per-step `task.toml` entries are gone; the flat layout has `instruction.md`
  (every note from 14.3.1 to 15.2.0, cue-word sweep clean, ASCII only), `tests/` (the verifier skeleton, moved from
  `common/verifier/`) and `solution/` at the task root, and `task.toml` checks `RELEASE=15.2.0` in one 34,560 s
  session. Grading is the old step 3: all 56 units against 15.2.0 with the held-fixed duals gate. notes/STEPS.md
  is kept as history, marked parked.
- **Difficulty sizing.** The owner asked that the single session be "difficult enough"; target frontier at most
  about 0.6. notes/DESIGN.md section 13 keeps the dual gate at full strength (weight never below 0.25), keeps the
  AAT and `kern` families, drops no hard but fair note, and estimates frontier ≈ 0.48 (0.36-0.60) and mid-tier
  ≈ 0.12-0.30, with how each yield-driven cut would move it.
- Upstream's `CLAUDE.md` is a symlink to `AGENTS.md`, whose rules (narrow changes, preserve behaviour) fit the work
  order: kept, without its `perf/: benchmarks` line. `CODE_OF_AI_CONDUCT.md` ("Do not fabricate benchmarks") and
  `test/vector/README.md` ("golden files") join the prune list.
- **Spike: go.** S2: the product build takes 15-31 s on 4 CPUs (arm64), and outputs are identical with and without
  ragel. S3: the driver reproduces all 16 of upstream's new Khmer expectations. S6: 49 of 56 units revert cleanly.
  S7: a 14.3.0 tree regenerated from the shipped Unicode 18 files matches 15.0.0's Unicode properties on every code
  point. S8: the verifier builds a tree and runs 1,802 cases in 27 s. S10: three runs and a perturbed fourth are
  byte-identical; no-FMA and emulated amd64 give the same outputs. Yield: 51-855 attributable changed cases for
  each of the 11 units measured; no unit cut, so the difficulty estimate stands.
- What the first sweep taught: HarfBuzz applies `trak` only with `STAT`, and prefers `GPOS` over `kerx` only when
  `GSUB` is present too, so our fonts now have those tables; Noto Sans Bengali's `init` covers the E and AI signs;
  the Hangul note is about the beginning-of-text flag. Generators leave out what 15.2.0 changes beyond a note.
- Upstream's `gen-ucd-table.py` needs `lxml`; the agent and pipeline images now install Ubuntu's `python3-lxml`.
- The instruction now says the product passes each run's surrounding text as context.
- Milestone: 15.2.0 scores 1.0 (also on amd64, emulated), 14.3.0 and the pruned starting tree 0.0. The private
  selection and its salt are in the private store and its harbor-lh bundle. notes/PHASE-B-REPORT.md has the
  numbers and the next steps.
