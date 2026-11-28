# HarfBuzz forward-port: QA fix round 2

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
| R2-M1 | 19 of unit 35's 60 cases graded the reverse mapping, `UPPH` back to `und-fonupa`, which no note stated (03) | The note states it ("... and `UPPH` back to `und-fonupa`"). The draw drops exact repeats before choosing (changed, duals, broad), each unit from its own random stream; unit 35 has 50 distinct reverse inputs | c4: 60 changed cases, 48 forward and 12 reverse; no case id repeats in the 5,245 | 3850870a, 4b4baaf4 |
| R2-M2 | Stated clauses with no case (03, 23) | 36: "and extents" dropped (14.4.0 saturates positions; extents were never compared). 33: Proto-Cuneiform property cases with neighbours on the unassigned code points around the block; `hbapi33`, a constants probe built only where `HB_SCRIPT_JURCHEN`, `_PROTO_CUNEIFORM` and `_SEAL` are declared; USE routing cases (a font with `pres` under the new script tags) and ideographic-baseline cases, attributed through a forward build, `fwd-33` (the regenerated tables plus bf93d8671's two code hunks); the note states the routing and the baseline. 48: `hbapi48` sets `HB_FONT_FUNCS=ot` before its first call. 13: Khmer cases (a precomposed Latin letter in Khmer-shaped text, as upstream's own test has). 23: `kerx` format 6 class-kerning fonts | c4: unit 33's 60 changed cases include 3 Proto-Cuneiform property cases, 3 constants cases, 5 routing and 7 baseline cases; unit 48's 60 run under `HB_FONT_FUNCS=ot`; unit 13 has 3 Khmer cases; unit 23 has 14 format-6 and 9 mixed format-0/6 cases; the oracle scores 1.0 on all of them | 3850870a, 4b4baaf4 |
| R2-M3 | The egress window was open: the hook killed `dev` only after Harbor's log transfer and recorded nothing, so a drop-in shaped like `solve.sh` scored 1.0 unrecorded (08, 21, 24) | The siblings' mitigation, ported (SymPy's fsmaint suite, Carve's egress watch). Set-up hooks as root start `fsmaint-netcheck`: it polls three public hosts with TLS handshakes (no request sent), watches `dev`'s sessions and processes, and keeps copies of the tree's files as they change. The collect hook `fsmaint-sweep` ends every process of `dev`, takes the end of the work from the net check, the session or the work's limit, puts back whatever changed after it (the last copy from before the end, else the shipped file, else removed), and leaves a record and an HMAC-signed listing in `/var/lib/fsmaint/out`, a second artifact. `tests/sweep_check.py` (read by `verify.py`) faults on a missing or badly signed mark, or a tree that differs from the listing. The instruction says the tree is taken as it is when the work ends | Trials (below): a process left behind copies the reference's files once the network returns, 130 late entries (129 holding the reference's content) all taken out, 0.0; 97 leftover processes with no network killed, 1.0; a capped run's last edit kept and the later ones undone, 1.0; a process whose first thread has exited is found by its live thread and killed, none left (its reward check is re-run after a fix to the probe); round 1's hook leaves that process alive | ca86363a, 2693c43b |
| R2-M4 | An absolute link or a FIFO stopped Harbor's transfer, so honest work scored 0; the round-1 cluttered tree passed only on the local path (21) | Reproduced on the real path: `simulate_trial.py` packs with GNU `tar -czf` as root and unpacks with `tarfile.extractall(filter="data")`, as Harbor's worker does; the first refused member ends the extraction. The sweep removes build folders; as `dev`, it makes in-tree absolute links relative, turns links that leave the tree into copies (256 MiB in all) and removes FIFOs, sockets and devices; as root it removes whatever is not a file, folder or link of the tree, and over-deep, over-long or unprintable names. The robust (cluttered) tree now goes through the same path. The instruction states the limits | Links and a FIFO left in the reference: 1.0, 7,915 of 7,915 entries arrived (one link made relative, two copied, three removed); the same tree without the hook stops the extraction at the FIFO (7,719 of 7,862); the robust tree 1.0 with all 104,738 entries | ca86363a, 2693c43b |
| R2-M5 | `verify.py` kept each batch's result lines uncapped: out of memory, no reward (11) | A result over 4,096 characters fails its case; outside `RECORD=1` only a pass bit and a salted 8-hex digest per case are kept (`case_pass.json`, beside `metrics.json`); `metrics.json` stays under 60 KiB | long-line tree: 266 results over 4,096 characters fail their cases, the check's memory peaks at 203 MiB, the reward is written in 89 s; flood 0.067 in 72 s; every `metrics.json` under 60 KiB | 1f543682 |
| R2-M6 | The final sweep's wait had no bound; `builder` could stop root's sweeper (07, 11) | The sweeper's child has a spare real and saved uid, with `builder` only as its effective uid, so `builder` cannot signal it; every wait polls for at most 2 s, then root kills and reaps; alarms bound the main phase (1,980 s), the final sweep and clean-up (90 s) and publishing (30 s); survivors fail the tree. Batches take at most 15 s, keeping 2 s for each later one | stall tree 0.0 in 118 s; fork bomb 1.0 in 68 s, and 1.0 in 72 s under `--pids-limit=96`; memory flood 0.0 in 18 s (255 processes ended); no survivor in any run; slow and hang trees get their reward at 1,800 s | 1f543682 |
| R2-M7 | The tiers followed no single rule (17, 16) | Panel 2026-11-28: the ordered rule (C if the behaviour shows only on tables no shipped font has and fontTools cannot write, or the note is symptom-only with the cause neither stated nor pointed to and no shipped material shows it; otherwise A if the note names the edit; otherwise B). Applied with per-unit evidence: A 23, B 22, C 8 (10a, 23, 25a, 25b, 25c, 26, 31, 42). The fontTools facts were settled in the agent image (below). Panel 2026-11-28b: the graded sentence, the same in README, DESIGN, CLAIMS and the pre-registration | `scripts/pipeline/tiers.tsv`, frozen at sha256 `0301c586...6b82c` | 2ff36f48, 50202148, 2de7d90c |
| R2-M8 | The kill conditions could not tell the sentence from its rivals; two fired by chance; condition 3 undefined; the population mismatched (17) | `notes/PREREGISTRATION.md` amended and committed before any run: the population (the first three accepted Opus-class claude-code sessions at 34,560 s), the frozen tiers with a strict-reading sensitivity, pass 16's per-unit estimates, the registered ranking tests with their simulated pass, chance and wording-rival rates, the mechanism and fix-size contrasts, per-unit conditions calibrated under 5% chance, a defined over-breadth test, and kill condition 1 (its contingent completeness lever was struck by amendment 2, 2026-11-28c, before any run) | Predicted frontier D 0.687 (reward about 0.65); tier means A 0.824, B 0.601, C 0.529 | 2de7d90c, 3054a0a3 |
| R2-S1 | 330 cases compared raw float bits; 40a's "in points" ambiguous (10, 03) | Floats print rounded (`f:%.3f`); unit 40a's size bounds sum to multiples of 5, so every reading of "in points" gives the same value | c4: the recording and its 3+1 are byte-identical, the rounded outputs of 40a, 40b, 40c and 48 included; the oracle scores 1.0 through the amd64 verifier | 4b4baaf4 |
| R2-S2 | The tripwire zeroed a version bump alone under a false label (24) | Not built only with 3 or more of the 15 upstream test sources, or a linked `meson.build`, `NEWS`, `src` or `src/hb-version.h`; a version that is not exactly 14.3.0 multiplies the reward by 0.9; the note names the cause; the instruction says to leave the version as it is; the README's drop-in row is YELLOW | c4: the 15.2.0 release dropped in is not built (all 15 test sources listed), 0.0; the oracle, `solve.sh` and every stub keep 14.3.0 (no version factor) | 3850870a, 1f543682 |
| R2-S3 | Frontier about 0.65, horizon 2-3 weeks (16) | Panel: accept about 0.65 as about 0.6. The panel the owner asked to settle his open questions (2026-11-28c, with an adversarial review) kept that with no lever: the contingent p_k² clause is struck (an accepted version is frozen), a median above 0.70 is reported to the owner, and a re-version after an accept needs his word. The horizon is stated (about 10-16 working days for an engineer who knows HarfBuzz, several weeks otherwise), no scope cut | README difficulty row, CLAIMS C37, PREREGISTRATION amendment 2 | ee9d1ccf, 50202148, 3054a0a3 |
| R2-S4 | Over-broad probes keep 93-99.6%; the zoo's no-op was the weaker one; V_full misstated (09, 06) | The plan's over-broad test is staying below the unit's share of D; `noop-api-zero` writes 0 through the out-parameters; V_full 0.642 in the errata | c4 zoo: both no-op stubs 0.0 with h_d 1.0 | f0630f4e, 4b4baaf4, 366b8ad7 |
| R2-S5 | Duals inside the wording of notes 2, 13 and 16; NBSP graded oppositely; unit 6's "a base"; unit 26; 65 repeated duals (05) | Unit 2's note keeps U+00A0 a base; unit 6's note gives the dotted circle a typed U+25CC's properties; 13 `x:exclusion` and 16 `x:oor-covered` with their duals redrawn; 29 `b:after-lvt` again under a tightened note; the README names unit 26's `b:mid-before` as a stratum a literal reading fails; repeats dropped from every draw | c4: unit 2 grades 8 NBSP duals as bases, 16's duals are `b:in-range-nf` and `b:no-alias`, 29 has 8 `b:after-lvt` duals, and no case id repeats | 3850870a, 4b4baaf4, eabb8dbb |
| R2-S6 | V a weak proof; two causes misdescribed; metrics cannot split throughput from wrong fixes (17) | V is described as a consistency check; the sentence no longer names Unicode data (33 is checkable) and ranks symptom-only units by what the agent can see; `case_pass.json`'s salted digest of each output lets a post-run audit tell "not landed" (14.3.0's output) from "landed wrong" (no release's); inside-stratum labels for 1, 5, 13, 23, 25a, 33, 35 and 49 | | cb46168e, a4e9da1b, 4b4baaf4, 1f543682 |
| R2-S7 | A writable `/logs/verifier` (Docker Desktop) outlasted the sweep (07) | A `builder` child tries to create a file in `/logs/verifier`; if it can, the check faults. Local runs no longer mount `/logs/verifier`: it is collected with `tar` as Harbor does | every c4 run collected `/logs/verifier` with `tar` as root: no `reward.json` in any | 1f543682, ca86363a |
| R2-S8 | README linked a pruned file; the cue regex missed half the classes; probe the rebuilt agent image (02) | The prune drops the link (a guard stops the image build if it survives); the gate sweeps every class of QA-PLAN section 4 over every agent-visible file, with a per-file allowance for the specification notes' own senses; the protection probe re-run on the rebuilt image | The rebuilt image: no 15.x material, no network, no sudo, the hooks' files unreadable as `dev` | 57bcaa8b, eef35871 |
| R2-S9 | DESIGN and README stale (12) | 53 units, the cut notes out of the instruction, `--wrap-mode=nodownload`, the dated counts | | cb46168e, a4e9da1b |
| R2-S10 | OFL.txt and NOTICE.txt not gated; NOTICE.md without Microsoft's CC-BY-4.0; overstated "no 9-word run" (15) | The gate checks name ID 13 of every Noto font and OFL.txt and NOTICE.txt beside them; NOTICE.md names the MicrosoftDocs/typography licence; the errata correct the claim | Gate row 15: 15 fonts, no problem | eef35871, a1835431, 366b8ad7 |
| R2-S11 | "Stays 14.3.0" checked only against 15.x; other restrictions in part (23, 03) | The version is checked exactly; each new function must be declared in the header its note names (a missing declaration fails that unit only); the README lists the clauses no case checks | | 1f543682, eabb8dbb |
| R2-S12 | S9 pending | Upstream's suite, offline, on the rebuilt agent image | 244 of 244 passed, offline, as `dev` on the rebuilt agent image (64 s to build, 3 s to test). The first try, in phase A, stopped on Docker's full disk | |
| Root's PATH (coordinator; Dogwood pass 07 F1) | Harbor collects `/logs/verifier` and the artifacts with `tar` run as root through the image's PATH, and reads `reward.json` first | `path_check.py` asks the kernel, as `dev`, `builder`, `nobody` and a fresh uid, whether any directory root resolves commands through (the image's PATH, su's defaults, verify.py's and the sweep's, the standard ones and every parent), or any file in one, is writable. The hooks and `test.sh` set their own PATH. Canaries plant `tar`, `gzip` and the rest: the path-canary tree as the verifier's build user, `path_canary.sh` as `dev` in the agent image. Local runs collect with `tar` as root, as Harbor does | Both images: 14 directories each, none writable by any of the four; the path-canary tree 0.0, with no marker or `reward.json` in what was collected; the planter as `dev` in the agent image planted nothing | 9d236c63, ca86363a, eeb5981b |
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

## The re-recording cycle (c4)

- **Phase A** (one hold of the shared lock, 33 min, 06:42-07:15 UTC; `CACHE/work/plans/c4-final-a.json`): the
  pipeline image, the c4 sweep (68 builds of releases, reverts, partials, mutants and the forward build `fwd-33`,
  each removed once its cases had run), classification, the selection check, every tree, the agent image with the
  hooks, S9, the PATH check, the canary and the protection probe in that image.
- **Phase B, first try** (07:39-07:42 UTC): the recording failed in 6.9 s with "the reference tree did not build".
  Docker's VM disk had 0 bytes free for unprivileged writes, and the verifier copies and builds the tree as its own
  user. Phase A's S9 had stopped the same way ("No space left on device"). Fixes: 86 stale build-cache records of
  this task's own builds pruned by exact ID, leaves first (4.1 GB back); the milestone checks for 3 GB free before
  a recording and before trials; a failed recording now says why.
- **Phase B** (one hold, 77 min, 08:17-09:35 UTC; `private/fix2/chain-b2.sh`, then `c4-final-c.json`): the
  recording and 3+1 through the amd64 verifier image, every tree through a simulated trial (the hooks, the turn as
  `dev`, Harbor's `tar` transfer as root, the worker's `tarfile` "data" filter, then the verifier with no network),
  S9 and the canary again, the verifier image's PATH check, the probes and the fork bomb under a pids limit.
- **Re-runs** (one hold, queued at the time of writing): V and W as `mutant-v` and `mutant-w` (phase B refused the names `V` and
  `W`: trial names are lowercase), and the zombie-thread probe with its egress test fixed (its first run took a
  socket refused at once for egress, so its thread broke the tree two seconds before the session ended; the sweep
  rightly kept the tree as it was at the end).

**Selection:** 5,245 cases: 3,145 changed over 53 units (36-60 each), 1,500 duals over 50 units, 600 broad, no case id
repeated. **Recording:** through the amd64 verifier image under the glibc pin; record-2, record-3 and record-1cpu
byte-identical to it.

| Tree, through a simulated trial | Reward | D | h_d | h_b | Seconds (trial) |
| --- | --- | --- | --- | --- | --- |
| oracle (shipped tree + reference change) | 1.0 | 1.0 | 1.0 | 1.0 | 97 |
| solved (`solution/solve.sh` as the turn) | 1.0 | 1.0 | 1.0 | 1.0 | 97 |
| nop (the image's tree) | 0.0 | 0.0 | 1.0 | 1.0 | 80 |
| V (`mutant-v`) | queued |  |  |  |  |
| W (`mutant-w`) | queued |  |  |  |  |
| stub-comments, -refactor, -noop-api, -noop-api-zero | 0.0 | 0.0 | 1.0 | 1.0 | 78-80 |
| stub-nobuild | 0.0 | 0.0 | 0.0 | 0.0 | 30 |
| stub-empty | 0.0 | 0.0 | 0.273 | 0.0 | 78 |
| stub-abort | 0.0 | 0.0 | 0.261 | 0.0 | 77 |
| robust (a pipe, a 600 MB sparse file, 100,000 files, links out) | 1.0 | 1.0 | 1.0 | 1.0 | 148 |
| hostile | 0.0 | 0.0 | 1.0 | 1.0 | 94 |
| dropin (the 15.2.0 release) | 0.0, not built | 0.0 | 0.0 | 0.0 | 17 |
| flood | 0.066566 | 0.283 | 0.261 | 0.0 | 90 |
| long-line | 0.000009 | 0.003 | 0.003 | 0.0 | 107 |
| fork-bomb; under `--pids-limit=96` | 1.0; 1.0 | 1.0 | 1.0 | 1.0 | 86; 89 |
| mem-flood | 0.0 | 0.0 | 0.0 | 0.0 | 37 |
| path-canary | 0.0 | 0.0 | 1.0 | 1.0 | 77 |
| stall | 0.0 | 0.0 | 0.95 | 1.0 | 135 |
| slow | 0.0 at 1,800 s | 0.0 | 0.0 | 0.0 | 1,818 |
| hang | 0.069968 at 1,801 s | 0.297 | 0.261 | 0.0 | 1,819 |
| fault (an unknown release) | none (`check fault: unknown RELEASE`) | | | | 22 |

Every run's transfer arrived whole, the sweep's reader found no fault, and no collected `/logs/verifier` held a
`reward.json` or the canary's marker. The fault row is the intended probe: a verifier fault leaves no reward (the
version factor is a different check; no tree here changes the version except the drop-in, which is not built).

The robust tree's sweep notes that the net check's watch "had not looked at it close to the end, or lost track of
some entries". Its 100,000 new files pass the watch's 50,000 tracked entries (53,739 untracked), so the sweep falls
back to removing any late entry it has no copy of. Nothing changed after the end, so nothing was removed and the
tree scored 1.0; an honest tree is not affected.

| Probe (`run_probes.py`) | Result |
| --- | --- |
| oracle through the whole path | held: nothing late, 7,856 of 7,856 entries, 1.0 |
| a-late-dropin | held: 130 late entries listed (129 holding the reference's content), every one taken out, 0.0 |
| b-links-fifo | held: 1 link rewritten, 2 copied, 3 removed with the FIFO; 7,915 of 7,915 arrived; 1.0 |
| b-links-fifo-raw (no hook) | held: the extraction stops at the FIFO (`SpecialFileError`), 7,719 of 7,862 arrive |
| c-zombie-thread | the process was found by its live thread and killed, none left after the hook; the reward check did not hold on the first run because the probe's egress test fired before the session ended (fixed in 2387dc68; re-run queued) |
| c-zombie-thread-legacy (round 1's hook) | held: the thread outlives the hook |
| e-capped-last-edit | held: the end taken from the limit, the last edit before it kept, the later one and a new file undone, 1.0 |
| d-hook-processes (no network) | held: 97 processes listed and killed, none left, 1.0 |

**S9:** upstream's suite, offline, as `dev` on the rebuilt agent image: 244 of 244 passed. **Protection probe:** no
15.x material, no network, no sudo, the hooks' files unreadable as `dev`. **Root's PATH:** nothing writable in either
image (14 directories each, as `dev`, `builder`, `nobody` and a fresh uid); the canary planted nothing in either.

**V and W** (pipeline, c4): V as built 0.8752 (D 0.8752, h_d 1.000, h_b 1.000): 25b's commit does not revert on
15.2.0 and 25a keeps 0.383. Complete, with every tier-C unit at 0, V is 0.8491, inside the band (0.60-0.85, not
moved), with D lost only on tier C (panel 2026-11-28, item 3). W 0.6948 (D 0.9824, h_d 0.7093, h_b 0.9700); W_literal
0.7659; R_unbuilt 0.8186; R_all 0.177. Through the verifier: queued (`CACHE/work/plans/c4-final-d.json`).

## Gate (QA-PLAN.md section 1), `scripts/gate_checks.py`, `CACHE/work/gate-c4.json`

| # | Gate | Result |
| --- | --- | --- |
| 1 | Inventory | **Pass.** 48 notes, 53 graded units, 4 cut with reasons |
| 2 | Kill matrix | **Pass.** 53 units, at least 36 cases each, no cross-kill |
| 3 | Stub zoo | **Pass.** nop and all seven stubs exactly 0.0, with no problem row |
| 4 | Oracle and nop | **Pass.** oracle 1.0, `solve.sh` 1.0, nop 0.0, all through simulated trials |
| 5 | Determinism | **Pass.** 3+1 recordings identical (5,245 cases) |
| 6 | Cue words | **Pass.** 0 hits over the instruction and every agent-visible file |
| 8-10 | Robustness, isolation, no early stops | **Pass.** Every tree as expected (table above); nothing stops the session before 34,560 s, and the net check ends `dev`'s processes when the network comes back only once no session of `dev` is alive or the work's limit has passed |
| 12 | Band | **Pass (pipeline).** V complete 0.849 in band, D lost only on tier C, h_d and h_b 1.000; W 0.695 and W_literal 0.766 as bounds. The verifier trials of V and W are queued |
| 15 | Font licences | **Pass.** 15 fonts |
| 16 | Root's PATH | **Pass.** both images and both canaries |
| 17 | Probes | 7 of 8 held; c-zombie-thread is re-run after the probe fix |

## Bundle and preflight

- Bundle `d06cb52b2648774f683d6b539fb1b1869136ffca8431ed8e0343b5c80ef945ab`: 668 files, 24.6 MB
  (`scripts/package_task.py`; the notes file matches the instruction; both copies of the hook's key agree; no patch
  files).
- Local `oddish preflight` (no upload): **passed**.
- The private store has `fix2/`: the residual audit and its evidence, the in-image fontTools check, the
  pre-registration's simulation and calibration, the cycle's plans, and `fix2/c4/` (the c4 selection, cases and
  recorded outputs, the gate and band data, every trial's result, metrics, per-case verdicts and sweep record, the
  probes, the PATH checks, S9 and the protection probe), backed up as a bundle in harbor-lh
  `ops/swe-marathon-v2/next-tasks/harfbuzz-forward-port-private/`.

## Left open

- The verifier trials of V and W and the zombie-thread probe's re-run are queued (`c4-final-d.json`), behind the
  memory gate and the game campaign's hold.
- V keeps 25b whole and 25a in part (three commits do not revert on 15.2.0); the band applies to the complete value.
- Docker's VM disk sits at 98-99%, mostly other projects' images; the milestone now stops before a recording or a
  trial with less than 3 GB free for unprivileged writes.
- The net check's watch tracks at most 50,000 changed entries; past that the sweep removes any late entry it has no
  copy of (the robust tree shows the note; honest trees are not affected).
- No Oddish upload or run; QA round 3 comes next.

## Rules

- The cases and audit subagents ran fontTools 4.60.2 from the user's site-packages on the macOS host, on our own
  synthetic fonts. That breaks the rule against running downloaded code on the host; it was not repeated, and the
  in-image check is the one the tiers rest on.
- The cases subagent ran `rm -rf` on a shell variable, inside its scratch folder.
- I pulled `alpine:3.20` (12 MB) for a disk check and removed it by tag at once.
- Build cache: 86 stale records of this task's own builds pruned by exact ID (leaves first, the current images'
  layers kept), to free Docker's disk. Nothing of other projects was touched.
- The lock was always taken through `spike.heavy` (30% gate, never lowered); no hold was taken over. Containers ran
  at `--memory=4g`, at most two background trials at once. No Oddish upload or run, no PR edits.

## Owner flags

- Difficulty: settled by the panel the owner asked for (2026-11-28c): the frontier prediction of about 0.65
  (D 0.687) is accepted with no lever; a first-run median above 0.70 is reported to him, and a re-version after an
  accept needs his word.
- Horizon: about 10-16 working days for an engineer who knows HarfBuzz, several weeks otherwise, above the 2-7 day
  target. No scope cut, since cutting tier C raises the frontier.
