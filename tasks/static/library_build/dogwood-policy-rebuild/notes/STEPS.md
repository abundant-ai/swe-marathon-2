# Steps, acceptance criteria and the panel decision (2026-11-26)

Author notes, never shipped. The brief the panel read, the three votes and the decision record
live in the private ops repository (`harbor-lh`). The record is
`ops/swe-marathon-v2/decisions/2026-11-26-dogwood-policy-rebuild-steps-DECISION.md`.

## 1. The decision

The owner asked for multi-step where possible. Three judges (opus, sonnet, haiku) read the same
brief with four options:
- **S:** single step, rebuild 1.2.0.
- **M2a:** rebuild 1.1.2, then upgrade to 1.2.0.
- **M2b:** rebuild 1.0.2, then upgrade to 1.2.0.
- **M3:** 1.0.2, then 1.1.2, then 1.2.0.

| Question | opus | sonnet | haiku | Result |
| --- | --- | --- | --- | --- |
| Q1 structure | M2a | M2a | M2a | **M2a, unanimous** |
| Q2 reward | final | final | final | **`final`, unanimous** |
| Q3 agent budgets | 21,600 + 12,600 | 20,700 + 12,600 | 21,600 + 12,600 if each verifier fits 2,700 s | **21,600 + 12,600 (2 to 1)**, with sonnet's 20,700 as the fallback (section 6) |
| Q4 step-2 reward | plain families | plain families | plain families | **Plain capability families on 1.2.0 gold, unanimous;** the changed cases are a reported metric |
| Q5 tell step 1 that releases follow | yes | yes | yes | **Yes, unanimous;** never how many or when |

**Cost follow-up.** The brief said +3-5 person-days per extra version. The itemised estimate
([DESIGN.md](DESIGN.md) section 7) is +8 to +9. All three judges were asked again, and none
changed Q1 (votes appended to their files).

**Build order (opus, in the follow-up):**
1. Build S's assets first: the 1.2.0 build, docs, gold and verifier. They are step 2's assets, and
   S can ship alone.
2. Spend the extra 8-9 person-days on step 1 only after a long-chain probe shows the heavy
   last-step verifier grading reliably. If it does not, ship S.

The spike ([SPIKE-PLAN.md](SPIKE-PLAN.md)) follows this order.

**Why M2a, from the votes:**
- Upstream wrote the 1.2.0 notes against 1.1.2 ("All comparisons in this section are with 1.1.2",
  ending in upgrade notes), so step 2 is a real upgrade of the agent's own code, not a
  manufactured dependency.
- M2b would stitch notes written against two bases. It would also load step 2 with all of
  `explain`, which is specified mostly by example.
- M3 leaves about 900 s of the 43,200 s cap for three setups and collections.
- The last step's verifier is S's, so S stays a drop-in fallback and the rewards stay comparable.
- Plain families keep B at its full weight. The rejected 0.75/0.25 split would have given an
  un-upgraded tool 0.75 and handed an always-reject stub the new-rejection items at full per-item
  weight.

## 2. The chain

| | Step 1 `01-rebuild` | Step 2 `02-upgrade` |
| --- | --- | --- |
| Brief | [steps/01-rebuild/instruction.md](../steps/01-rebuild/instruction.md) | [steps/02-upgrade/instruction.md](../steps/02-upgrade/instruction.md), standing alone (fresh session) |
| `dogwood` on `PATH` | 1.1.2 (`929f49e7`) | 1.2.0 (`8ffd2106`); 1.1.2 kept as `dogwood-1.1.2` |
| Docs | `/app/docs/1.1.2` | adds `/app/docs/1.2.0` (guide, bundles, trimmed release and upgrade notes) |
| Registry | Cedar 4.11.0 and the 1.1.2 crate set | the same, plus Cedar 4.14.0, `rustc-literal-escaper` 0.0.8 and new transitive crates; nothing removed |
| `[steps.agent] timeout_sec` | 21,600 | 12,600 |
| `[steps.verifier] timeout_sec` | 2,700 | 2,700 |
| Graded against | gold from the 1.1.2 build | gold from the 1.2.0 build |
| Counts toward the trial reward | no (reported) | yes (`final`) |

## 3. Step 1 acceptance criteria (1.1.2)

