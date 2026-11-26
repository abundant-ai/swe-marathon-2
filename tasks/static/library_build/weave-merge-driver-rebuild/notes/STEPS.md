# Weave merge-driver rebuild: steps, acceptance criteria, reward strategy (Phase A, 2026-11-26)

Author notes. The decision record, with the brief and the three votes verbatim, is in harbor-lh:
`ops/swe-marathon-v2/decisions/2026-11-26-weave-merge-driver-rebuild-steps-{BRIEF,opus,sonnet,haiku,DECISION}.md`.

## 1. Decision

The suggested split ("0.6 engine, then 0.7.1's gate and changes") rests on a misread history: the
gate shipped in 0.6.0 (2026-10-19). Within scope, 0.6.x to 0.7.1 changes about 120 merge-path lines
(`region.rs` +79/-40 and `binding.rs` +29/-13 in 0.7.0; nothing in 0.7.1); the release with new
behaviour is 0.5.4 to 0.6.0 (27 merge-path files, weave-core source 778 KB to 1,131 KB, the
expression fold deleted). The panel chose among four structures:

| Option | Steps | Votes |
| --- | --- | --- |
| A | one step: rebuild 0.7.1 | haiku |
| B | 0.6.2, then the 0.7.0/0.7.1 changes | sonnet |
| C | 0.5.4, then the 0.6.0-0.7.1 releases | opus (built in stages, A first) |
| D | 0.6.2, then 0.7.1 plus Rust and Java | none |

**No majority; the tie rule gives the more conservative option: build A first.** All three agreed
that A is the base of every option (Proximus refuses `[[steps]]`; both chains reuse A's verifier as
their last step), that any chain uses `final`, and that a chain needs one idle full-length chain
graded in every step before any model trial. Whether a chain follows is decided on spike days 4-5
by each judge's own measurable condition (section 5).

## 2. Platform facts that shape every step

- Harbor runs every step in one sandbox; files persist; each step has its own instruction, tests,
  solution, verifier run, reward and `[steps.agent] timeout_sec` (falling back to `[agent]`).
- `multi_step_reward_strategy`: `mean` (the default) drops a step that has no verifier result, so a
  lost later step can raise the score; `final` uses the last step's result. **`final`.**
- Oddish's 43,200 s attempt holds the whole chain, image builds and verifiers included. Agent time
  stays at 34,560 s in total, leaving 8,640 s for two verifier runs (an estimated 7-18 minutes each
  with pre-recorded outputs, 15-30 with recording at image build).
- Proximus refuses `[[steps]]`: it gets the flat bundle (A).
- No task-side stop before a step's `timeout_sec`.
- Step material arrives through `steps/<step>/workdir/` (uploaded as the agent user; its optional
  `setup.sh` runs as that user and is visible, so nothing secret goes there) and through a root
  collect hook at the end of the previous step, which can swap in a new execute-only build from a
  root-only staging directory. Per-step root collect hooks ran in the 2026-11-19 canary.
- Per-step verifier images were graded in a short canary; a heavy-verifier run capped at 9.6 h was
  graded in both layouts on 2026-11-24 (n = 1 each).

## 3. Plan A: one step (adopted)

| | |
| --- | --- |
| Agent gets | the 0.7.1 build (execute-only), our specification written from the `v0.7.1` tag, `git`, Rust, the 82-crate offline registry (`sem-core` 0.29.0 with three grammars, `diffy` 0.5.2) |
| Agent delivers | `/app/driver`, a Rust project that builds offline into `target/release/weave-driver` |
| `timeout_sec` | 34,560 |
| Families graded | F1-F10 (DESIGN.md section 3), about 1,200 kept cases, F8 (the gate) 20% |
| Reward | `sum_f w_f * g_f` with per-family stub netting; no `multi_step_reward_strategy` |

**Acceptance criteria before the first upload (all must hold):**

1. Oracle (upstream source built against the agent's crates and features) scores 1.0 in two runs;
   nop scores 0 in two runs; the stub zoo's reward is 0.000 (every Z and N stub).
2. Every feature id has at least 3 killing cases in its own family and every stated restriction at
   least 1 (QA-PLAN.md, gate items 1-2).
3. M-gate scores 1 - w_F8 = 0.80 with F8's net credit at 0 and every other family at 1.0; no other
   mutant has F8-only movement; each mutant moves its own family by at least 50 points.
4. Byte-identical verdicts over 3 runs plus 1 perturbed; verifier wall time (offline build plus
   every case) within 30 minutes on 4 CPUs.
5. The cue-word sweep is clean over the instruction, `/app/docs`, file names and the build's
   `--help`; the protection probe fails every route to the binary's bytes.
6. A full-length idle canary of the flat bundle is graded within 43,200 s.

**Expected:** the original 1.0 by construction; frontier about 0.45-0.70, mid-tier about 0.15-0.40
(untested).

## 4. The two candidate chains (designed, not adopted)

Common to both: `multi_step_reward_strategy = "final"`; a trial missing any step's result is
reported as lost, never as 0; every step's instruction restates every requirement (a step may start
a fresh session); step 1 says that new releases will come, never how many or when; step-2 material
(the new build, its notes, new crates) sits in a root-only staging directory with a neutral name
until step 1's collect hook swaps it in; step 2's verifier is A's verifier with A's cases, so the
headline is comparable with A and the flat bundle is A.

