# HarfBuzz forward-port: QA fix round 2

> **DRAFT (2026-11-28, about 04:00 UTC).** Every item's change is committed and pushed. The final re-recording cycle
> (c4) is queued under the shared lock and the memory gate and has not run yet, so cells marked with angle
> brackets are still empty: the c4 selection, the recording and 3+1, every tree through a simulated trial, the
> probes, both PATH checks, S9 and the gate. Plans: CACHE/work/plans/c4-final-a.json (phase A), the milestone
> command in private/fix2/chain-b.sh (phase B) and CACHE/work/plans/c4-final-c.json (its after-ops).

Author notes, never shipped. 2026-11-28. QA round 2 (17 passes on the fix-round-1 bundle `de0962c420fe`: 3 PASS,
8 CONCERN, 6 FAIL; harbor-lh `ops/swe-marathon-v2/qa/harfbuzz/SUMMARY-R2.md`) gave eight must-fix and twelve
should-fix items. Two three-judge panels decided the held items (R2-M7, R2-S3): the tier rule, V, the difficulty
lever and the horizon (`decisions/2026-11-28-harfbuzz-tiers-difficulty-DECISION.md`), then the failure sentence
once the rule had been applied (`decisions/2026-11-28b-harfbuzz-sentence-after-tiering-DECISION.md`, unanimous).
The coordinator added two items: Harbor's root `tar` and root's PATH (from Dogwood's pass 07 F1), and the S9 re-run.
Every report a finding cites was read before its fix. Five subagents did part of the work under the author's
review: the case fixes, the verifier hardening, the egress hooks and transfer, the residual-case audit, and the
tier evidence. Rules held throughout, with the exceptions listed under "Rules": the shared heavy-job lock and the
30% memory gate (never lowered), `--memory=4g` containers, no Oddish upload or run, no PR edits, push after every
commit, the session left at 34,560 s with no stated budget.

What did not change: the reward formula (reward = D x h_d x (1 - 0.10 (1 - h_b))), the 53 graded units, the case
counts per kind, the session length and the verifier's 2,400 s timeout.

## Items

| Item | QA finding (pass) | What changed | Evidence | Commit |
| --- | --- | --- | --- | --- |
| R2-M1 | 19 of unit 35's 60 cases graded the reverse mapping, `UPPH` back to `und-fonupa`, which no note stated (03) | The note states it ("... and `UPPH` back to `und-fonupa`"). The draw drops exact repeats before choosing (changed, duals, broad), each unit from its own random stream; unit 35 has 50 distinct reverse inputs | ⟨C4-35⟩ | 3850870a, 4b4baaf4 |
| R2-M2 | Stated clauses with no case (03, 23) | 36: "and extents" dropped (14.4.0 saturates positions; extents were never compared). 33: Proto-Cuneiform property cases with neighbours on the unassigned code points around the block; `hbapi33`, a constants probe built only where `HB_SCRIPT_JURCHEN`, `_PROTO_CUNEIFORM` and `_SEAL` are declared; USE routing cases (a font with `pres` under the new script tags) and ideographic-baseline cases, attributed through a forward build, `fwd-33` (the regenerated tables plus bf93d8671's two code hunks); the note states the routing and the baseline. 48: `hbapi48` sets `HB_FONT_FUNCS=ot` before its first call. 13: Khmer cases (a precomposed Latin letter in Khmer-shaped text, as upstream's own test has). 23: `kerx` format 6 class-kerning fonts | ⟨C4-M2⟩ | 3850870a, 4b4baaf4 |
| R2-M3 | The egress window was open: the hook killed `dev` only after Harbor's log transfer and recorded nothing, so a drop-in shaped like `solve.sh` scored 1.0 unrecorded (08, 21, 24) | The siblings' mitigation, ported (SymPy's fsmaint suite, Carve's egress watch). Set-up hooks as root start `fsmaint-netcheck`: it polls three public hosts with TLS handshakes (no request sent), watches `dev`'s sessions and processes, and keeps copies of the tree's files as they change. The collect hook `fsmaint-sweep` ends every process of `dev`, takes the end of the work from the net check, the session or the work's limit, puts back whatever changed after it (the last copy from before the end, else the shipped file, else removed), and leaves a record and an HMAC-signed listing in `/var/lib/fsmaint/out`, a second artifact. `tests/sweep_check.py` (read by `verify.py`) faults on a missing or badly signed mark, or a tree that differs from the listing. The instruction says the tree is taken as it is when the work ends | ⟨PROBES-M3⟩ | ca86363a, 2693c43b |
| R2-M4 | An absolute link or a FIFO stopped Harbor's transfer, so honest work scored 0; the round-1 cluttered tree passed only on the local path (21) | Reproduced on the real path: `simulate_trial.py` packs with GNU `tar -czf` as root and unpacks with `tarfile.extractall(filter="data")`, as Harbor's worker does; the first refused member ends the extraction. The sweep removes build folders; as `dev`, it makes in-tree absolute links relative, turns links that leave the tree into copies (256 MiB in all) and removes FIFOs, sockets and devices; as root it removes whatever is not a file, folder or link of the tree, and over-deep, over-long or unprintable names. The robust (cluttered) tree now goes through the same path. The instruction states the limits | ⟨PROBES-M4⟩ | ca86363a, 2693c43b |
| R2-M5 | `verify.py` kept each batch's result lines uncapped: out of memory, no reward (11) | A result over 4,096 characters fails its case; outside `RECORD=1` only a pass bit and a salted 8-hex digest per case are kept (`case_pass.json`, beside `metrics.json`); `metrics.json` stays under 60 KiB | ⟨C4-M5⟩ | 1f543682 |
| R2-M6 | The final sweep's wait had no bound; `builder` could stop root's sweeper (07, 11) | The sweeper's child has a spare real and saved uid, with `builder` only as its effective uid, so `builder` cannot signal it; every wait polls for at most 2 s, then root kills and reaps; alarms bound the main phase (1,980 s), the final sweep and clean-up (90 s) and publishing (30 s); survivors fail the tree. Batches take at most 15 s, keeping 2 s for each later one | ⟨C4-M6⟩ | 1f543682 |
| R2-M7 | The tiers followed no single rule (17, 16) | Panel 2026-11-28: the ordered rule (C if the behaviour shows only on tables no shipped font has and fontTools cannot write, or the note is symptom-only with the cause neither stated nor pointed to and no shipped material shows it; otherwise A if the note names the edit; otherwise B). Applied with per-unit evidence: A 23, B 22, C 8 (10a, 23, 25a, 25b, 25c, 26, 31, 42). The fontTools facts were settled in the agent image (below). Panel 2026-11-28b: the graded sentence, the same in README, DESIGN, CLAIMS and the pre-registration | `scripts/pipeline/tiers.tsv`, frozen at sha256 `0301c586...6b82c` | 2ff36f48, 50202148, 2de7d90c |
| R2-M8 | The kill conditions could not tell the sentence from its rivals; two fired by chance; condition 3 undefined; the population mismatched (17) | `notes/PREREGISTRATION.md` amended and committed before any run: the population (the first three accepted Opus-class claude-code sessions at 34,560 s), the frozen tiers with a strict-reading sensitivity, pass 16's per-unit estimates, the registered ranking tests with their simulated pass, chance and wording-rival rates, the mechanism and fix-size contrasts, per-unit conditions calibrated under 5% chance, a defined over-breadth test, and kill condition 1 with the contingent completeness lever | Predicted frontier D 0.687 (reward about 0.65); tier means A 0.824, B 0.601, C 0.529 | 2de7d90c |
| R2-S1 | 330 cases compared raw float bits; 40a's "in points" ambiguous (10, 03) | Floats print rounded (`f:%.3f`); unit 40a's size bounds sum to multiples of 5, so every reading of "in points" gives the same value | ⟨C4-S1⟩ | 4b4baaf4 |
| R2-S2 | The tripwire zeroed a version bump alone under a false label (24) | Not built only with 3 or more of the 15 upstream test sources, or a linked `meson.build`, `NEWS`, `src` or `src/hb-version.h`; a version that is not exactly 14.3.0 multiplies the reward by 0.9; the note names the cause; the instruction says to leave the version as it is; the README's drop-in row is YELLOW | ⟨C4-S2⟩ | 3850870a, 1f543682 |
| R2-S3 | Frontier about 0.65, horizon 2-3 weeks (16) | Panel: accept about 0.65 as about 0.6, with p_k² (about 0.59) pre-registered as a lever if the median of the first three accepted sessions is above 0.70; the horizon is stated (about 10-16 working days for an engineer who knows HarfBuzz, several weeks otherwise), no scope cut | README difficulty row, CLAIMS C37 | ee9d1ccf, 50202148 |
| R2-S4 | Over-broad probes keep 93-99.6%; the zoo's no-op was the weaker one; V_full misstated (09, 06) | The plan's over-broad test is staying below the unit's share of D; `noop-api-zero` writes 0 through the out-parameters; V_full 0.642 in the errata | ⟨C4-S4⟩ | f0630f4e, 4b4baaf4, 366b8ad7 |
| R2-S5 | Duals inside the wording of notes 2, 13 and 16; NBSP graded oppositely; unit 6's "a base"; unit 26; 65 repeated duals (05) | Unit 2's note keeps U+00A0 a base; unit 6's note gives the dotted circle a typed U+25CC's properties; 13 `x:exclusion` and 16 `x:oor-covered` with their duals redrawn; 29 `b:after-lvt` again under a tightened note; the README names unit 26's `b:mid-before` as a stratum a literal reading fails; repeats dropped from every draw | ⟨C4-S5⟩ | 3850870a, 4b4baaf4, eabb8dbb |
| R2-S6 | V a weak proof; two causes misdescribed; metrics cannot split throughput from wrong fixes (17) | V is described as a consistency check; the sentence no longer names Unicode data (33 is checkable) and ranks symptom-only units by what the agent can see; `case_pass.json`'s salted digest of each output lets a post-run audit tell "not landed" (14.3.0's output) from "landed wrong" (no release's); inside-stratum labels for 1, 5, 13, 23, 25a, 33, 35 and 49 | | cb46168e, a4e9da1b, 4b4baaf4, 1f543682 |
| R2-S7 | A writable `/logs/verifier` (Docker Desktop) outlasted the sweep (07) | A `builder` child tries to create a file in `/logs/verifier`; if it can, the check faults. Local runs no longer mount `/logs/verifier`: it is collected with `tar` as Harbor does | ⟨C4-S7⟩ | 1f543682, ca86363a |
| R2-S8 | README linked a pruned file; the cue regex missed half the classes; probe the rebuilt agent image (02) | The prune drops the link (a guard stops the image build if it survives); the gate sweeps every class of QA-PLAN section 4 over every agent-visible file, with a per-file allowance for the specification notes' own senses; the protection probe re-run on the rebuilt image | ⟨PROBE-AGENT⟩ | 57bcaa8b, eef35871 |
| R2-S9 | DESIGN and README stale (12) | 53 units, the cut notes out of the instruction, `--wrap-mode=nodownload`, the dated counts | | cb46168e, a4e9da1b |
| R2-S10 | OFL.txt and NOTICE.txt not gated; NOTICE.md without Microsoft's CC-BY-4.0; overstated "no 9-word run" (15) | The gate checks name ID 13 of every Noto font and OFL.txt and NOTICE.txt beside them; NOTICE.md names the MicrosoftDocs/typography licence; the errata correct the claim | ⟨GATE-15⟩ | eef35871, a1835431, 366b8ad7 |
| R2-S11 | "Stays 14.3.0" checked only against 15.x; other restrictions in part (23, 03) | The version is checked exactly; each new function must be declared in the header its note names (a missing declaration fails that unit only); the README lists the clauses no case checks | | 1f543682, eabb8dbb |
| R2-S12 | S9 pending | Upstream's suite, offline, on the rebuilt agent image | ⟨S9⟩ | |
| Root's PATH (coordinator; Dogwood pass 07 F1) | Harbor collects `/logs/verifier` and the artifacts with `tar` run as root through the image's PATH, and reads `reward.json` first | `path_check.py` asks the kernel, as `dev`, `builder`, `nobody` and a fresh uid, whether any directory root resolves commands through (the image's PATH, su's defaults, verify.py's and the sweep's, the standard ones and every parent), or any file in one, is writable. The hooks and `test.sh` set their own PATH. Canaries plant `tar`, `gzip` and the rest: the path-canary tree as the verifier's build user, `path_canary.sh` as `dev` in the agent image. Local runs collect with `tar` as root, as Harbor does | ⟨PATH⟩ | 9d236c63, ca86363a, eeb5981b |
| S9 re-run (coordinator) | The coordinator's run failed on Python 3.9 (`datetime.UTC`) | `spike.py` stops at once on Python older than 3.11, with a message | | ca86363a |

## Tiers, sentence and pre-registration

- **fontTools in the agent image** (4.69.1, `scripts/pipeline/fonttools_aat_check.py` over our fonts and the shipped
  test fonts, 104 tables): `kerx` 17 of 17 raw bytes (no module); `kern` 30 structured, every format-0 subtable
  (coverage 0, 1, 5 and 64) round-tripping through TTX unchanged, formats 1-3 raw; `morx` 45 structured (31 round
  trips byte-identical; 13 compile 2 bytes shorter and one 38 bytes shorter, still structured); `trak` 5 and `JSTF` 4 structured; `mort` 2 structured, and the third, entered
  at a non-first initial state (unit 25c's construct), does not decompile. This confirms the capability reading, so
  |C| = 8 stands (panel 2026-11-28b, item 1) and `tiers.tsv` was frozen.
- **Residual-case audit** (panel item 6, `notes/RESIDUAL-AUDIT.md`): one unit whose cases its note did not
  determine (7, fixed in the note) and five determined only through 14.3.0's behaviour (5, 17, 21, 41, 46, notes
  tightened). None names a tier-C cause, so nothing reopens.
- **The sentence:** "With no 15.x code or tests to check against, agents land most fixes whose note names the
  change, fewer where they must work the change out or diagnose a symptom the shipped fonts reproduce, and fewest
  where no shipped font shows the behaviour: a bug they must first reproduce on a font they build, or AAT `kerx`
  and `kern` tables they must assemble by hand."
- **Registered tests** (mean per-unit pass over the first three accepted Opus-class sessions, linear p_k), with the
  rate at which each passes if pass 16's estimates hold, by chance (no tier structure) and under a wording-only
  rival: A-C >= 0.15 (0.91, 0.09, 0.965); A-B >= 0.10 (0.96, 0.117, 0.951); B-C >= 0.05 (0.57, 0.32, 0.756);
  B >= 0.55 (0.80, 0.989, 0.702); B's share of the D loss at least 40% (0.99, 0.60, 0.982); all five 0.48 (fractional
  0.73), 0.014, 0.547.

⟨CYCLE⟩

## Rules

⟨RULES⟩

## Owner flags

- Difficulty: the frontier prediction is about 0.65 (D 0.687), which the panel accepted as "about 0.6" with a
  contingent lever above a 0.70 median. The owner's word is wanted on whether about 0.65 is close enough; if not,
  p_k² applies before the first run.
- Horizon: about 10-16 working days for an engineer who knows HarfBuzz, several weeks otherwise, above the 2-7 day
  target. No scope cut, since cutting tier C raises the frontier.