**What must pass before upload:**
1. **Reference 1.000 at step 1, twice locally and twice on the platform.** The reference is
   upstream 1.1.2's source with our frozen lock, delivered by `solution/solve.sh` and built by the
   step-1 verifier offline.
2. **nop 0.000, twice locally and twice on the platform.**
3. **Stub zoo 0.000 after the gate** ([QA-PLAN.md](QA-PLAN.md) section 3), with each member's raw
   pass rates recorded.
4. **M-dedup (1.1.2 source patched)** lands in 0.70-0.85 (predicted about 0.82). B-dedup drops at
   least 50 points, and every other family stays at 95% or more. **M-scope** drops only B-scope.
   No other mutant shares either signature ([CLAIMS.md](CLAIMS.md) section 4).
5. **Kill matrix.** Every 1.1.2 feature id has at least 3 kills in its own family, and every
   restriction id at least 1 (preferring 2).
6. **Determinism.** 3+1 runs give byte-identical verdict files. V-msg cases also pass the 10-run
   stability filter, because 1.1.2's diagnostic order is not fixed.

**Families graded:** all ten, on 1.1.2 gold ([DESIGN.md](DESIGN.md) section 3).

**Regression on earlier steps:** none (first step).

**Expected scores:**
- Reference 1.000.
- Frontier models 0.40-0.65 and mid-tier 0.12-0.30 at the step boundary (estimates).
- This number is reported in `metrics.json` and the step result; under `final` it does not
  count.

## 4. Step 2 acceptance criteria (1.2.0)

**What must pass before upload:**
1. **Reference 1.000 at step 2, twice locally and twice on the platform.** The reference is
   upstream 1.2.0's source with our frozen lock, built offline against the post-setup registry.
2. **nop 0.000 at step 2**, twice locally and twice on the platform.
3. **The no-upgrade anchor.** 1.1.2's reference source, delivered unchanged at step 2:
   - builds against the post-setup registry (which keeps Cedar 4.11.0);
   - scores 1.000 on the unchanged partition and 0.000 on the changed partition, both by
     construction;
   - scores between 0.55 and 0.80 overall.

   Above 0.80, the step needs more changed cases. Below 0.55, it measures little but the upgrade.
4. **The changed partition is at least 30% of step 2's cases.** Every CLI-observable 1.2.0
   release-note item (about 45 after the Rust-API and build-only entries are removed) has at least
   3 changed cases (target 10), each paired with an unchanged dual. A "changed" case is one whose
   1.1.2 and 1.2.0 outputs differ; every case is checked both ways.
5. **Stub zoo 0.000; M-dedup in band (about 0.82); M-scope B-scope only; kill matrix and
   determinism**, as in step 1, on 1.2.0. B keeps at least 20% of the final grade (it has 25%).
6. **The chain runs end to end.** An idle full-length chain (reference, and no-op) shows:
   - both steps graded;
   - step 2 still runs and is graded after step 1's verifier scores 0 or times out;
   - the totals fit (section 6).

**Families graded:** all ten, on 1.2.0 gold. The changed partition is reported per release-note
item and carries no separate weight.

**Regression on earlier steps:** the unchanged partition is exactly the 1.1.2 behaviour still in
force. A tool that breaks it while upgrading loses those cases in their own families. Behaviour
that 1.2.0 removed (`schema mcp`, string-typed trace values, ingesting non-conforming history
events) is graded the 1.2.0 way.

**Expected scores:**
- Reference 1.000; no-upgrade anchor 0.55-0.80.
- Frontier final 0.40-0.65; mid-tier 0.10-0.30 (estimates).
- On a working task, the changed partition trails the unchanged one, and B is still the lowest
  family.

## 5. Reward strategy: `final`

The trial reward is step 2's score.
- **Why not `mean`:** Harbor's `mean` leaves a step with no verifier result out of the
  denominator. A lost step 2 would therefore silently report step 1's 1.1.2 score as the trial's
  reward. Under `final`, a lost step 2 is a lost trial, which matches our rule of never reporting
  a lost run as 0.
- **No double counting:** step 2 grades the whole tool, so `final` does not double-count the
  behaviour that both versions share.
- **`min_reward`:** none. A weak step 1 must not stop step 2.

## 6. Timeouts and the attempt cap

