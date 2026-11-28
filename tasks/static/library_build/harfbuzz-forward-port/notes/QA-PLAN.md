# QA plan (Phase A)

Author notes, never shipped. The gate follows the grading guide's §12 (twelve checks, each scripted, run at every
build, blocking upload when it fails, with its output committed to the README) and §13 (the failure sentence checked
before any model run). Phase B puts the scripts in the task-root `checks/` folder, which never ships. QA reports go to
harbor-lh, `ops/swe-marathon-v2/qa/harfbuzz/`, never into this public folder.

## 1. The pre-upload gate, mapped to this task

| # | Gate | Pass criterion | How, for this task |
| --- | --- | --- | --- |
| 1 | **Inventory** | Every note, clause and stated restriction has an id; a diff against the instruction shows nothing unlisted | `scripts/pipeline/notes_map.tsv` maps the instruction's 48 notes to their units (53 graded; 47a superseded by 47b, and 28, 30 and 50 cut with their notes removed, `cuts.tsv`); `scripts/gate_checks.py` item 1 fails on a note without 3 graded cases. The derivation paths are QA pass 04's per-unit table |
| 2 | **Kill matrix** | Each unit killed by at least 3 cases of its own (target 20) and by none of another unit's; each restriction by at least 1, better 2 by different routes; a mutant fails as cases, never by crashing the runner | One upstream revert R_k per unit, built on the unit's release. Restrictions are killed by the stubs and probes of section 2. Units without an isolating revert are merged or cut |
| 3 | **Stub zoo** | Every member scores 0.000, raw pass rates recorded | Section 3 |
| 4 | **Oracle and nop** | Oracle 1.000 twice and nop 0.000 twice | Oracle = the shipped tree with the reference change (`make_oracle.sh`: 15.2.0's library, the tree's own version kept, 15.x's new unit-test sources left out); the reference solution (`solve.sh`) gives the same tree. The 15.1.0 tree must score its predicted value (about 21/56 before the gate) |
| 5 | **Determinism** | 3 identical runs plus 1 perturbed give byte-identical per-case verdicts | Perturbed run: 1 CPU, a longer scratch path, `MALLOC_PERTURB_`, a shuffled environment order. Run on the oracle, and on the base for case classification; plus an emulated amd64 sample against the arm64 builds, since the platform is x86_64 |
| 6 | **Cue-word sweep** | Zero unjustified hits on every agent-visible surface | Section 4 |
| 7 | **Protection probe** | As the agent user in the real sandbox, every route to 15.x material or answers fails; `id -u` is not 0 | No 15.x source or binary; no `libharfbuzz*`, `hb-version.h` or version string newer than 14.3.0 anywhere (`find`, `strings`); no `solution/`; no network. In the verifier: the `builder` user cannot read `/tests/private` or write the reward |
| 8 | **Verifier robustness** | The verifier image builds from pinned inputs; the oracle grades 1.0 within half the verifier timeout; a forced fault leaves no reward file; no delivered tree can write or keep a reward of its own | Trees (fix round 1): robust (100,000 extra files, a FIFO, a 600 MB sparse file, links out of the tree) 1.0; hostile (the build and the library try every forging route, leave processes behind and plant links under every name root uses) 0.0; drop-in (the 15.2.0 release itself) 0.0 with its release markers listed; fault (an unknown release) exit 1, no reward. A tree that does not build scores 0 with a clean exit |
| 9 | **Isolation and timeouts** | A hang, crash, fork bomb or flood costs only its own batch, and the check always ends with a reward | One deadline of 1,800 s for the copy, the build and every batch (each step gets what is left); 120 s per batch; at most 16 MiB + 1 byte of a batch's output read; process, file-size and address-space limits; every `builder` process killed after each step. Trees: slow (the build outlasts the deadline) and hang (the library spins in shaping) end with a reward after about 1,800 s; flood fails only the batches that shape |
| 10 | **No early stops** | No task-side timer, kill or deadline before `timeout_sec` | Nothing stops the session before the task's `timeout_sec` (34,560 s). The verifier's own deadline runs inside the verifier's timeout, after the session; the `[[verifier.collect]]` hook ends `dev`'s processes only once the session is over, before the tree is copied out |
| 11 | **Leak scan** | No case input contains its answer; no agent-visible file holds a case or a near-copy | No HarfRust 0.15 or later, no newer subproject wrap, history cut at the base; example fonts are not private fonts and show only 14.3.0 outputs; the shipped `test/` holds only 14.3.0 expectations |
| 12 | **Band check** | The proof mutant lands in the band, losing D only where the failure sentence says | Since 2026-11-27 (decision on the failure sentence): mutant V, 15.2.0 with every tier-C unit taken out (DESIGN.md section 10), lands in 0.60-0.85 with its D loss confined to tier C and h_d, h_b at least 0.98. W (every conditional note widened), W_literal and R_unbuilt are reported beside it as bounds, with D, h_d and h_b separately |

Task-specific items on top of the twelve:

- **A capped oracle run**: one oracle trial held to the full 34,560 s, graded 1.0, with per-phase times recorded
  (the platform's known loss is a heavy verifier image after a capped run).
- **Difficulty sizing** (DESIGN.md section 13): the spike's per-unit yield and every cut unit are recorded with
  their effect on the frontier estimate.
- **Standing rules**: Oddish pre-trial QA passes on the version before any agent trial; at least 20 independent QA
  passes (section 5) before any run.

## 2. Coverage inventory

- **Units.** One id per behaviour change in the notes (57). Notes with several fixes get one unit per fix: 10a-b,
  25a-c, 40a-c, 44a-b, 47a-b.
- **Clauses.** A note with several stated conditions gets clause ids, and each clause needs at least one killing
  case:
  - `hb_buffer_deserialize_glyphs2()` and `_unicode2()`: the offset on success, the offset on failure, 0 when
    nothing is consumed, `buf_consumed` `NULL`, `buf_len` −1, both serialization formats;
  - `hb_font_create_without_funcs_or_fail()`: no font functions installed, scale and variations as
    `hb_font_create()`, the face made immutable;
  - `hb_ot_layout_get_extender_glyphs()`: count only, `start_offset` past the end, `glyphs` `NULL`, a script the
    `JSTF` table does not list, the language ignored;
  - `hb_style_get_value()`: its three fixes; `hb_buffer_get_glyph_positions()`: items added after the first call;
  - `hb_face_create_or_fail()`: indices with named-instance bits;
  - `hb_ot_layout_lookup_collect_glyph_alternates()`: `AlternateSubst` and `SingleSubst` format 1.
- **Restrictions** stated in the instructions, each with its killing route:

| Id | Restriction | Killed by |
| --- | --- | --- |
| R1 | The tree builds with the stated commands, unchanged | The unbuildable-tree stub (0); a tree that needs an extra option fails to build |
| R2 | Anything the notes do not change comes out as 14.3.0's does | Mutant W and the over-broad probes, through the dual and broad held-fixed gate |
| R3 | The new functions are declared in the named headers with the stated signatures | Each API driver includes the public umbrella headers (`hb.h`, and `hb-ot.h` for 49) and compiles with `-Werror=implicit-function-declaration`; since fix round 2 the verifier also checks, as text, that each declaration is in the header the note names. A missing declaration fails that unit only |
| R4 | The build regenerates only the ragel machines; other generated tables must be in the tree | A tree with updated generator scripts but stale tables fails the Unicode units |
| R5 | A later note replaces an earlier one (`hb_font_set_face()`) | A tree with 15.0.0's behaviour fails 47b |
| R6 | Each note holds for every font and text it applies to | Per-unit cases span several fonts and strings; a fix keyed to one font (for example by glyph count) fails most of its unit |

- **Two-way matrix.** Every unit has at least 3 cases, and every case belongs to one unit or one held-fixed class.
  The gate fails on any unit below 3 and on any orphan case. Areas the instructions leave out (subsetting, rendering,
  integrations, 24-bit tables, work limits, speed) need no cases; the sweep checks that no case depends on them alone.

## 3. Stub zoo

| Member | Expected |
| --- | --- |
| The untouched 14.3.0 tree (nop) | 0.000 |
| The base with comment and whitespace edits | 0.000 |
| The base with behaviour-neutral refactors (renamed locals, reordered independent statements) | 0.000 |
| A tree that does not build | 0.000 (a valid reward, not an error) |
| A library whose `hb_shape()` returns an empty buffer | 0.000 |
| A library that aborts on its first call | 0.000 |
| The base with the four new functions declared as the notes give them and bodies that do nothing (noop-api) | 0.000 |
| The same, writing 0 through the out-parameters (noop-api-zero, fix round 2) | 0.000 |
| R_all: 15.2.0 with the single-commit graded units reverted | 0.000 on every unit it reverts (not overall) |

Over-broad probes are costed on the case set, not required to be 0: always insert a dotted circle; zero every
glyph's extents; flag every glyph unsafe to break; apply `kerx` and `kern` whenever present. The gate prices
over-breadth in aggregate (W loses 32%), and one note widened alone loses at most about 2% of its own credit to it
(QA pass R2-09), so the test is that no probe scores above its unit's share of D; if one does, the duals around that
unit are too thin.

## 4. Cue-word sweep

**Surfaces.**

- The three instructions and `/app/docs/notes/`.
- Every file and directory name the agent can list.
- The specs (`/app/docs/specs/`), the Unicode files and the example fonts' names.
- The whole `/app/harfbuzz` tree: `README.md`, `TESTING.md`, `BUILD.md`, `RELEASING.md`, `docs/`, `test/`, `util/`,
  the meson files, and upstream's `CLAUDE.md`, `AGENTS.md` and `CODE_OF_AI_CONDUCT.md`.
- The `--help` text of the tools the agent can build (`hb-shape`, `hb-info`).
- Environment variables and image paths in the agent container.
- `task.toml` (no comments).

**Word classes.** These come from grading guide §12 and the three rejections:

- evaluation, benchmark, graded or grader, score, test case, hidden, held-out;
- reference, oracle, gold or golden;
- "cannot be told apart", "behave exactly like", "every request exactly as", "exactly as the reference", identical to;
- budget, deadline, session, verifier, trial, reward, time limit.

**Whitelist.** Hits are allowed only in their domain sense, and each is listed with its count in the sweep report:

- "reference" in reference counting (`hb_*_reference()`) and in font-table prose;
- `test/` and upstream's test files in a source tree;
- "evaluate" in the variation-store and state-machine sense inside the specs and the source.

Everything else is removed or reworded.

**Pruned in Phase A by design:** `perf/`, `subprojects/google-benchmark.wrap`, the `benchmark` meson option and its
`subdir`, `.github/`, `.ci/` and `.codecov.yml`.

**Read before deciding:** upstream's `CLAUDE.md`, `AGENTS.md` and `CODE_OF_AI_CONDUCT.md`. claude-code loads
`CLAUDE.md` as instructions, so they stay only if they neither steer against the work order nor carry cue words.

**Draft instruction:** the three step drafts were swept on 2026-11-26 and the merged single-step instruction on
2026-11-27: no hits, no non-ASCII characters.

**Known residue:** the harness's own process line, visible with `ps`, is not ours to change; it is recorded and left
alone. The run-prompt suffix chosen on 2026-11-25 is used unchanged.

## 5. The 20 QA lenses

Each lens is one independent reviewer pass with its own context, run after the gate is green. Findings go to
harbor-lh `qa/harfbuzz/NN-<lens>.md` as must-fix, should-fix or note.

| # | Lens | The question it answers |
| --- | --- | --- |
| 1 | Real-world work order | Would a team that froze 14.3.0 ask for this, this way? Does "port each fix from its note into our code" read as natural, with the certification reason? |
| 2 | Evaluation awareness | Reading only what the agent sees, does anything suggest a test, a comparison or a hidden check? |
| 3 | Instruction-verifier agreement | Is every credited behaviour stated, is nothing credited that is not, and do units map one-to-one to notes and clauses? |
| 4 | Restated notes | Does each restated (R) note determine the release's output on every case, and does its derivation path hold? |
| 5 | Duals | Is each dual's expected output the base's? Does no listed note change it? Is each a fair neighbour of the stated condition? |
| 6 | Attribution | For 50 random changed cases, is the difference really its unit's (read the R_k diff)? |
| 7 | Verifier-side hacks | Can the tree's build scripts or library code reach recorded outputs, the reward file or the comparison? |
| 8 | Agent-side leaks | Is any 15.x material, newer HarfBuzz, network route, solution file or new output in the agent's reach? |
| 9 | Stubs | Does every stub score 0.000, and does every over-broad probe stay below its unit's share of D? |
| 10 | Determinism and toolchain | Do 3+1 runs agree? Are the base image, apt snapshot and compiler the same on the gold host and in the verifier? |
| 11 | Robustness and isolation | Do hangs, crashes, fork bombs, disk floods and odd files in the tree cost only their batch? Do the fail-soft and evaluation-error paths behave? |
| 12 | Instruction coherence | Does the one instruction list every graded note, release by release, with the superseded `hb_font_set_face()` note stated as superseded? Is `RELEASE` wired from the task config? |
| 13 | Platform constraints | Timeouts, the 43,200 s attempt, no task-side timers, network modes, image sizes, the capped oracle run |
| 14 | Unicode data fidelity | Are the shipped UCD and USE-override versions those 15.x used? What did the regeneration check keep? Which packTab version? |
| 15 | Fonts and licences | Every font's licence; synthetic fonts are ours; no upstream in-house font among the private ones; redistribution of each shipped document |
| 16 | Difficulty and horizon | Is this two to seven days of skilled human work? Is any family trivial or impossible? What is the mid-tier floor? |
| 17 | Failure-mode validity | Does W have its signature? Do the learnability write-ups hold? Do the difficulty-ordering proxies favour the sentence or throughput? |
| 18 | Memorization and contamination | Does anything in reach encode 15.x behaviour? Is every unit's fix post-cutoff? Are cases tagged by release? |
| 19 | The shipped tree and tools | Do upstream's `CLAUDE.md`, `AGENTS.md`, `CODE_OF_AI_CONDUCT.md`, `TESTING.md` or the tools' help text steer the agent or conflict with the work order? |
| 20 | Novelty and overlap | Against SWE-M2's tasks, Forge and public benchmarks (SWE-EVO, SWE-Chain, RoadmapBench, SWE-smith-cpp); the "each fix is small" perception |

## 6. Post-run "good failure" checks

After the first accepted trials, before any score is shown to anyone:

0. Before any score is used: run `ops/swe-marathon-v2/audit_egress.py` on every trial; read the post-session
   sweep's record (`/var/lib/fsmaint/out` and the tree's `.fsmaint.json`: egress, processes, end of the work, late
   entries); void a trial with a confirmed fetch; publish no score before this audit (2026-11-19 decision).
1. Oracle 1.0 and every stub 0, on the version that ran.
2. Every trial graded. One ungraded capped trial stops the campaign; a lost trial is reported as lost,
   never as 0.
3. Progress still rising at the cap: the agent is still landing notes in the last hours of the session rather than
   idle (read from the trajectory and the tree's history).
4. Every failed case traces to a stated note through its unit tag, and the oracle or at least one other run passes
   it. Every failed dual is one the base passes by construction.
5. Failures cluster in named families: a per-family table per trial.
6. The failure-sentence test: the kill conditions in notes/PREREGISTRATION.md, committed before any run (tier C at
   least 0.10 below tiers A and B; per-family and per-unit bounds). If units an agent implemented fail their duals
   at 15% or more, and at least three times the rate of untouched units, the Phase A over-breadth sentence
   (CLAIMS.md, section 4) comes back.
7. Contamination: pass rate by release tag. A jump on the oldest releases against the newest flags recall.
8. No infrastructure error, no task-forced stop, and no awareness finding: read the verdict and each trial's
   `evaluation_awareness`.
9. Frontier rewards checked against the sizing target (DESIGN.md section 13): at most about 0.6, no full solve.
