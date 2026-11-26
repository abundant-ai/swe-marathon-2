# QA plan (Phase A, 2026-11-26)

Author notes, never shipped. This plans the checks that must pass before the first upload:
- the 12-item pre-upload gate from the grading guide (section 12), mapped to this task;
- the coverage inventory;
- the stub zoo;
- the wording sweep;
- the 20 independent QA lenses (the owner's rule: at least 20 adversarial passes before any run);
- the checks applied after the first trials.

Nothing here has run yet.

**Where the evidence goes:**
- The gate scripts live in task-root `checks/` (tracked, never shipped).
- Their outputs are committed into the README's evidence section.
- QA reports go to the private ops repository (`qa/dogwood/NN-<lens>.md` plus `SUMMARY.md`).

## 1. The 12-item gate, mapped to this task

Every item runs per step: 1.1.2 at step 1 and 1.2.0 at step 2. Upload is blocked while any item
fails.

| # | Gate | Pass criterion here | Planned script |
| --- | --- | --- | --- |
| 1 | Inventory complete | `features.yaml` per version, extracted mechanically from the shipped docs and `--help` (section 2). A diff against the docs shows nothing unlisted; every id names its family and the doc line it comes from | `checks/test_inventory.py` |
| 2 | Feature-kill matrix | Every feature id has at least 3 kills in its own family, and every restriction id at least 1, preferring 2 by different routes (for example a `validate` near-miss and a `check-parse` error). A killing mutant fails as a case and never crashes the grader. 40-80 source-patched mutants per version, built on a Linux build machine; only the cases whose reference coverage touches the patched code are re-run | `checks/test_kill_matrix.py` (reads recorded results) |
| 3 | Stub zoo at 0.000 | Every member of section 3 scores 0.000 after pairing and baseline subtraction at both steps; raw pass rates recorded. A case any stub passes on its own is dropped or paired | `checks/test_stub_zoo.py` |
| 4 | Oracle and nop | The reference is 1.000 on at least 2 local runs and 2 platform runs per step, and nop is 0.000 the same way. At step 2, the no-upgrade anchor (1.1.2's source) scores 0.55-0.80 | `checks/test_baselines.py` plus the platform baseline rows |
| 5 | Determinism | 3 identical runs plus 1 perturbed run give byte-identical per-case verdict files, with matching hashes. The perturbed run uses 1 CPU, a longer path, another `HOME` and another umask. Multi-permit replays and multi-environment validations repeat at least 10 times; 1.1.2's diagnostic order is filtered for stability | `checks/test_determinism.py` |
| 6 | Wording sweep | Zero unjudged hits on the surfaces in section 4. Each hit is fixed or whitelisted with its sense | `checks/test_wording.py` |
| 7 | Protection probe | As `dev`, inside the real sandbox, every attempt fails, at both steps: read, copy, `ptrace`, `LD_PRELOAD`, `/proc/<pid>/{exe,mem,maps}`, core dumps, `strings`, and listing or reading `/root/.staging` during step 1. `id -u` is not 0 and there is no `sudo` | `checks/test_protection.py` (driver) plus the in-sandbox probe script, run by the oracle |
| 8 | Verifier robustness | Each step's verifier image is prebuilt and pinned. It must grade the oracle at 1.000 within 50% of 2,700 s on a long-run smoke: a 5 GB `target/`, 100k files, leftover processes, odd file types. A forced runner exception is an evaluation error and leaves no reward | `checks/test_verifier_smoke.py` |
| 9 | Isolation and timeouts | A submission that hangs on one case, forks a bomb, prints 10 GB, or has a `build.rs` that loops or reads the grader's files loses only those cases or fails its build. The other cases' scores are unchanged. The submission builds as `builder` and runs as `nobody`; neither can read gold | `checks/test_isolation.py` |
| 10 | No early stops | No timer, kill or deadline of ours ends an agent phase before its `timeout_sec`. The only deadlines are the verifier's own global deadline and the per-case 5 s limit, which the brief states | `checks/test_no_timers.py` (grep plus `task.toml` arithmetic) |
| 11 | Leak scan | No hidden input contains its answer. No agent-visible file contains a hidden case or a near-copy of one. Hidden cases never equal or near-copy a shipped example or a public upstream corpus case (578 temporal, 155 macros, 262 expected-failure, 80 probes, 93 bundles; by normalised AST of the policy and the trace's event sequence). Steps use disjoint seeds | `checks/test_leaks.py` |
| 12 | Band check | M-dedup scores 0.70-0.85 (about 0.82) with only B-dedup moving; M-scope moves only B-scope; no other mutant shares either signature; M-global's K drop is recorded for the difficulty ordering | `checks/test_band.py` |

## 2. Coverage inventory: every documented feature and stated restriction gets cases that fail without it

**What the inventory extracts from the shipped docs of each version:**
- the grammar productions of chapter 08's concrete syntax, and the temporal and event-schema
  grammars as the guide states them;
- each bold rule name in chapter 08;
- each H2/H3 heading and each bullet in chapters 02-06, 09, 10 and 12;
- every command, subcommand, option and value from `dogwood --help` and each subcommand's
  `--help`;
- every error class the docs name;
- every sentence with "must", "must not", "only", "cannot", "is an error", "rejects", "fails"
  or "at most".

**Ids.**
- Each item becomes an id: `feat:` or `restr:`, plus the chapter and slug.
- Each id records the doc line it comes from, the family that grades it, and the route that
  observes it: `replay`, `validate`, `lower`, `explain`, `format`, `check-parse` or `schema`.
- A person then merges duplicates and splits compound sentences. Merges are recorded, not
  silent.

**Known restriction groups** (each needs at least 1 rejecting case, preferring 2):
- no `||` in temporal blocks;
- only `s`/`m`/`h`/`d` units and integer amounts;
- `within` is mandatory;
- closedness and range restriction;
- producer before consumer;
- every `for` variable bound and positively restricted;
- `sum` over a `for` variable;
- aggregates only as comparison operands;
- parenthesised non-final aggregates;
- tp-dependence (no degenerate scopes);
- the binder-type rules;
- `==` type rules;
- no `min`/`max`/`avg`;
- pins only on leaves;
- the selector misuse errors;
- duplicate kinds (1.2.0);
- `max_window` up to `max_horizon` (1.2.0) and a zero cap;
- the macro rejection classes: arity, kind, shape, hygiene, reserved names, no macro inside a
  macro, plain identifiers in `def temporal` bodies;
- the provider declaration errors and `paramType` rules;
- the parse limits (depth 32, 1,000,000 nodes, 64 open brackets in an action schema);
- integer literals outside `i64`;
- `has` and `like` right-hand sides;
- relational chains without parentheses;
- record keys;
- 1.2.0's new validation checks and load errors, one by one.

**Out-of-scope ids:**
- `schema mcp`, the Rust API, `net` and LSP get ids marked out of scope.
- No case uses them.
- A check confirms that no hidden case touches an out-of-scope id.

**Unchecked statements:**
- A stated restriction the build does not enforce (the timestamp contract) is reworded in the
  shipped docs. It is not a restriction id.
- Hidden traces stay inside the contract.

**Step 2:**
- Every CLI-observable 1.2.0 release-note item is an id with at least 3 changed cases (target 10)
  and an unchanged dual.
- The 15 or so Rust-API and build-only entries are listed as excluded, with a reason each.

**Two-way trace:**
- Every case lists the feature ids it exercises.
- A case with no id is a bug (an undocumented behaviour), and so is an id with no case.
- This is how back office v11 (5 untested routes) and BasedPL v6 (zero-case functions, an
  unchecked sandbox) would have been caught.

## 3. Stub zoo

Each member is delivered the way a submission is: a small Cargo project whose `dogwood` binary
implements the stub, built and run by the real verifier.

| # | Stub | Expected raw pass rate before pairing | What zeroes it |
| --- | --- | --- | --- |
| Z1 | Empty project (nop) | 0 | build fails |
| Z2 | Prints nothing, exits 0 | 0 | every case has non-empty stdout |
| Z3 | Prints nothing, exits with each command's most common status | 0 | stdout compared too |
| Z4 | `validate` prints "OK: validation passed with no errors or warnings." (or the JSON equivalent) | the accepted share of V | accept/near-miss pairs |
| Z5 | `validate` always rejects with a generic finding | 0 (message and spans differ) | stdout compared |
| Z6 | `replay` parses trace lines and prints all DENY | single-verdict streams | R/B/K streams mixed, or paired with a mixed dual |
| Z7 | `replay` all ALLOW | as Z6 | as Z6 |
| Z8 | `format` as `cat` | already-formatted input; comment-inside-statement cases | `format` cases differ from their input, except the comment rule's, which are paired with a formatting case |
| Z9 | `check-parse` counts `permit`/`forbid` and prints "OK: parsed N policies." | clean parses without temporal or provider notes | paired with syntax-error cases; most clean cases carry temporal notes |
| Z10 | `schema …` prints "OK: … schema is valid." | valid schemas | paired with invalid ones |
| Z11 | `lower` echoing the Cedar part through `cedar-policy`'s printer, no hoisting | Cedar-only policies | under 10% of L is Cedar-only; paired with a temporal twin |
| Z12 | Lookup table of every agent-visible example output | 0 by the leak rule | leak scan (gate 11) |
| Z13 | Wrapper that runs `dogwood` or `dogwood-1.1.2` from `PATH` | 0 in the verifier (no build) | integrity gate; the verifier also checks the binary for the shipped builds' hashes |
| Z14 | The 1.1.2 reference source submitted at step 2 (no-upgrade anchor) | 0.55-0.80 | not a stub: the measured anchor of STEPS section 4 |

Every member's raw and gated scores are recorded per family and per step. The gate requires all of
Z1-Z13 at 0.000.

## 4. Wording sweep

**Surfaces** (everything the agent can read or run, at both steps):
- both step briefs;
- every shipped guide chapter;
- `RELEASE_NOTES.md`;
- the 93 bundles' READMEs and policy comments, and every file and directory name under `/app/docs`;
- `--help` and every subcommand's `--help` of both builds, plus the error and warning texts the
  builds print on the probes we run;
- `setup.sh`, if it survives;
- environment variables in the sandbox;
- `/etc/motd`, shell profiles, `~/.cargo/config.toml`, and the registry's crate names;
- image paths and user and group names;
- the stub-free starter state of `/app/dogwood-rebuild`.

**Word classes** (case-insensitive, stems):
- "evaluat", "benchmark", "grade", "score", "test", "hidden", "held-out";
- "reference", "oracle", "gold", "golden";
- "told apart", "indistinguishable", "identical to", "exactly as", "behave exactly like";
- "budget", "deadline", "session", "verifier", "verify";
- "corpus", "harness", "conformance", "trial";
- "sealed";
- time budgets of any kind.

**Judging rules:**
- **Whitelisted senses**, each recorded with its sentence:
  - "evaluate" for policy evaluation in the guide;
  - "conforms" and "nonconforming" for events against their schema;
  - "session" for an agent's or user's session in policy examples;
  - "budget" for a refund budget in a policy;
  - "score" in field names such as `confidenceScore`.
- **Never whitelisted:** the authoring senses of "test", "corpus", "oracle", "harness" and
  "reference interpreter". They are rewritten or cut.
- **Measured load** (1.2.0 guide): "evaluat" 177, "corpus" 45 (24 case citations), "test" 34,
  "session" 23, "conformance" 9, "reference interpreter" 5, "harness" 4. Example READMEs:
  "corpus" 24, "test" 12, "harness" 4, "oracle" 1.

**The briefs.**
- Today's drafts are clean apart from the domain term "comparison operands" and the substring
  "grade" in "upgrade".
- Both stay in the requester's voice. Each requirement is stated by what depends on it. Both end
  with the cut-over line.
- No "step", "stage" or "session" wording, and no time budget.

**Known residue we cannot clean.** Harbor's own launcher line (`harbor_claude_code_instruction_…`)
is visible to `ps`. It is recorded as residue.

## 5. The 20 QA lenses

**How each pass runs:**
- A fresh agent with one lens and no stake in the task.
- Read-only on the task repository; no Oddish, no Docker.
- Each writes `qa/dogwood/NN-<lens>.md` with PASS, CONCERN or FAIL.
- `SUMMARY.md` resolves every FAIL before any run.

Lens 19 is specific to the two-step chain. It replaces the generic "comparisons" lens, whose
question moves into lens 17.

| # | Lens | The Dogwood-specific question |
| --- | --- | --- |
| 01 | Practitioner realism | Would a team gating agent tool calls with Dogwood commission a clean-room `dogwood`, and then the 1.2.0 move, in this form? What is artificial in owning an Apache-2.0 tool clean-room? |
| 02 | Input realism | Do the generated policies, schemas and traces look like AgentCore-style policies (tool actions, `callerPrincipal` pins, windows up to 24 h, providers), or like grammar noise a model could exploit? |
| 03 | Instruction realism | Do both briefs read like a real platform team's request? Would that team really have the consumers named, the run conditions stated and the out-of-scope list? Does step 2 stand alone? |
| 04 | Attack: the builds | From `dev`, can either build be read, copied, traced, preloaded, dumped or recovered from `/proc`? Can 1.2.0 be found or run during step 1? |
| 05 | Attack: lookup tables | Can probing the build plus the shipped bundles be turned into a table or a narrow special-case engine that passes hidden cases? Are the dual pairs enough? |
| 06 | Attack: leaked answers | Does anything visible reveal hidden inputs, gold or the grading? Candidates: docs, bundle READMEs, `setup.sh`, the registry, image layers, file names, step 1's verifier residue in step 2 |
| 07 | Attack: the verifier | Can the submission's `build.rs` or proc macros read gold or the grader, write a reward, or leave processes behind? Can an oversized `target/` or link trick break artifact transfer? |
| 08 | Attack: network and source | Is any Dogwood source reachable? Check cargo caches, the registry, docs links, pip or apt caches, the Lean spec. Is the registry exactly the allow-list? |
| 09 | Evaluation cues | What in the briefs, docs, `--help`, error texts or sandbox signals "this is a test"? The guide's own "test authors" and "corpus" passages are the main hazard |
| 10 | Verifier bugs | Line by line: rule-list normalisation, JSON comparison, exit status, stdout capture, per-case limits, the global deadline, build-failure handling, metrics and reward writing, evaluation-error paths |
| 11 | Determinism | Can the hash-set rule order, 1.1.2's unordered diagnostics, Cedar's schema printer, Rhai or the environment make a recorded output flake? Is 3+1 enough? |
| 12 | Spec vs grading | Is every graded behaviour stated in the shipped docs or the brief? Is every stated restriction checked? Is anything out of scope graded? |
| 13 | Oracle, nop and anchor | Do both references score 1.000 legitimately, nop 0, and the no-upgrade anchor 0.55-0.80? Could a trivial submission score above 0? |
| 14 | Horizon: human estimate | Break the 1.1.2 rebuild and the 1.2.0 move into parts: how many days for a strong engineer new to Dogwood? |
| 15 | Horizon: agent estimate | How many hours and steps would a capable coding agent need for step 1 (21,600 s) and step 2 (12,600 s)? Where does it stall? |
| 16 | Horizon: shape | Is the work a dependent chain (parser to relational evaluator to slicing to validation) or farmable pieces? Does step 2 depend on step 1's architecture? |
| 17 | Difficulty: frontier and comparisons | What would a frontier model reach at each step? How does that compare with MirrorCode, SWE-Marathon v1, Goose (0.30-0.36 mid-tier) and Carve (0.56-0.76 mid-tier)? Too easy, about right, or impossible? |
| 18 | Difficulty: the tail | Are the hardest 20% (B, K, V-msg, `explain`, the silent 1.2.0 verdict changes) reachable from the shipped material alone? |
| 19 | Step boundary and upgrade | Does anything from step 1's grading reach step 2? Is the registry a superset, is `setup.sh` idempotent and silent, and do the timings fit 43,200 s? Is the changed partition right both ways, and is the 1.2.0 release-note trim faithful? |
| 20 | Red team | The single strongest reason to reject this task |

## 6. After the first trials: is it a "good failure"?

A trial's failure counts as a result only if all of these hold. Otherwise it is a defect to fix
before any score is shown.

1. **Baselines.** Reference 1.000 and every stub 0.000 at both steps, on the version that ran.
   The no-upgrade anchor is inside 0.55-0.80.
2. **Still rising at the cap.** The per-step score was still rising at the cap: the agent was
   mid-feature, not stalled or idle. This is read from the trajectory and the step-1 versus final
   scores.
3. **Fair cases.** Every failed case traces to a documented feature id. At least one trial, the
   reference, or a second implementation passes it, which rules out "overly strict" cases.
4. **Named families.** Failures cluster in named families, and the labelled failures test the
   sentence: is B, specifically B-dedup, the lowest family in most trials? Are K and the step-2
   changed partition next? If not, re-run the solvability derivation for the family that
   dominates before touching difficulty.
5. **Clean run.** No infrastructure error, no stop forced by the task, no lost step 2 (a lost
   step is reported as lost, never as 0), and no evaluation-awareness finding in any trajectory.
6. **No special-casing.** Submissions are scanned for long literals matching visible
   `expected.out`/`explain.out` text (report, not auto-zero). The scan covers wrappers around the
   builds too.
7. **Honest step 1.** Step 1's reported score is consistent with what the agent built: a low
   step-1 score followed by a high final score is read in the trajectory, not assumed.
