# HarfBuzz forward-port, 14.3.0 → 15.2.0

**Status: QA fix round 2 done (2026-11-28).** Single-step (owner, 2026-11-26). 53 of 57 units are graded on 5,245
private cases (four cut, with reasons in notes/DESIGN.md). Every tree below went through a simulated trial: the
agent image's set-up and collect hooks, Harbor's `tar` transfer, then the amd64 verifier image. The reference
solution scores 1.0, the untouched tree 0.0, every stub 0.0 (both no-op API stubs too), the verification-gap mutant
V 0.875 as built (D 0.875, h_d 1.000, h_b 1.000; complete, with every tier-C unit at 0: 0.849, inside the 0.60-0.85 band) and the over-broad mutant W,
a secondary bound, 0.695 (D 0.982, h_d 0.709, h_b 0.970); the hostile, drop-in and path-canary trees score 0.0; slow and hanging trees still
get their reward at the 1,800 s deadline. Local preflight passes on the flat bundle. Next: QA round 3; no Oddish
run before the owner says so. Category: Library Reproduction (`tasks/static/library_build/`). Branch
`neel/harfbuzz-forward-port`.

A product ships HarfBuzz 14.3.0 and has frozen that build. The agent brings it forward to the shaping, layout,
metrics and API behaviour of upstream's next eight releases (14.3.1 to 15.2.0, 2026-08-13 to 2026-11-19), in one
session, working from the release notes, the specifications and its own test fonts. It never sees a 15.x tree or
binary. A separate verifier compiles the delivered tree and compares integer shaping and API outputs
on private fonts and strings with the upstream releases. Only behaviour a listed note changed is credited, and
behaviour no note changed must stay as it was. Where agents are expected to fail: with no 15.x code or tests to
check against, they land most fixes whose note names the change, fewer where they must work the change out or diagnose
a symptom the shipped fonts reproduce, and fewest where no shipped font shows the behaviour: a bug they must first
reproduce on a font they build, or AAT `kerx` and `kern` tables they must assemble by hand.

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
| [notes/RESIDUAL-AUDIT.md](notes/RESIDUAL-AUDIT.md) | The static audit of every unit's graded cases against its note (fix round 2) |
| [notes/FIX2-REPORT.md](notes/FIX2-REPORT.md) | QA fix round 2: every item, the panels' outcomes, the re-recording cycle and its evidence |

## Design dimensions (proposal stage)

| Dimension | Argument | Evidence so far | Open |
| --- | --- | --- | --- |
| Novelty | First SWE-M2 task that changes an existing C++ library, first text-shaping task, first forward-port. Release-notes upgrades exist (SWE-EVO, SWE-Chain, RoadmapBench) but on pre-cutoff Python releases graded by upstream tests; this one is post-cutoff, in OpenType and AAT shaping, graded by differential execution on private fonts | No shaping task among Forge's 664 tasks or this repository's tasks (read 2026-11-26) | Public-benchmark comparisons are second-hand (CLAIMS.md C9, C11) |
| Verifiability | Outputs are integer sequences; per-item upstream revert mutants prove each graded case belongs to one note; the unmodified base scores 0 by construction | Commit-level evidence in CLAIMS.md | Case yield per item, revert cleanliness, determinism: all spike items |
| Realism | Frozen, certified builds that take upstream fixes as their own changes are common practice; the notes are upstream's own (the restated rules of units 6, 29 and 37 and the new functions' API texts are ours), the specs are the ones a maintainer reads | Upstream's notes state rules as conditions precise enough to implement (CLAIMS.md C29) | The "no upstream diff" story has to read as natural (QA lens 1) |
| Difficulty | 53 graded changes across 8 families: 23 whose note names the edit, 22 the agent must work out or diagnose on material it can see, and 8 where no shipped font shows the behaviour (hand-assembled `kerx`, or a symptom-only bug to reproduce on a font it builds); no oracle for the new behaviour, beyond what fontTools computes for units 31, 41 and 42; a gate on everything the notes leave alone. Horizon: about 10-16 working days for an engineer who knows HarfBuzz, several weeks otherwise (QA pass R2-16), above the owner's 2-7 day target; no scope cut, since cutting tier C raises the frontier | Pre-registered from QA pass 16's per-unit estimates: frontier D 0.687, reward about 0.65 (0.53-0.76), accepted as about 0.6, with no lever, by the panel the owner asked to settle it (2026-11-28c); mid-tier about 0.29; a median above 0.70 over the first three accepted Opus-class sessions is reported to the owner, and any re-version after an accept needs his word | Unmeasured until the first runs |
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
reward. Every result reports D, h_d and h_b separately, and the verifier's `case_pass.json` (beside `metrics.json`)
records each case's verdict and a salted digest of its output, by unit and kind, for post-run analysis. Details and rationale: [notes/DESIGN.md](notes/DESIGN.md#6-reward).

