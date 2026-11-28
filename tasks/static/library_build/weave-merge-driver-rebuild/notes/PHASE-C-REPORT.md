# Phase C report: Weave made QA-ready

Task `abundant/swe-m2_software-engineering_weave-merge-driver-rebuild`, branch
`neel/weave-merge-driver-rebuild`. Phase C covered:

- a wider generator;
- the brief in the requester's voice and the cue-word sweep;
- the coverage inventory and kill matrix;
- the stub zoo, the leak scan, and determinism on the final case set;
- calibration;
- the verifier's hardening;
- the flat bundle and the local preflight.

The session stays at 34,560 s, with no budget stated anywhere. No upload or Oddish run was made.

## 1. Result

Weave is QA-ready, apart from the closing image checks, which wait for the shared lock (section 6).

- **Determinism:** 3+1 runs on 8,990 candidates, 0 unstable.
- **Kept cases:** 6,329, each tied to at least one stated rule.
- **Stubs:** all 15 trivial programs, and the no-op, copy-ours and wrapper crates through the
  verifier, score 0.
- **M-gate:** 0.7500, with only F8 moving.
- **Mutants:** 22 of 23 features have a mutant that moves at least 3 kept cases. FT-SUPERSET waits
  for its relaxed mutant: switching the route off changes no output.
- **Verifier and images:** hardened against everything on the must-fix lists (sections 4 and 4a).
- **Preflight:** passes on bundle `2751bdd4b638`.

**Ready for the 20-pass QA once the closing job lands.**

## 2. The 12-item pre-upload gate (`notes/QA-PLAN.md` section 1)

| # | Gate | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Inventory | pass | `notes/COVERAGE.md`: all 23 instruction-level features, all 167 rule ids (read from the specification's own markers, so nothing is unlisted), and 10 stated restrictions. Each of the 50 rules no recipe or mutant targets is classified: 22 pass through every case, 9 through every conflict or check, 8 through every rename or data case, 2 are fast paths a trivial program reproduces, and 9 are not behaviour. |
| 2 | Kill matrix | 22 of 23 pass; FT-SUPERSET **pending** (closing job, section 6) | 30 feature-removal mutants (44 patches); 29 built and run on 8,990 candidates, `superset_relaxed` pending. Kept cases moved per feature: `notes/COVERAGE.md`. |
| 3 | Stub zoo | pass | All 15 programs score 0.0000 net: take ours/theirs/base, git plain and labelled, git with the hint, diffy with the CLI checks, one whole-file box, always 2, routing only, git always clean, git without the hint, no-op, empty and clean, ours as a conflict, ours with the hint. Through the verifier, the no-op crate, copy-ours and a wrapper around the installed build each score 0.0 (Phase C job 2). |
| 4 | Oracle and nop | pass | The oracle matches the reference on 8,990 of 8,990 candidates. In the verifier: the upstream solution 1.0 twice (88 s and 93 s for 6,329 cases), the empty delivery 0.0 twice. The re-run on the final verifier is **pending** (closing job, section 6). |
| 5 | Determinism | pass | Three runs plus one perturbed run on 8,990 candidates: 0 unstable, 0 invalid statuses. The agent and verifier images both report git 2.43.0. The amd64 sample (Phase B) was 200 of 200. Neither weave nor sem-core uses a libm or fused multiply-add function, so no output depends on CPU features. |
| 6 | Cue-word sweep | pass | `scripts/checks/cue_words.py`: 0 hits on `instruction.md` and the 17 files in `/app/docs`. The installed build's `--help` and the collect hook: 0 hits. The re-sweep of the shipped image's file names as `dev` is **pending** (closing job, section 6); the one hit in job 2 came from my own copy of the upstream source. |
| 7 | Protection probe | pass | Phase B: read, copy, `/proc/pid/mem`, `/proc/pid/exe`, gdb attach and core dump all refused; `LD_PRELOAD` ignored. Phase C, real agent image as `dev`: the same result. PATH writability as `dev` is **pending** (closing job, section 6). |
| 8 | Verifier robustness | pass, with the re-run **pending** (closing job, section 6) | See note 8 below the table. |
| 9 | Isolation | **pending** (closing job, section 6) | See note 9 below the table. |
| 10 | No early stops | pass | No task-side timer, kill or deadline exists before `timeout_sec`. The only time limits are the verifier's own: 10 s per case, the build limit, and the image-build limits. |
| 11 | Leak scan | pass | `scripts/checks/leak_scan.py`: no private line, run of lines or seed in the instruction, the docs, the README, the notes or `task.toml` (33 files, 6,329 cases). Agent image (job 2): no private or recorded file and no weave source readable. |
| 12 | Band check | pass | M-gate scores **0.7500** (1 - w(F8)) and moves only F8. The other mutants mostly move their own family; some features run through several families by nature, and each signature is in the kill matrix. |

