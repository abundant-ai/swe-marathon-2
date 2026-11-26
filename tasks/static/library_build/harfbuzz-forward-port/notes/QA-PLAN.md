# QA plan (Phase A)

Author notes, never shipped. The gate follows the grading guide's §12 (twelve checks, each scripted, run at every
build, blocking upload when it fails, with its output committed to the README) and §13 (the failure sentence checked
before any model run). Phase B puts the scripts in the task-root `checks/` folder, which never ships. QA reports go to
harbor-lh, `ops/swe-marathon-v2/qa/harfbuzz/`, never into this public folder.

## 1. The pre-upload gate, mapped to this task

| # | Gate | Pass criterion | How, for this task |
| --- | --- | --- | --- |
| 1 | **Inventory** | Every note, clause and stated restriction has an id; a diff against the three instructions shows nothing unlisted | `features.yaml` generated from the three `instruction.md` files: 57 units (ids from the CLAIMS.md inventory), clause ids for the multi-part notes and the API descriptions, and restrictions R1-R6 (section 2). Each unit records its derivation path: the note, the spec paragraph, and one probe command on the agent's own 14.3.0 build |
| 2 | **Kill matrix** | Each unit killed by at least 3 cases of its own (target 20) and by none of another unit's; each restriction by at least 1, better 2 by different routes; a mutant fails as cases, never by crashing the runner | One upstream revert R_k per unit, built on the unit's release. Restrictions are killed by the stubs and probes of section 2. Units without an isolating revert are merged or cut |
| 3 | **Stub zoo** | Every member scores 0.000 at every step, raw pass rates recorded | Section 3 |
| 4 | **Oracle and nop** | Oracle 1.000 twice and nop 0.000 twice, per step | Oracle = the tree patched to that step's release. The carry-over stubs (the previous release's tree) must score their predicted values (STEPS.md) |
| 5 | **Determinism** | 3 identical runs plus 1 perturbed give byte-identical per-case verdicts | Perturbed run: 1 CPU, a longer scratch path, `MALLOC_PERTURB_`, a shuffled environment order. Run per step on the oracle, and on the base for case classification |
| 6 | **Cue-word sweep** | Zero unjustified hits on every agent-visible surface | Section 4 |
| 7 | **Protection probe** | As the agent user in the real sandbox, every route to 15.x material or answers fails; `id -u` is not 0 | No 15.x source, binary or notes beyond the current window; no `libharfbuzz*`, `hb-version.h` or version string newer than 14.3.0 anywhere (`find`, `strings`); no `solution/`; no network. In the verifier: the `builder` user cannot read `/tests/private` or write the reward, and nothing the verifier writes reaches the agent's sandbox |
| 8 | **Verifier robustness** | The verifier image builds from pinned inputs; the long-run smoke grades the oracle at 1.0 within half the verifier timeout; a forced runner fault leaves no reward file | Smoke on a delivered tree with 100,000 extra files, a full disk, leftover processes, links pointing outside the tree, FIFOs and a 4 GB file. Plus the fail-soft path: a tree that does not build scores 0 and the next step starts |
| 9 | **Isolation and timeouts** | A hang, crash, fork bomb or 10 GB of output costs only its own batch | One process per font batch, with CPU, memory, file-size and process limits and a timeout |
| 10 | **No early stops** | No task-side timer, kill or deadline before any step's `timeout_sec` | grep of the environment, hooks and verifier; only the per-step `timeout_sec` values |
| 11 | **Leak scan** | No case input contains its answer; no agent-visible file holds a case or a near-copy | No HarfRust 0.15 or later, no newer subproject wrap, history cut at the base; `/app/docs/notes/` shows only windows up to the current step; example fonts are not private fonts and show only 14.3.0 outputs; the shipped `test/` holds only 14.3.0 expectations |
| 12 | **Band check** | The B-mutant lands in the band with a single-family drop | Mutant W at step 3 (CLAIMS.md, proof plan): D ≥ 0.98, h_d ≤ 0.5, h_b and every F family ≥ 0.95, reward in 0.60-0.85, a signature no R_k or R_flags shares; the dual weight fixed here (0.20-0.35); difficulty-ordering proxies recorded |

Task-specific items on top of the twelve:

- **The capped oracle chain** (panel Q3, STEPS.md): all three steps graded 1.0 with each step held to its cap,
  per-phase times recorded, and the switch rule applied.
- **Harbor's step verifier timeout**: on the platform's Harbor build, each step's verifier gets its own
  `timeout_sec`, not a 600 s default.