**Budget arithmetic:**
- Oddish allows 43,200 s per attempt, everything included, with images prebuilt at upload.
- Agent 21,600 + 12,600 = 34,200 s, the single-step tasks' 34,560 s less 360 s.
- Verifiers 2 x 2,700 = 5,400 s.
- That totals 39,600 s and leaves 3,600 s for environment start, two step setups, two collections
  (a workspace with a Rust `target/` of several GB is excluded from the artifact copy, but the
  collection still walks it) and two verifier container starts.

**Acceptance:**
- The idle chain's measured total must be at most 42,000 s, and two idle chains must run before
  any model trial.
- If measured overheads exceed 2,400 s, step 1 drops to 20,700 s (sonnet's figure), giving
  4,500 s of slack.
- Each verifier must finish its full case count with a worst-case submission inside 2,700 s. That
  means every case at its 5 s limit, run 4 at a time, under a global deadline that fails the
  remaining cases with a fixed denominator. If it does not fit, the case count is cut, not the
  agent time.

**No task-side stops:**
- No timer, kill or deadline of ours runs before a step's `timeout_sec`; Harbor ends each agent
  phase.
- Every per-step field is set explicitly. In Harbor 0.25 a step's `[steps.verifier] timeout_sec`
  defaults to 600 s rather than inheriting the task-level value, and per-step network modes are
  only overrides.

## 7. What crosses the step boundary

**Persists:**
- `/app/dogwood-rebuild` and anything else the agent wrote. A step-1 agent may leave notes for
  its successor; nothing asks it to.
- The agent's home directory. Its `~/.claude` hooks or a `CLAUDE.md` would carry over too, which
  is realistic continuity and gains nothing.

**Installed at step 2** by `steps/02-upgrade/workdir/setup.sh` as root, before the agent starts:
- the 1.2.0 build;
- the 1.2.0 docs;
- the Cedar 4.14.0 crates added to the registry.

It is idempotent, uses no network, and deletes itself from `/app` when done. Its text holds no
grading or platform wording, because the agent can read it if it survives.

**Never in the sandbox:**
- step 1's cases, gold, per-case diffs and metrics, which live only in the separate verifier
  container;
- the seeds (steps use disjoint seeds);
- anything naming 1.2.0 before step 2 (root-only staging directory, probed as `dev` in step 1).

**To confirm in the spike:** that Harbor does not expose step names inside the sandbox. If it
does, the neutral names `01-rebuild` and `02-upgrade` still reveal only that a second request
exists, which the brief already says.

## 8. The single-step fallback (S)

**What it is:**
- One step, brief adapted from step 2's: a fresh clean-room rebuild of 1.2.0 with
  `/app/docs/1.2.0` only, `dogwood` = 1.2.0, no 1.1.2 build, and the 1.2.0 registry.
- Agent timeout 34,560 s.
- The verifier is step 2's, unchanged, with the same weights and reward formula, so rewards are
  comparable with the chain's.

**When it is used:**
- on harnesses that cannot run steps (Proximus);
- if either idle chain fails to grade step 2;
- if the platform's per-step verifier canary regresses.

It uploads under the same task name in the same experiment, as the flat bundles did on
2026-11-24.

## 9. Platform facts relied on

| Fact | Source |
| --- | --- |
| One sandbox; per-step agent timeout, instruction, verifier image (`steps/<N>/tests/`) and reward; `final` uses the last step's result verbatim; `mean` drops steps with no verifier result | Harbor 0.25 `trial/multi_step.py`, `models/task/config.py` (read in this repository's locked environment) |
| A step's `setup.sh` runs from its `workdir/` before the agent | `trial/multi_step.py` `_run_step_setup` |
| Per-step verifier timeout defaults to 600 s, not the task's | `models/task/config.py` `VerifierConfig.timeout_sec = 600.0`; `trial/trial.py` `_step_verifier_timeout_sec` |
| Multi-step only on claude-code-style harnesses; Proximus refuses `[[steps]]` | Oddish Proximus worker, probe of 2026-11-19 |
| Heavy per-step verifiers after long chains: all 4 such trials failed on 2026-11-19; a probe graded both layouts on 2026-11-24 (n = 1) | Platform write-up in the ops repository; cap probe of 2026-11-24 |
| No task-side stop before `timeout_sec` | Verdicts on BasedPL v2 and v4; panel of 2026-11-24 |
