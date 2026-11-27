# HarfBuzz forward-port, 14.3.0 → 15.2.0

**Status: QA fix round 1 done (2026-11-28).** Single-step (owner, 2026-11-26). 53 of 57 units are graded on 5,256
private cases (four cut, with reasons in notes/DESIGN.md). Through the amd64 verifier image: the reference solution
scores 1.0, the untouched tree 0.0, every stub 0.0 (the no-op API stub too), the verification-gap mutant V 0.685
(D 0.685, h_d 1.000, h_b 1.000; band 0.60-0.85) and the over-broad mutant W, now a secondary bound, 0.678 (D 0.985,
h_d 0.691, h_b 0.977); hostile and drop-in trees 0.0; slow and hanging trees still get their reward at the
1,800 s deadline. Local preflight passes on the flat bundle. Next: the QA re-check passes; no Oddish run before
the owner says so. Category: Library Reproduction (`tasks/static/library_build/`). Branch `neel/harfbuzz-forward-port`.

A product ships HarfBuzz 14.3.0 and has frozen that build. The agent brings it forward to the shaping, layout,
metrics and API behaviour of upstream's next eight releases (14.3.1 to 15.2.0, 2026-08-13 to 2026-11-19), in one
session, working from the release notes, the specifications and its own test fonts. It never sees a 15.x tree or
binary. A separate verifier compiles the delivered tree and compares integer shaping and API outputs
on private fonts and strings with the upstream releases. Only behaviour a listed note changed is credited, and
behaviour no note changed must stay as it was. Where agents are expected to fail: with no 15.x code or tests to
check against, they land the fixes they can confirm on their own 14.3.0 build and fall short on the ones they
cannot, chiefly AAT/`kern` behaviour that needs hand-built fonts, regenerated Unicode data, and bugs a note
describes only by symptom.

| Document | Contents |
| --- | --- |
| [notes/DESIGN.md](notes/DESIGN.md) | What the agent gets and delivers, the hidden reference, cases and attribution, families, reward, stub filters, determinism, expected scores, effort, risks |
| [notes/STEPS.md](notes/STEPS.md) | History: the three-step plan, parked by the owner on 2026-11-26; its step 3 is the task's grading |
| [notes/CLAIMS.md](notes/CLAIMS.md) | Every claim behind the task checked against primary evidence; the item inventory; the failure sentence and its proof plan |
| [notes/QA-PLAN.md](notes/QA-PLAN.md) | The 12-item pre-upload gate for this task, coverage inventory, stub zoo, cue-word sweep, 20 QA lenses, post-run checks |
| [notes/SPIKE.md](notes/SPIKE.md) | The spike that must pass before the build, and the exact download list |
| [notes/PHASE-A-REPORT.md](notes/PHASE-A-REPORT.md) | Phase A summary |
| [notes/PHASE-B-REPORT.md](notes/PHASE-B-REPORT.md) | Phase B: downloads, spike results (go), yield per unit, milestone, resource use |
| [notes/PHASE-C-REPORT.md](notes/PHASE-C-REPORT.md) | Phase C: every unit, the failure-sentence proof, recorded outputs, images, the gate |
| [notes/PREREGISTRATION.md](notes/PREREGISTRATION.md) | Per-unit and per-family prediction for a frontier agent, with kill conditions, committed before any run |
| [notes/FIX1-REPORT.md](notes/FIX1-REPORT.md) | QA fix round 1: every must-fix and should-fix item, what changed, the evidence |

## Design dimensions (proposal stage)