- **Flat parity**: the flat bundle's verdicts equal step 3's on the oracle, the nop and W.
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
| R3 | The new functions are declared in the named headers with the stated signatures | Each API driver includes only `hb.h` and the named header and compiles with `-Werror=implicit-function-declaration`; a definition without the declaration fails that unit only |
| R4 | The build regenerates only the ragel machines; other generated tables must be in the tree | A tree with updated generator scripts but stale tables fails the Unicode units |
| R5 | A later note replaces an earlier one (`hb_font_set_face()`) | A step-3 tree with 15.0.0's behaviour fails 47b |
| R6 | Each note holds for every font and text it applies to | Per-unit cases span several fonts and strings; a fix keyed to one font (for example by glyph count) fails most of its unit |

- **Two-way matrix.** Every unit has at least 3 cases, and every case belongs to one unit or one held-fixed class.
  The gate fails on any unit below 3 and on any orphan case. Areas the instructions leave out (subsetting, rendering,
  integrations, 24-bit tables, work limits, speed) need no cases; the sweep checks that no case depends on them alone.

## 3. Stub zoo

| Member | Expected at every step |
| --- | --- |
| The untouched 14.3.0 tree (nop) | 0.000 |
| The base with comment and whitespace edits | 0.000 |
| The base with behaviour-neutral refactors (renamed locals, reordered independent statements) | 0.000 |
| A tree that does not build | 0.000 (a valid reward, not an error) |
| A library whose `hb_shape()` returns an empty buffer | 0.000 |
| A library that aborts on its first call | 0.000 |
| R_all: the step's release with every graded unit reverted | 0.000 |

Over-broad probes are recorded but not required to be 0, because each is the failure mode in miniature: always insert a
dotted circle; zero every glyph's extents; flag every glyph unsafe to break; apply `kerx` and `kern` whenever present.
Each must lose most of its unit credit to the gate. If one scores above its unit's share of D, the duals around that
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

**Draft instructions:** swept on 2026-11-26 with no hits and no non-ASCII characters (STEPS.md commit).

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
| 9 | Stubs | Does every stub score 0.000 at every step, and does every over-broad probe lose its credit to the gate? |
| 10 | Determinism and toolchain | Do 3+1 runs agree? Are the base image, apt snapshot and compiler the same on the gold host and in the verifier? |
| 11 | Robustness and isolation | Do hangs, crashes, fork bombs, disk floods and odd files in the tree cost only their batch? Do the fail-soft and evaluation-error paths behave? |
| 12 | Multi-step coherence | Is each instruction self-contained? Are replacements stated and later notes absent? Is `RELEASE` wired, are the carry-over values right, is each step's `workdir/` right? |
| 13 | Platform constraints | Timeouts, the 43,200 s attempt, step verifier timeouts on the platform's Harbor, no task-side timers, network modes, image sizes, the capped oracle chain |
| 14 | Unicode data fidelity | Are the shipped UCD and USE-override versions those 15.x used? What did the regeneration check keep? Which packTab version? |
| 15 | Fonts and licences | Every font's licence; synthetic fonts are ours; no upstream in-house font among the private ones; redistribution of each shipped document |
| 16 | Difficulty and horizon | Is this two to seven days of skilled human work? Is any family trivial or impossible? What is the mid-tier floor? |
| 17 | Failure-mode validity | Does W have its signature? Do the learnability write-ups hold? Do the difficulty-ordering proxies favour the sentence or throughput? |
| 18 | Memorization and contamination | Does anything in reach encode 15.x behaviour? Is every unit's fix post-cutoff? Are cases tagged by release? |
| 19 | The shipped tree and tools | Do upstream's `CLAUDE.md`, `AGENTS.md`, `CODE_OF_AI_CONDUCT.md`, `TESTING.md` or the tools' help text steer the agent or conflict with the work order? |
| 20 | Novelty and overlap | Against SWE-M2's tasks, Forge and public benchmarks (SWE-EVO, SWE-Chain, RoadmapBench, SWE-smith-cpp); the "each fix is small" perception |

## 6. Post-run "good failure" checks

After the first accepted trials, before any score is shown to anyone:

1. Oracle 1.0 and every stub 0, on the version that ran.
2. Every trial graded at step 3. One ungraded capped trial stops the campaign; a lost trial is reported as lost,
   never as 0.
3. Progress still rising at the cap: each window's unit pass fraction grows across the steps, and the agent is still
   working in the last half hour of step 3 rather than idle.
4. Every failed case traces to a stated note through its unit tag, and the oracle or at least one other run passes
   it. Every failed dual is one the base passes by construction.
5. Failures cluster in named families: a per-family table per trial.
6. The failure-sentence test (CLAIMS.md, section 4): the dual failure rate on units an agent implemented is at least
   15% and at least three times the rate on units it left alone, in at least two of the first three accepted runs.
   Otherwise the fallback sentence applies.
7. Contamination: pass rate by release tag. A jump on the oldest releases against the newest flags recall.
8. No infrastructure error, no task-forced stop, and no awareness finding: read the verdict and each trial's
   `evaluation_awareness`.
9. Steps and flat trials labelled and reported separately.