**Note 8 (Verifier robustness).** Image builds took 113 s (agent) and 15 s (verifier). The oracle's verification took 88-93 s
for 6,329 cases, against the 3,600 s limit. With the private inputs missing, the verifier exits 2
and leaves no file.

The first forger run (job 2) found a real hole: zombies counted as survivors, and the error path
left the forger's `reward.json`, `reward.txt` and a link under `metrics.json` behind. Fixed:
- live processes are judged per thread;
- every error path clears the reward names;
- any entry under them is removed;
- `/logs/verifier` is made root's 0755.

The forger re-run is **pending** (closing job, section 6).

**Note 9 (Isolation).** The hostile submission (the upstream solution patched to hang on 2 cases, leave 64 children
on 34, print 64 MB on 38 and plant a file on 32) should score 0.999099, losing only the 2 hanging
cases. Its first run hit the zombie fault above. Also pending:
- the non-UTF-8 and 1,000-level canary;
- a delivery carrying a 1,000-level junk chain, which should score 1.0, with the chain left out
  past 64 levels.

## 3. Numbers

| Item | Value |
| --- | --- |
| Candidates | 8,990 (3,910 from the Phase B recipes plus 51 new recipes; fresh private seed) |
| Kept | **6,329**. By family: F1 1,156, F2 491, F3 1,120, F4 643, F5 767, F6 195, F7 280, F8 1,109 (600 refusals and 509 accept-duals), F9 448, F10 120 |
| Filtered (reproduced by a trivial program) | `git_labelled_hint` 2,185, `diffy` 943, `git_plain` 774, `take_theirs` 321, `take_ours` 296 (these overlap) |
| Kept despite a trivial match, netted | 220 cases: the status-2 restriction cases, the line route for both-created files and for many equal names, and two boxes far apart (the hint on the first closing marker only) |
| Stub rates used for netting | F1 0.216, F3 0.143, F4 0.187, F8 0.541, F9 0.018; the other families 0 |
| Specification | 16 chapters, 15,006 words (30.0 pages), plus `NOTICE.md` |
| Bundle | `2751bdd4b638` (247 files), packaged twice to the same hash; `oddish preflight` passes |

## 4. The must-avoid list (HarfBuzz's QA findings), checked in Weave

| Class | Weave |
| --- | --- |
| Comparison framing in the instruction | The brief says what depends on each behaviour: the merge queue re-runs reviewed merges, landing agents act on exit 0, and editors read the markers. Nothing in it says the work is right when outputs match another program. The sweep also checks brief-only words (compare, match, same as, pass the). |
| Graded but undocumented, documented but never graded | Every graded case's behaviour is stated in the specification, which three independent reviews checked against the tag. The oracle (the tag's own source) matches the original on every candidate. Every instruction-level feature has a mutant that moves at least 3 kept cases (22 of 23; FT-SUPERSET pending, `notes/COVERAGE.md`); every kept case is tied through its recipe to a rule the specification states. Every stated restriction has a case or an enforcing check. The CLI documents one form, and no case uses another flag (no `-h`, no `--version`). |
| Stubs above 0 | 15 trivial programs net exactly 0, and so do the no-op crate, copy-ours and the wrapper through the verifier (0.0 each). Cases a trivial program reproduces are dropped, or kept only where they grade a stated rule, and then netted. |
| Reward forging | Everything the submission runs is bounded and runs as uid 51000 with `no_new_privs`. Every process of that uid is killed before results are read. Outputs are opened with `O_NOFOLLOW` from root-owned case directories. Anything under the reward names is removed, then `metrics.json` and `reward.txt` are created last with `O_EXCL`. The forger (build.rs and runtime writes, links and a daemon): the first run found the error-path hole, now fixed; the re-run is **pending** (closing job, section 6) |
| Emulated versus real amd64 | No libm or fused multiply-add use anywhere on the merge path. Similarity scores use plain IEEE division and multiplication, and Rust never contracts these. |
| Spec licensing | A verbatim scan against the tag finds only keyword lists and the hint line (22 words at most). `NOTICE.md` in the docs names the MIT OR Apache-2.0 licences, whose texts ship alongside. |

## 4a. Dogwood's must-fix list, checked in Weave