| Dimension | Argument | Evidence so far | Open |
| --- | --- | --- | --- |
| Novelty | First SWE-M2 task that changes an existing C++ library, first text-shaping task, first forward-port. Release-notes upgrades exist (SWE-EVO, SWE-Chain, RoadmapBench) but on pre-cutoff Python releases graded by upstream tests; this one is post-cutoff, in OpenType and AAT shaping, graded by differential execution on private fonts | No shaping task among Forge's 664 tasks or this repository's tasks (read 2026-11-26) | Public-benchmark comparisons are second-hand (CLAIMS.md C9, C11) |
| Verifiability | Outputs are integer sequences; per-item upstream revert mutants prove each graded case belongs to one note; the unmodified base scores 0 by construction | Commit-level evidence in CLAIMS.md | Case yield per item, revert cleanliness, determinism: all spike items |
| Realism | Frozen, certified builds that take upstream fixes as their own changes are common practice; the notes are upstream's own, the specs are the ones a maintainer reads | Upstream's notes state rules as conditions precise enough to implement (CLAIMS.md C29) | The "no upstream diff" story has to read as natural (QA lens 1) |
| Difficulty | 53 graded changes across 8 families: 14 whose note names the fix, 20 an agent can check on its own 14.3.0 build, and 19 it cannot without fonts or data it builds itself (AAT and `kern` tables no shipped font has, the Unicode 18 data, bugs described only by symptom); no oracle for the new behaviour; a gate on everything the notes leave alone | Pre-registered, from QA pass 16: frontier D 0.66, reward about 0.64 (0.54-0.75), mid-tier about 0.28 (notes/PREREGISTRATION.md) | Unmeasured until the first runs; five kill conditions |
| Initial feasibility | Every graded case follows from its note as shipped (upstream's wording; a stated rule for units 6, 29 and 37), the specification notes and the 14.3.0 code (QA pass 04), and cases a note does not determine are left out; the base tree, its own tests and fontTools let the agent check its work against 14.3.0 for everything the notes leave alone | Example: the Khmer fix is a one-token change whose rule is quoted from Microsoft's spec in the 14.3.0 source itself | E-item restatements; fontTools has no `kerx` writer (our assembler) |

## One step

The owner parked multi-turn on 2026-11-26, so the task is a single step: one instruction listing every note from
14.3.1 to 15.2.0, one 34,560 s session, and one verifier run at the end that checks the 53 graded units against
15.2.0 (the 15.0.0 note on `hb_font_set_face()` is superseded by 15.2.0's, so only the final behaviour counts;
three more are cut, with reasons in notes/DESIGN.md). The
three-step plan the panel chose in Phase A stays in notes/STEPS.md as history; its step 3 is exactly this grading.

## Reward formula

reward = D · G, where D is the mean over the graded units of each unit's pass fraction on its changed cases, and
G = h_d · (1 − 0.10·(1 − h_b)). h_d is the mean over the units of the pass fraction of each unit's neighbouring cases
(the duals: inputs one stated condition away from the note, drawn evenly over the unit's boundaries, on which every
release behaves as 14.3.0 does); h_b is the pass fraction of the broad held-fixed cases. The dual gate is fully
multiplicative: a port that applies every note one condition too broadly keeps D but loses the share of neighbours it
breaks. A tree that does not build scores 0; a missing driver output fails its case; a verifier fault leaves no
reward. Every result reports D, h_d and h_b separately, and the verifier's `metrics.json` records each case's verdict
by unit and kind for post-run analysis. Details and rationale: [notes/DESIGN.md](notes/DESIGN.md#6-reward).

## Failure mode

Chosen by a three-judge panel on 2026-11-27 (harbor-lh
`ops/swe-marathon-v2/decisions/2026-11-27-harfbuzz-failure-sentence-DECISION.md`):

> With no 15.x code or tests to check against, agents land the fixes they can confirm on their own 14.3.0 build and
> fall short on the ones they cannot, chiefly AAT/kern behaviour that needs hand-built fonts, regenerated Unicode
> data, and bugs a note describes only by symptom.

Each graded unit has a tier (notes/DESIGN.md section 10, `scripts/pipeline/tiers.tsv`): A, the note names the fix
(14); B, checkable on the agent's own 14.3.0 build with the shipped fonts and tools (20); C, not checkable without
material the agent builds itself (19). The proof mutant **V** is 15.2.0 with every tier-C unit taken out; it must
land in 0.60-0.85 with its D loss confined to tier C and the gate untouched. The over-broad mutant **W** (every
conditional note widened) is kept as a secondary bound on what the gate takes from a careless port, beside
W_literal (pass 17's literal widenings only) and the panel's R_unbuilt (every F4 and F5 unit taken out). The
per-unit and per-family prediction and its kill conditions were committed before any run
(notes/PREREGISTRATION.md); if implemented units fail their neighbours at 15% or more, and at least three times the
rate of untouched units, the earlier over-breadth sentence comes back.

## Hackability assessment

Tested in fix round 1 (2026-11-27/28) on the amd64 verifier image, except where a row says otherwise.

| Attack | Boundary | Mitigation | Severity |
| --- | --- | --- | --- |
| Read the expected outputs or case files from the tree's build scripts or library code during grading | Verifier container | The build and the case programs run as `builder` (fixed uid, no new privileges, process, file-size and address-space limits); `/tests/private` and `verify.py` are root-only; root's own files are in a root-only `/var/lib/hbv`, and a case program sees its input and output only as files root opened | 🟢 GREEN: as `builder`, reading the expected outputs, listing `/tests/private` and writing the reward all fail (Phase C); the hostile tree's links, planted to make root read or write through them, moved nothing (0.0) |
| Forge or keep a reward: write `/logs/verifier`, plant links under root's file names, leave processes running, preload a library into root | Verifier container | `/logs/verifier` root-owned 0755; root opens through folder descriptors with `O_NOFOLLOW|O_EXCL`; every `builder` process is killed after each step and batch and once more at the end; any reward file found is removed; `metrics.json`, then `reward.txt`, are written last | 🟢 GREEN: the hostile tree (forging at setup, at build and in the library, links planted under every name root uses, processes left behind, a preload library) scores 0.0; `reward.txt` is root's regular file, no `reward.json`, and the leftover processes are reported and killed |
| Leave processes running in the agent container to change the tree after the session | Agent container | A root `[[verifier.collect]]` hook ends every process of `dev` (`kill -9 -1` as `dev`, then `pkill`, until none is left) before the tree is copied out | 🟢 GREEN (locally): run as root in the agent image against 22 `dev` processes (a stopped one, one in its own session, a forking loop, a `nohup` one), it leaves none in 139 ms; on the platform it runs as Harbor's collect step |
| Obtain 15.x code or a newer HarfBuzz binary in the agent container | Agent image | No 15.x source, binary or version string; no network; history cut at one commit | 🟢 GREEN: the protection probe found none, and no network (Phase C) |
| Drop a 15.x release into the tree | Verifier | A tree with a 15.x version in `meson.build`, `src/hb-version.h` or `NEWS`, or one of the 15 unit-test sources only 15.x has (by sha256), is not built and scores 0; the instruction says the tree stays version 14.3.0, and the reference keeps it | 🟢 GREEN: the 15.2.0 release dropped in scores 0.0 unbuilt, all 18 markers listed; the reference, the `solve.sh` tree, V and W carry none |
| Earn credit without implementing the notes | Reward | Every changed case fails on 14.3.0; held-fixed sets only gate; the new-function probes end with a call that only a working function passes | 🟢 GREEN: untouched tree 0.0; comment edits, a neutral refactor, a tree that does not build, an empty `hb_shape`, an abort and the four new functions as no-ops all 0.0 |
| Key outputs on private fonts | Cases | The agent never sees them | 🟢 GREEN: no private case id or font name in any agent-visible file |
| Clutter the delivered tree (pipes, huge files, many files, links out) | Verifier copy | Special files and files over 64 MiB are not copied; links are copied as links; a tree over 4 GiB or 300,000 entries scores 0 with a note | 🟢 GREEN: a tree with a pipe, a 600 MB sparse file, 100,000 files and links out of the tree scores 1.0 |
| Outlast the verifier: a build that never ends, a library that hangs | Verifier | One 1,800 s deadline for the copy, the build and every batch; 120 s per batch; what has not run fails and a reward is still written; a last-resort alarm at 2,100 s, inside the 2,400 s timeout | 🟢 GREEN: a build that sleeps past the deadline scores 0.0 with the reward written at 1,800 s; a library that spins in shaping gets 0.018 at 1,806 s (14 batches stopped at 125 s, 227 not run) |
| Flood the verifier's reads | Verifier | At most 16 MiB + 1 byte of a batch's output is read; 64 MiB file-size limit on case programs; step logs keep their last 4,000 bytes | 🟢 GREEN: a library that writes 4 GiB per shaping call fails its 141 shaping batches, the other 261 score as the reference, and the check ends in 79 s |
| Apply the notes over-broadly | Reward gate | The neighbours' pass rate multiplies the reward | 🟢 GREEN (secondary bound): W, which widens every conditional note, scores 0.678 (h_d 0.691); W_literal, with only literal widenings, 0.751 |

Highest unresolved severity: 🟢 GREEN. The collect hook's platform run is checked on the first oracle trial.

## Layout

```
README.md            this file (never shipped)
task.toml            single step, 34,560 s, separate verifier checking RELEASE=15.2.0
instruction.md       the request, every note from 14.3.1 to 15.2.0
tests/               verifier: Dockerfile, test.sh, verify.py, driver/ (hbdrv.c and the API probes)
                     (private/, inputs/ and wheels/ are staged by packaging and git-ignored)
solution/            solve.sh copies the reference source files and removes the listed paths (solution/private/, git-ignored)
scripts/             development tooling, never shipped: fetch_inputs.sh, gate_checks.py, package_task.py, pipeline/
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
- **Phase C (all units, the failure sentence, QA-ready).** Five unit authors wrote generators, fonts, the API drivers
  and one widening per conditional unit; the c2 sweep classified 50,299 candidates (23,836 changed and
  attributed). 53 units are graded on 5,256 cases (36-60 changed cases each, 1,500 neighbours, 600 broad); 47a,
  28, 30 and 50 are cut with their reasons. The dual gate is now a full factor; mutant W scores 0.672 through the
  verifier. Expected outputs are recorded through the amd64 verifier image built from a pinned Ubuntu snapshot,
  identical to the pipeline's on all 5,256 cases; 3+1 recordings are byte-identical. The specification notes keep
  only what the downloaded pages state. The reference solution ships source files. A stub that never shapes
  briefly scored 0.002 on unit 43's position cases; the probe now refuses to answer when shaping did not run.
  notes/PHASE-C-REPORT.md has the numbers.

### 2026-11-28

- **QA fix round 1.** The independent QA round (21 passes) gave ten must-fix and seven should-fix items; the panel
  on the failure sentence added M11. Every item is fixed, with evidence, in notes/FIX1-REPORT.md:
  - the instruction speaks in the requester's terms, the cut notes are gone, and three notes (6, 29, 37) state
    their rule; the others keep upstream's wording and their cases were narrowed instead;
  - unit 25a's CoreText-history cases are no longer graded, the new-function probes end with a call a no-op
    fails, and three units' boundary cases follow their notes;
  - the verifier keeps its own files root-only, writes the reward last, kills every leftover process, keeps one
    1,800 s deadline over the build and every batch, caps every read, and rejects a dropped-in 15.x release; a
    post-session hook ends the agent's processes;
  - the specification notes are paraphrased and carry a NOTICE; the fonts ship with their OFL text;
  - the failure sentence is the verification-gap one, with tiers, the proof mutant V and a pre-registration;
    W is a secondary bound.
- The c3 sweep rebuilt every release, revert and mutant (66 builds); the expected outputs were recorded again
  through the amd64 verifier image (0 differences from the pipeline; 3+1 recordings identical).