### Chain C: 0.5.4, then the 0.6.0-0.7.1 releases

| | Step 1: `01-rebuild-driver` | Step 2: `02-follow-releases` |
| --- | --- | --- |
| Story | Rebuild the installed 0.5.4 (August-September 2026 engine) | Our fleet moved to 0.7.1; follow upstream's 0.6.0-0.7.1 notes |
| Agent gets | 0.5.4 build (execute-only); a 0.5.4 specification limited to the core, the statement fold and the old line route; a registry with the 0.5.4 lock's crates (`sem-core` 0.23.0, its grammars) | the 0.7.1 build swapped in place; upstream's notes for 0.6.0-0.7.1 scrubbed to scope; the revised specification; `sem-core` 0.29.0 and its grammars added |
| `timeout_sec` (opus) | 14,400 | 20,160 |
| Families graded | F1-F5, F7, F10 at 0.5.4 behaviour plus F4's 0.5.4 fold cases; no F6, F8, F9 (they do not exist in 0.5.4); about 400 cases, cases where the token-level expression fold fires dropped by an instrumented build | F1-F10 at 0.7.1: exactly A's cases |
| Regression | none (first step) | carried-over behaviour is re-graded at 0.7.1 in F1-F5, F7, F10 |
| Original's expected score | 1.0 (0.5.4 oracle) | 1.0 (0.7.1 oracle) |
| Reward | diagnostic only | the trial's reward (`final`) |
| What the step adds | a working engine to build on | the gate, the element union and its guards, the region rules, line-granular composition replacing the folds, the new import rule, the lossless split: refusals retrofitted into an engine built to compose |

### Chain B: 0.6.2, then the 0.7.0/0.7.1 changes

| | Step 1: `01-rebuild-driver` | Step 2: `02-follow-release` |
| --- | --- | --- |
| Story | Rebuild the installed 0.6.2 | Our fleet moved to 0.7.1 |
| Agent gets | 0.6.2 build; a 0.6.2 specification; `sem-core` 0.28.0 registry | the 0.7.1 build; the 0.7.0/0.7.1 notes in scope (lossless split; `sem-core` 0.29); the revised specification; `sem-core` 0.29.0 added |
| `timeout_sec` | 26,000 (sonnet) or 24,000 (haiku) | 8,000 (sonnet) or 10,000 (haiku) |
| Families graded | F1-F10 at 0.6.2 | F1-F10 at 0.7.1 (A's cases) plus at least about 100 step-2-only cases in F1's layout sub-family (CRLF, a missing final newline, entities sharing a line) |
| Regression | none | everything else in A's cases |
| Original's expected score | 1.0 | 1.0 |
| Reward | diagnostic only | the trial's reward |
| What the step adds | the whole engine, gate included | a layout change of about 120 lines |

## 5. How the chain question is settled (spike days 4-5)

Both measurements score a second build of upstream against A's cases with A's verifier.

| Chain | Adopted only if | Prediction (author's, unmeasured) |
| --- | --- | --- |
| B | at least about 100 step-2-only discriminating cases, and a 0.6.2 build scores at most 0.85 of the 0.7.1 build on A's cases (sonnet); a steps-layout heavy-verifier canary graded at the cap in 2 of 2 runs (haiku) | fails: 0.6.2 and 0.7.1 differ only in layout and binding code, so a 0.6.2 build should score close to 1.0 on A's cases |
| C | the 0.5.4 offline build is byte-identical over 3+1 runs; a 0.5.4 build lands at 0.25-0.70 on A's cases with F8 at 0; the fold-tagged step-1 set (about 400) survives the stub filter; entity differences between `sem-core` 0.23 and 0.29 are known; an independent review passes the 0.5.4 specification; the 0.7.1 material is invisible in step 1; the oracle chain scores 1.0 and 1.0 and nop 0 and 0; an idle chain is graded in both steps within 43,200 s (opus) | plausible: 0.5.4 has no gate, element union or region rules, so F6, F8 and F9 and many F4 cases should fail |

If both qualify, a new panel chooses. If neither, A ships alone. After adoption, switch back to A if
a chain loses a step's grade on the platform, or the first three mid-tier chains all score under
0.10.

## 6. Layout if a chain is adopted

```text
weave-merge-driver-rebuild/
├── task.toml                      # [[steps]] 01-rebuild-driver, 02-follow-release(s); final
├── environment/                   # one agent image: both builds, the step-2 build root-only until swapped
└── steps/
    ├── 01-rebuild-driver/{instruction.md, tests/, solution/}
    └── 02-follow-release(s)/{instruction.md, workdir/, tests/, solution/}
```

The flat bundle for Proximus is A: the root `instruction.md`, `tests/` and `solution/` of this
directory, identical to step 2's verifier and cases. Draft step instructions for both chains are in
`notes/steps/`.

```toml
# Fragment for chain C (opus's budgets); chain B would use 26000 + 8000
multi_step_reward_strategy = "final"

[[steps]]
name = "01-rebuild-driver"
[steps.agent]
timeout_sec = 14400

[[steps]]
name = "02-follow-releases"
[steps.agent]
timeout_sec = 20160
```