## Failure mode

Chosen by a three-judge panel on 2026-11-27 and revised by a second on 2026-11-28 (harbor-lh
`ops/swe-marathon-v2/decisions/2026-11-27-harfbuzz-failure-sentence-DECISION.md` and
`2026-11-28-harfbuzz-tiers-difficulty-DECISION.md`, with the wording of `2026-11-28b-harfbuzz-sentence-after-tiering-DECISION.md`):

> With no 15.x code or tests to check against, agents land most fixes whose note names the change, fewer where they
> must work the change out or diagnose a symptom the shipped fonts reproduce, and fewest where no shipped font shows
> the behaviour: a bug they must first reproduce on a font they build, or AAT `kerx` and `kern` tables they must
> assemble by hand.

Each graded unit has a tier, by the 2026-11-28 panel's ordered rule (notes/DESIGN.md section 10,
`scripts/pipeline/tiers.tsv`, frozen with the pre-registration): C if the behaviour shows only on tables no shipped
font has and fontTools cannot write (hand-assembled `kerx` or AAT `kern`), or the note gives only a symptom whose
cause it neither states nor points to and no shipped font shows it (8: 10a, 23, 25a, 25b, 25c, 26, 31, 42); A if
otherwise the note names the edit (23); B otherwise (22). The mutant **V** (15.2.0 with every tier-C unit's commits
reverted) is a consistency check of the scoring: it must land in 0.60-0.85 with its D loss confined to tier C and h_d
and h_b at 0.99 or more (1 - 8/53 = 0.849 complete; 25a's and 25b's later commits do not revert, so V keeps 25b whole
and 25a in part). The over-broad mutant **W** (every conditional note widened) is kept as a secondary bound on what
the gate takes from a careless port, beside W_literal (pass 17's literal widenings only) and R_unbuilt (every F4 and
F5 unit taken out). The per-unit and per-family predictions, the registered tests on the tier ranking (A - C, A - B,
B - C, B's level and loss share) with their chance rates, and the other kill conditions were committed before any
run (notes/PREREGISTRATION.md).

## Stated but not graded

- **Descriptive clauses.** The 15.0.0 note that `hb_font_set_face()` is deprecated (unit 47a, cut: in 15.2.0 the
  function is 47b's no-op, and the deprecation attribute shows in no output), and "or `NULL` if allocation fails"
  in unit 48's API text, which honest work cannot reach. Both describe 15.2.0; no case checks them.
- **Strata a literal reading fails.** Unit 26's `b:mid-before` duals keep 14.3.0's mid-text insertion behaviour,
  which every release keeps, so a port that also changes it loses them. Read them before calling a failed dual
  over-breadth (QA pass R2-05).

## Hackability assessment

Tested in fix round 2 (2026-11-28) through simulated trials: the agent image with its set-up and collect hooks, the
turn as `dev`, Harbor's `tar` transfer as root and the worker's `tarfile` "data" filter, then the amd64 verifier
image with no network, except where a row says otherwise.

| Attack | Boundary | Mitigation | Severity |
| --- | --- | --- | --- |
| Read the expected outputs or case files from the tree's build scripts or library code during grading | Verifier container | The build and the case programs run as a fresh unprivileged uid (no new privileges, process, file-size and address-space limits); `/tests/private` and `verify.py` are root-only; root's own files are in a root-only `/var/lib/hbv`, and a case program sees its input and output only as files root opened | 🟢 GREEN: as the build user, reading the expected outputs, listing `/tests/private` and writing the reward all fail (Phase C); the hostile tree's links, planted to make root read or write through them, moved nothing (0.0) |
| Forge or keep a reward: write `/logs/verifier`, plant links under root's file names, leave processes running, preload a library into root | Verifier container | `/logs/verifier` root-owned 0755, and the check faults if the build user can create a file there; root opens through folder descriptors with `O_NOFOLLOW|O_EXCL`; every build-user process is killed after each step and batch and once more at the end, from a helper it cannot signal, every wait bounded; any reward file found is removed; `metrics.json`, then `reward.txt`, are written last | 🟢 GREEN: the hostile tree scores 0.0 with no `reward.json` in what Harbor collects; stall (stoppers and a survivor that changes its pid) 0.0 in 118 s, every leftover process killed; fork bomb 1.0 in 68 s (also under `--pids-limit=96`: 1.0 in 72 s); memory flood 0.0 in 18 s (meson killed, 255 processes ended), with no survivor in any of them |
| Plant a command where root resolves names, so that Harbor's `tar` (collecting `/logs/verifier`, which it reads `reward.json` from first) or the hooks run it as root (Dogwood pass 07 F1) | Both images | No directory on root's PATH, su's default paths, the hooks' or verify.py's paths, or their parents, and no file in one, is writable by `dev`, `builder`, `nobody` or a fresh uid; the hooks and `test.sh` set their own PATH | 🟢 GREEN: `path_check.py` finds nothing writable in either image (14 directories in each, none writable by `dev`, `builder`, `nobody` or a fresh uid); the path-canary tree (its build plants `tar`, `gzip` and eleven more wherever it can) scores 0.0 with nothing planted and no marker or `reward.json` collected; the same planter as `dev` in the agent image plants nothing |
| Leave processes running in the agent container to change the tree after the session, or fetch 15.x once the network comes back before the tree is copied out | Agent container | The net check (set-up hooks, root) watches `dev`'s sessions and processes, keeps copies of the tree's files as they change, and notes when the network comes back; the collect hook stops and kills every process of `dev` (a process counts while any thread lives), puts back whatever changed after the end of the work, and leaves a signed listing and record beside the tree; the verifier faults on a tree that differs from the listing | 🟢 GREEN: a drop-in left behind to copy the reference's files once the network returns: 130 late entries (129 holding the reference's files), all taken out, 0.0; a process whose first thread has exited while another writes: found by its live thread and killed, its writes after the end put back, 1.0 (round 1's hook: it outlives the hook); 22 or more leftover processes with no network: 97 listed and killed, none left, 1.0; a capped run's last edit kept and later ones undone: 1.0 |
| Obtain 15.x code or a newer HarfBuzz binary in the agent container | Agent image | No 15.x source, binary or version string; no network; history cut at one commit; the hooks, their key and their state are root-only | 🟢 GREEN: the protection probe on the rebuilt image finds none (no 15.x material, no network, no sudo, the hooks' files unreadable) |
| Drop a 15.x release into the tree | Verifier | A tree that holds 3 or more of the 15 unit-test sources only 15.x has (by sha256), or links `meson.build`, `NEWS`, `src` or `src/hb-version.h`, is not built and scores 0; a version other than exactly 14.3.0 multiplies the reward by 0.9; the instruction says the tree stays 14.3.0 | 🟡 YELLOW: the 15.2.0 release dropped in scores 0.0, unbuilt, with its markers listed. The tripwire is a backstop that a drop-in without the test sources passes; the boundary is that no 15.x code reaches the tree (no network in the session; the collect hook undoes what is fetched after it) |
| Earn credit without implementing the notes | Reward | Every changed case fails on 14.3.0; held-fixed sets only gate; the new-function probes end with a call that only a working function passes; a function counts only where its note's header declares it | 🟢 GREEN: untouched tree 0.0; comment edits, a neutral refactor, a tree that does not build, an empty `hb_shape`, an abort and the four new functions as no-ops (both kinds) all 0.0 |
| Key outputs on private fonts | Cases | The agent never sees them | 🟢 GREEN: no private case id or font name in any agent-visible file |
| Clutter the delivered tree (pipes, huge files, many files, absolute and outward links) | Agent-side sweep, Harbor's transfer, verifier copy | The collect hook removes build folders, FIFOs, sockets and devices, makes in-tree links relative and outward links copies (256 MiB in all), removes dangling links, over-deep, over-long and unprintable names, and refuses a tree over 200,000 entries or 1 GiB; the verifier copies no special file or file over 64 MiB; the instruction states the limits | 🟢 GREEN: links and a FIFO left in the reference: 1.0 (one link made relative, two copied, three removed with the FIFO; 7,915 of 7,915 entries arrived), the whole tree arriving (without the hook the extraction stops at the FIFO: 7,719 of 7,862); robust (a pipe, a 600 MB sparse file, 100,000 files, links out of the tree): 1.0, all 104,738 entries arriving (its new files pass the net check's 50,000 tracked entries, which the sweep notes; nothing changed after the end, so nothing was removed) |
| Outlast the verifier: a build that never ends, a library that hangs | Verifier | One 1,800 s deadline for the copy, the build and every batch; at most 15 s per batch, keeping 2 s for each later one; what has not run fails and a reward is still written; alarms at 1,980 s (main), 90 s (clean-up) and 30 s (publishing), inside the 2,400 s timeout | 🟢 GREEN: a build that sleeps past the deadline 0.0, the reward written at 1,800 s; a library that spins in shaping 0.070, the reward written at 1,801 s |
| Flood the verifier's reads or memory | Verifier | At most 16 MiB + 1 byte of a batch's output read; a result over 4,096 characters fails its case, and only a pass bit and a digest are kept per case; `metrics.json` under 60 KiB; 64 MiB file-size limit on case programs | 🟢 GREEN: a library that writes 4 GiB per shaping call 0.067 in 72 s; one huge result line per program 266 results over 4,096 characters fail their cases, the check's memory peaks at 203 MiB, the reward is written in 89 s |
| Apply the notes over-broadly | Reward gate | The neighbours' pass rate multiplies the reward | 🟢 GREEN (secondary bound): W, which widens every conditional note, scores 0.695 through the verifier (D 0.982, h_d 0.709, h_b 0.970); W_literal 0.766 in the pipeline |

Highest unresolved severity: 🟡 YELLOW (the drop-in tripwire is a backstop; the boundary is the closed network).

## Layout

```
README.md            this file (never shipped)
task.toml            single step, 34,560 s, root set-up and collect hooks, two artifacts (the tree and the hook's
                     record), separate verifier checking RELEASE=15.2.0
instruction.md       the request, every note from 14.3.1 to 15.2.0
environment/         agent image: Dockerfile, prune_tree.sh, docs/ (the notes and specifications), and the set-up
                     and collect hooks (fsmaint-reserve, fsmaint-netcheck, fsmaint-sweep; root-only in the image)
tests/               verifier: Dockerfile, test.sh, verify.py, sweep_check.py (reads the collect hook's mark),
                     driver/ (hbdrv.c and the API probes)
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
  session. Grading is the old step 3: all 56 units (then; 53 after Phase C's cuts) against 15.2.0 with the
  held-fixed duals gate. notes/STEPS.md
  is kept as history, marked parked.
- **Difficulty sizing.** The owner asked that the single session be "difficult enough"; target frontier at most
  about 0.6. notes/DESIGN.md section 13 keeps the dual gate at full strength (weight never below 0.25), keeps the
  AAT and `kern` families, drops no hard but fair note, and estimates frontier ≈ 0.48 (0.36-0.60) and mid-tier
  ≈ 0.12-0.30, with how each yield-driven cut would move it.
- Upstream's `CLAUDE.md` is a symlink to `AGENTS.md`, whose rules (narrow changes, preserve behaviour) fit the work
  order: kept, without its `perf/: benchmarks` line. `CODE_OF_AI_CONDUCT.md` ("Do not fabricate benchmarks") and
  `test/vector/README.md` ("golden files") join the prune list.
- **Spike: go.** S2: the product build takes 15-31 s on 4 CPUs (arm64), and outputs are identical with and without
  ragel. S3: the driver reproduces all 16 of upstream's new Khmer expectations. S6: 49 of the then 56 units revert cleanly.
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
- Upstream's own suite ran offline in the agent image: 244 of 245 tests passed; the threaded shaping test read its
  inputs from the pruned speed-measurement folder, so the prune now drops it. The re-run on the rebuilt image
  waits for the shared lock.

- **QA fix round 2.** QA round 2 (17 passes) gave eight must-fix and twelve should-fix items; two panels decided the
  tier rule, the difficulty lever, the horizon and the failure sentence. Every item is fixed, with evidence, in
  notes/FIX2-REPORT.md:
  - unit 35's note states the reverse mapping; every stated clause has cases or lost its words; floats print
    rounded; repeats are dropped from every draw;
  - the agent image's hooks close the egress window: a net check that watches `dev` and keeps copies of the tree,
    and a collect hook that ends `dev`'s processes, undoes what changed after the end, makes the tree copyable and
    signs a listing the verifier checks; the instruction says what is copied;
  - the verifier caps what it keeps of a result, bounds every wait, kills from a uid the build cannot signal,
    allows 15 s per batch, refuses a drop-in only on a quorum of upstream test sources and scales a wrong version
    by 0.9;
  - root's PATH is writable by no other user in either image, with canaries;
  - the tiers follow the panel's ordered rule (A 23, B 22, C 8, frozen), the sentence ranks them, and the amended
    pre-registration was committed before any run.
- The c4 sweep rebuilt every release, revert, mutant and the forward build of unit 33 (68 builds); the expected
  outputs were recorded again through the amd64 verifier image (3+1 identical). A first try failed on Docker's full
  disk; 86 of this task's stale build-cache records were pruned and the milestone now checks the disk first.
- Upstream's own suite ran offline on the rebuilt agent image: 244 of 244 tests passed.
