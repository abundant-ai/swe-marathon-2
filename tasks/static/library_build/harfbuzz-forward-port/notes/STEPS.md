# Multi-step plan and acceptance criteria (Phase A)

> **Parked by the owner, 2026-11-26** ("we dont have to promote multi-turn as well so make stuff likewise").
> The task is single-step: one instruction and one 34,560 s session from 14.3.0 to 15.2.0, graded as step 3
> below (all 56 units against 15.2.0, with the held-fixed duals gate). This file is kept as history; the panel's
> decision on steps no longer applies.

Author notes, never shipped. The design is in [DESIGN.md](DESIGN.md), the units in the
[CLAIMS.md inventory](CLAIMS.md#item-inventory), the gate in [QA-PLAN.md](QA-PLAN.md).

## Panel decision (2026-11-26)

Three judges (opus, sonnet, haiku) voted independently on the same brief. The brief, the three votes and the
decision are in harbor-lh, `ops/swe-marathon-v2/decisions/2026-11-26-harfbuzz-forward-port-steps-*.md`.

| Question | opus | sonnet | haiku | Decision |
| --- | --- | --- | --- | --- |
| Layout | A | A | A | **Three steps, release window by release window** (unanimous) |
| Reward strategy | final | final | final | **`final`** (unanimous) |
| Platform proof before any model run | C | B | B | **B: the oracle chain with every step held to its cap, all three steps graded 1.0** (majority) |

The guards adopted from the votes are listed in the decision file and carried into the criteria below.

## The chain

All three steps run in one sandbox; the tree and everything else the agent made persist from step to step.

| Step | Window | Upstream releases | New units | Units graded | Gold release | Agent `timeout_sec` | Verifier `timeout_sec` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `01-releases-14.3.1-to-15.0.0` | A | 14.3.1, 14.4.0, 14.5.0, 14.5.1, 14.6.0, 15.0.0 | 9 | 9 | 15.0.0 | 7,200 | 2,400 |
| `02-release-15.1.0` | B | 15.1.0 | 13 | 22 | 15.1.0 | 7,200 | 2,400 |
| `03-release-15.2.0` | C | 15.2.0 | 35 | 56 (47a's cases move to 47b) | 15.2.0 | 20,160 | 2,400 |

**How the steps connect.**

- Each step's instruction lists its own window's notes and repeats every earlier note its verifier still checks,
  because a step may start a fresh agent session. It never shows a later window. Step 3 says that
  `hb_font_set_face()` now does nothing, replacing the step-1 note that it resets the font functions. This change
  between steps 1 and 3 is by design.
- Each step's `workdir/` adds `/app/docs/notes/<window>.md` (the same list as the instruction) and, from Phase B,
  the example fonts for that window's restated notes. A release's material arrives with the release.
- Work left unfinished in one step can be finished in a later one: step 3 re-checks every unit against 15.2.0.
- The verifier learns which release it checks from `[steps.verifier] env` (`RELEASE`), never from the tree or any
  file the agent writes. The three `tests/` directories are byte-identical, staged by the packager from one
  source in `common/`, so the platform builds and caches one verifier image.
- No `min_reward`: a weak step never stops the chain.

**Time.** Agent time is 34,560 s, the same as the single-step version. Of the 43,200 s attempt, 8,640 s remain for
image builds, setup and three verifiers. Expected non-agent time is about 2,400 s: three verifier runs of at most
600 s each (spike S8's target) and about 600 s of setup. Worst case is 34,560 + 3 × 2,400 + 1,200 = 42,960 s.
**Switch rule** (from the panel): if measured non-agent time exceeds about 4,320 s (half the margin), or any step
goes ungraded, change to two steps or to the flat bundle before any model run.

**Harbor detail.** In the installed Harbor (0.25.0, `feea734`), a step's verifier timeout comes from
`[steps.verifier] timeout_sec`, whose default is 600 s even when the task-level `[verifier] timeout_sec` is set
(`trial.py`, `_step_verifier_timeout_sec`). Every step therefore sets it explicitly. The platform's Harbor build is
checked for the same behaviour before upload.

## Reward strategy

`multi_step_reward_strategy = "final"`: the trial reward is step 3's reward. It re-grades every unit against
15.2.0, so it equals the flat bundle's score on the same tree, and the two layouts share one scale. Steps 1 and 2
are recorded and published as the per-release diagnostic. A missing step-3 reward means a lost trial: never 0,
never filled in from step 2.

## Acceptance criteria per step

These are build-side criteria. A version is not uploaded until all of them pass; their outputs go into the README as
evidence.

### Step 1: `01-releases-14.3.1-to-15.0.0` (gold 15.0.0)

- **Units graded:** 26, 11, 30, 36, 33, 35, 37, 16, 47a. **Families:** F1, F2, F4, F6, F7, F8.
- **Held fixed:** the duals of the window's conditional units and the broad set. Every held-fixed case is unchanged
  at 14.3.0, 15.0.0, 15.1.0 and 15.2.0.
- **Must pass:**
  1. Oracle (the tree patched to 15.0.0): 1.000 on two local runs and two platform runs.
  2. Nop (the untouched tree): 0.000 on two runs.
  3. Stub zoo (QA-PLAN.md): 0.000 for every member.
  4. Kill matrix: each R_k built on 15.0.0 fails at least 3 (target 20) of its own unit's cases and none of any
     other unit's. A unit without an isolating revert is merged or cut.
  5. 3+1 determinism: byte-identical per-case verdicts.
  6. Fail-soft: a tree that does not build scores 0, the verifier exits cleanly with `metrics.json`, and step 2
     starts.
- **Regression on earlier steps:** none (first step).
- **Expected reward:** oracle 1.000; nop 0.000. Agents (estimate): frontier 0.5-0.8, mid-tier 0.2-0.5. The window is
  mechanical but heavy (Unicode 18 tables, about 30 saturation commits).

### Step 2: `02-release-15.1.0` (gold 15.1.0)

- **Units graded:** step 1's 9, re-checked against 15.1.0, plus 10a, 10b, 19, 25a, 25b, 25c, 31, 34, 44a, 44b, 45,
  46 and 51. **Families:** all of step 1's plus F3.
- **Must pass:** 1-6 as in step 1, with the oracle patched to 15.1.0 and R_k built on 15.1.0, plus:
  - **Carry-over stub** (the 15.0.0 tree): scores the predicted share of step-1 units whose cases 15.1.0 left
    unchanged, about 9/22 ≈ 0.41. Recorded, and it must match the prediction to the third decimal.
  - The two new API functions are declared in `hb-buffer.h`. The driver that calls them is a separate program, so a
    tree without them fails only unit 51.
- **Regression on earlier steps:** every step-1 case is re-graded against 15.1.0. A case that 15.1.0 changed again
  moves to the step-2 unit that explains it, or is dropped.
- **Expected reward:** oracle 1.000; nop 0.000. Agents (estimate): frontier 0.45-0.7, mid-tier 0.15-0.4. The `kerx`
  and `kern` units need fonts the agent must build from the binary layouts.

### Step 3: `03-release-15.2.0` (gold 15.2.0; the trial reward)

- **Units graded:** 56: every earlier unit re-checked against 15.2.0, 47a's cases now under 47b, plus window C's 35.
  **Families:** F1-F8, H_dual, H_broad.
- **Must pass:** 1-6 as before, with the oracle patched to 15.2.0, plus:
  - **Carry-over stub** (the 15.1.0 tree): about 21/56 ≈ 0.375, predicted and recorded.
  - **Band check** (QA gate item 12): mutant W scores at least 0.98 on D, at most 0.5 on h_d, at least 0.95 on h_b
    and on each of F1-F8. Its reward lands in 0.60-0.85, and no R_k or R_flags shares its signature. The dual
    weight (0.20-0.35) is fixed here.
  - **Flat parity:** the flat bundle's verifier gives the same per-case verdicts as this step on the oracle, the
    nop and W.
- **Regression on earlier steps:** all 21 surviving units from windows A and B re-graded against 15.2.0.
- **Expected reward:** oracle 1.000; nop 0.000; W 0.60-0.85. Agents (the report's estimate): frontier 0.35-0.65,
  mid-tier 0.10-0.30, with no full solve, F8 and F2 high, and F4, F5 and the dual gate low.

## Platform acceptance before any model run

On top of the standing rules (the Oddish pre-trial QA verdict on the version, oracle and nop baselines, 20 QA
passes):

1. **The capped oracle chain (panel Q3, B).** One oracle trial of the steps bundle, each step's oracle sleeping past
   its `timeout_sec`, on the exact version models will use. Pass: three graded steps, each 1.0, with per-phase wall
   times recorded in the README. It is repeated whenever `environment/` or `tests/` changes.
2. **The switch rule** above, applied to those measured times.
3. **One attempt per model trial** (`max_trial_attempts: 1`), with the attempt-1 error text read for every trial
   that reaches a cap. The first capped trial that goes ungraded stops the campaign.

## Single-step fallback

The packager also builds a flat bundle under the same task name: one instruction that is the three step requests
merged into one (every window's notes at once, `hb_font_set_face()` as 15.2.0 has it), `timeout_sec` 34,560, and the
step-3 verifier (`RELEASE=15.2.0`). It is used for Proximus, which refuses `[[steps]]`, and if the steps layout fails
its platform acceptance. Every trial is labelled steps or flat, and the two are reported separately: the step
boundaries prompt the agent to keep going in a way a flat run never gets.

## Phase B work for the steps

- `common/verifier/`: the one verifier source (Dockerfile, `test.sh`, `verify.py`, `verifier/` with the drivers'
  C source, the case runner and the scoring), staged into each `steps/<step>/tests/` by the packager.
- `steps/<step>/workdir/docs/notes/` and `…/docs/examples/`: the window's notes and example fonts.
- `steps/<step>/solution/solve.sh`: applies the window's upstream patch (generated from the tags into the
  git-ignored `solution/private/`) to `/app/harfbuzz`.
- `scripts/package_steps.py` and `scripts/package_flat.py`, writing to `experiment/dist/`.
- The restated notes (rating R in the inventory), written into each instruction after the spike shows that the
  rule pins the release's output.