| Dogwood finding | Weave |
| --- | --- |
| D-M1 PATH forging | Both images set an explicit `ENV PATH` and run `chmod -R go-w` over it. The build fails if anything on PATH is not root's or is writable by others. `verify.py` checks again at run time. The plant-tar canary (planting `tar`, `gzip` and `su` from `build.rs` and at run time, followed by root's own `tar`, `gzip` and `su`) is **pending** (closing job, section 6) |
| D-M2 zombie leader | Liveness is read per thread from `/proc/<pid>/task`, every pid of the uid is killed whatever its state, and `/logs/verifier` is root's 0755 and never reopened |
| D-M3 transfer truncation | The root collect hook (`[[verifier.collect]]`) removes FIFOs, devices, absolute, outward and loop links, anything past 64 levels and paths over 3 KB, and writes `.delivery/manifest.json`. A file missing against the manifest is a lost run, not 0. The brief promises nothing about such entries. Local proof through the pinned Harbor's `tar_transfer.py` (14 tests): without the hook the tree arrives cut, with it whole. The image run is **pending** (closing job, section 6) |
| D-M4 egress window | The hook runs as root: it kills every non-root process until none runs, and records egress, processes and ctimes. Files changed after start + 34,560 s are refused, and so are 234 digests of the original's published sources and builds. Still a stopgap: the platform fix is Harbor's |
| D-M5 hostile errors | `/proc` is parsed as bytes. Trees are walked and removed iteratively, and the delivery copy has a 64-level cap. The canary is **pending** (closing job, section 6) |
| D-M6 graded but unstated | Every kept case's recipe names the spec rules it tests; `coverage.py` reports 0 untied cases. The 31 older recipes were tagged, and generation is byte-identical |
| D-M7 stated but ungraded | All 23 instruction-level features have mutants, with 22 at 3 or more kills. Every one of the 49 rules no recipe or mutant targets is classified (`notes/COVERAGE.md`) |
| D-M8 out-of-scope case | None: one invocation form, five file types, inputs of 9.4 KB at most |
| D-M9 cheap partial credit | 15 programs in the zoo, all at 0 net; F8 and F3 are paired. A QA lens should still probe for cheaper programs |

## 5. Commits

Branch `neel/weave-merge-driver-rebuild`, all pushed:

| Commit | What |
| --- | --- |
| `1f546187` | brief rewritten, first verifier hardening, licence notice, cue and verbatim checks |
| `635acecd` | 29 feature mutants, wider stub zoo, test submissions, leak scan |
| `0242841d` | 51 recipes, four spec clarifications |
| `9dc271cd` | preflight clean (archive source, `.dockerignore`), packaging, coverage tooling |
| `a22da929` | verifier survives zombies and forged files |
| `68fcb4ab` | root PATH gate, collect hook, transfer manifest, tripwire, case-to-rule ties |
| (this commit) | this report, `notes/COVERAGE.md`, README |

harbor-lh `neel/swe-m2-ops` was pushed via `push_ops.sh` as `faf4fd2a` and later: the private
bundle (6,329 cases) and the Phase C tools.

## 6. Open items and next steps

**Pending: the closing job.** `jc-final.sh` (in the private Phase C tools) is queued with
1-minute retries for up to 12 hours, under the 30% memory gate and the shared lock. Two earlier
waits gave up after 3 and 10 hours: 258 of 300 attempts were memory-gated, and 42 found the lock
held. The job:

1. Builds both images from the worktree.
2. Sweeps the shipped agent image as `dev`: cue words in file names, PATH writability, private
   files, weave sources, the probe, the full `--help`.
3. Runs the collect hook on a cluttered delivery (FIFO, socket, absolute and outward links, a
   1,000-level chain, a non-UTF-8 name, a left-behind process).
4. Carries the tree through a tar transfer extracted with `filter="data"`, and grades it
   (expected 1.0, manifest intact).
5. Runs the verifier on:
   - the upstream solution (1.0);
   - a 1,000-level junk delivery (1.0);
   - the no-op crate (0);
   - the forger (0, with only root's reward files);
   - the hostile submission (0.999099);
   - plant-tar (0, no planted tool run by root);
   - the non-UTF-8 and deep canary (0, no crash);
   - the fault case (no files).
6. Builds and runs the relaxed-superset mutant (FT-SUPERSET kills).

When it lands, this report's pending cells are updated and pushed. Then:
- the 20+ independent QA passes (`notes/QA-PLAN.md` section 5);
- Oddish oracle and nop baselines, and pre-trial QA, before any agent trial.

**Open for the owner:**
- the stated 12-hour budget (one parameter, `[agent] timeout_sec`, still 34,560 with no budget
  stated);
- the platform fixes for the egress window and the transfer.
