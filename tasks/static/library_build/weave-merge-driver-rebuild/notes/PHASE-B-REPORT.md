# Phase B report: Weave merge-driver rebuild

Task `abundant/swe-m2_software-engineering_weave-merge-driver-rebuild`, branch
`neel/weave-merge-driver-rebuild`, on probation. Phase B covered the downloads, the four
probation checks in local Docker Desktop and the first build milestone. Everything ran
arm64-native; amd64 was emulated for the sample only. Dates are 2026-11-26 to 2026-11-27 (UTC).

## 1. Verdict

**GO.** All four probation checks pass, and so do the two Phase A gates measured in the spike
(section 4):

1. The 3+1 runs are byte-identical.
2. 2,388 discriminating cases are kept, and every stub scores 0.
3. M-gate scores exactly 0.75, and only the gate family moves.
4. The specification is complete, reviewed against the tag, and within the page budget.

The first build milestone: reached. The task images build the original from the pinned tag; the verifier gives the upstream solution 1.0 and an empty submission 0.

## 2. Changes from the owner during Phase B

- **Chains parked (2026-11-26).** The owner wrote: "we dont have to promote multi-turn as well so
  make stuff likewise". The task stays single-step (plan A).
  - The 0.5.4 and 0.6.2 chain measurements and the chain canary were dropped.
  - `notes/STEPS.md` and `notes/steps/` stay as history, marked "parked by the owner,
    2026-11-26".
  - The 0.5.4 and 0.6.2 source archives had been downloaded before the change. They were not used.
- **Difficulty (2026-11-26).** The owner wrote: "if its hard enough in single turn make sure to
  have it difficult enough". The targets are a frontier score at or below about 0.6 and a
  mid-tier score of 0.1-0.4, using fair levers only.
  - The gate family now weighs 25%.
  - Rename (F3) and placement (F2) are full families, and their thresholds are stated in the
    specification.
  - There are more near-miss pairs, where refusing or not turns on one stated condition.
  - Every rule a case tests is stated in the specification.
  - Expected scores (`notes/DESIGN.md` section 8): about 0.55 frontier, about 0.29 mid-tier.
  - **M-gate recheck after the reweighting:** 0.7500, exactly 1 - w(F8). The design band holds.
- **Session length (coordinator, 2026-11-27).** Accepted tasks now state a 12-hour budget in the
  brief (`timeout_sec` 43,200), with no network. Here the session length is a single parameter,
  `[agent] timeout_sec` in `task.toml` (now 34,560). The instruction states no budget. Adopting
  that pattern later means changing that one value and adding one sentence to the brief. Agent
  and verifier both run `no-network` already.

## 3. The four probation checks

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Byte-identical 3+1 with pinned git | **pass** | 3,910 candidates, each run by the reference 3 times plus 1 perturbed run (long path prefix, other file names, one CPU, sequential). 0 unstable, 0 invalid statuses. git is `1:2.43.0-1ubuntu7.4` in every image. |
| 2 | At least 1,000 discriminating cases, every stub at 0 | **pass** | 2,388 kept of 3,910. The 6 filter programs dropped the rest. All 11 stubs net 0.0000 (table below). |
| 3 | M-gate in band with a single-family signature | **pass** | M-gate 0.7500; only F8 moves (pass 0.46, net 0). The other mutants move their own families, below. |
| 4 | Spec of at most about 30 pages, accurate to `527ccb3` | **pass** | 16 chapters, 14,964 words (29.9 pages at 500 words a page). Independent agents reviewed every chapter against the tag: chapters 1, 2, 12 and 14 twice, the others once. All 49 findings (inaccurate or unclear rules: 7, 13, 12 and 17 by round) were fixed after re-checking the code. Two editing passes cut 1,456 words; a separate checker found no change of meaning (records: harbor-lh `ops/swe-marathon-v2/qa/weave/01-05`). |

**Kept cases.** By family, then by language:

| F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 | F9 | F10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 113 | 251 | 240 | 120 | 80 | 194 | 120 | 1,110 | 40 | 120 |

| Python | TypeScript | Go | JSON | TOML |
| --- | --- | --- | --- | --- |
| 634 | 726 | 748 | 160 | 120 |

The gate family holds 600 refusals and 510 paired accept-duals; the target was at least 150 of
each.

**Filter programs.** These are the candidates each program reproduced exactly; they were dropped.

| `git_labelled_hint` | `diffy` | `git_plain` | `take_theirs` | `take_ours` |
| --- | --- | --- | --- | --- |
| 1,153 | 746 | 577 | 120 | 80 |

The sets overlap. Among the routing sub-family, only the marker cases survive. The binary,
NUL-after-8,192 and non-UTF-8 cases are reproduced by the diffy program, which runs the same
command-line checks.

**Netting programs.** After netting, all five score 0.0000.

| Program | Raw pass rate before netting |
| --- | --- |
| `always_box` | 0.50 on F3, 0.54 on F8 |
| `always_error` | 0 |
| `routing_only` | 0 |
| `git_labelled_clean` | 0 |
| `git_no_hint` | 0 |

`always_box`'s raw rates are what the paired design expects.

- **F8 (0.54):** it passes all 600 refusals and none of the 510 duals.
- **F3 (0.50):** it passes all 120 edited-body renames and none of the 120 below-threshold ones.
  An edited-body rename that the other side also edits ends in one rename-against-edit box, and
  with nothing else changed that box equals a whole-file box.

With netting, these families score only when both halves of a pair are right.

**Mutants.**

| Mutant | Reward | Families it moves (pass rate) |
| --- | --- | --- |
| M-gate (gate off at its four call sites) | 0.7500 | F8 0.46 (net 0) only |
| M-elem (element union off) | 0.7491 | its own F6 0.41; F4 0.00 (same-definition edits use the union); the F8 duals that need the union, 0.90; F9 0.00 |
| M-place (gap order by version position instead of key) | 0.8657 | its own F2 0.39; F4 0.76 (cases that combine same-definition edits with placement); F1 layout cases 0.80 |

## 4. Phase A gates measured in the spike

- **Oracle under the agent's toolset.** This is the upstream tag source, patched to build only
  from the agent's crates with the three language features. It is identical to the reference on
  **3,910 of 3,910** candidates (100.00%; the gate was 99.5%) and scores 1.0000 on the kept set.
  The build took 60 s, with a container peak of 2.12 GB.
- **The agent's registry.** `cargo vendor` of the registry seed lists **64 crates** (106 MB
  unpacked), exactly the oracle's own vendored set. Phase A estimated 82 crates (14.5 MB of
  `.crate` files) from the full lock closure. The oracle patch drops `env_logger`, `weave-crdt`
  and the dev-dependencies, and that accounts for the difference.
- **amd64 sample.** The official x86_64 release binary (checksum verified) was run under
  emulation on 200 sampled candidates. **200 of 200** are byte-identical to the arm64 reference.
- **Protection probe** (as user `dev`, binary `root:weaveorig` mode 2711):
  - reading or copying the binary, `/proc/pid/mem`, `/proc/pid/exe` and gdb attach are all
    refused;
  - `LD_PRELOAD` is ignored;
  - strace runs the program but cannot read its memory.
  - The core-dump check: refused. It was re-run alone in the agent image (job 8, 9 s, every wait bounded). The settings were `suid_dumpable` 0, `core_pattern` `core` and an unlimited core limit. SIGABRT kills the driver (status 134) and no core is written, and `/proc/pid/environ` is owned by root, so the process is non-dumpable. The SIGQUIT half shows nothing: a background job of a non-interactive shell starts with SIGQUIT ignored, so the driver simply finished. SIGABRT settles the question.

## 5. First build milestone

| Item | Result |
| --- | --- |
| Agent image builds the original from pinned source | yes. `git clone --depth 1 --branch v0.7.1`, the commit checked equal to `527ccb37a951…`, built with Rust 1.100.0, stripped and installed `root:weaveorig` mode 2711; the source and cargo cache are removed |
| As user `dev` in the agent image | `weave-driver --version` prints `weave-driver 0.7.1`; the binary is not readable; the upstream solution (`solution/` with `scripts/stage_upstream.sh`) builds offline from `/opt/cargo-vendor` (8.9 MB binary) |
| Verifier skeleton (separate image, `no-network`) | builds the submission offline as a dropped uid, runs 2,388 cases one process each (10 s, 4 GB address space), compares status and output digest, nets per family, writes `metrics.json` then `reward.txt` |
| Upstream solution | **reward 1.0** (2,388 of 2,388, every family net 1.0) |
| Empty submission | **reward 0.0** (`no Cargo.toml in /app/driver`; a failed build is 0, never an evaluation error) |
| Generator | the first families, exported to the git-ignored `tests/private/` (cases, recorded status and digest, per-family stub rates); backed up as a bundle in harbor-lh `next-tasks/weave-merge-driver-rebuild-private/` |
| Public parts | committed and pushed (`4336322b`): environment, tests (without `private/`), solution, staging script |

## 6. Resource use

| Job | Wall time | Peak memory | Notes |
| --- | --- | --- | --- |
| Reference build (v0.7.1, all features) | 104 s | 3.27 GB (container cgroup peak, 4 GB cap) | stripped binary 71 MB |
| Oracle build (64 crates, 3 languages) | 60 s | 2.12 GB | |
| Case runs: reference x4 + 11 stubs | 182 s | under 4 GB cap | 3,910 cases each |
| Mutant builds + runs | 106 s | under 4 GB cap | builds reuse the reference's dependency artefacts |
| amd64 sample | 97 s | under 4 GB cap | emulated |
| Milestone images and checks | 394 s | under 4 GB cap | |

**Disk.** The largest items were:

- the builder image, 1.37 GB (removed);
- the shared build volume, 0.8 GB (removed after the oracle);
- the cache folder, 630 MB.

The cache folder holds:

- downloads, 122 MB;
- the cargo cache, 114 MB (unpacked crate sources deleted);
- spike binaries, case files and run records.

The milestone images: agent image 1.65 GB and verifier image 1.51 GB, sharing 1.03 GB (2.13 GB together), removed after the milestone and the probe.

Every container ran with `--memory=4g --cpus=6` or less. Every heavy job took the shared lock
after the memory check. No lock was taken over.

## 7. Downloads

All of these are under `~/Documents/github/Abundant/lib-tasks-cache/weave-merge-driver-rebuild/`
and are recorded in `MANIFEST.tsv` (file, bytes, sha256, source).

| File | Bytes | sha256 (first 16) | Check |
| --- | --- | --- | --- |
| `weave-v0.7.1.tar.gz` | 1,843,856 | `2c3c913b1b2ae8c2` | tag commit `527ccb37a951` |
| `weave-driver-x86_64-unknown-linux-gnu-v0.7.1.tar.gz` | 8,434,507 | `cab92e62f6732128` | equals upstream `checksums.txt` |
| `checksums-v0.7.1.txt` | 1,917 | `a3854aa6e6cd66c3` | release asset |
| `rustc-1.100.0-aarch64-unknown-linux-gnu.tar.xz` | 69,831,548 | `fcbfa5b8a0cb28f0` | equals the channel manifest |
| `cargo-1.100.0-aarch64-unknown-linux-gnu.tar.xz` | 10,568,184 | `d07ee80eb6ba3c58` | channel manifest |
| `rust-std-1.100.0-aarch64-unknown-linux-gnu.tar.xz` | 31,553,000 | `c73f62fbe5d837f9` | channel manifest |
| `channel-rust-1.100.0.toml` (+ `.sha256`) | 893,976 | `3051e859570f64a8` | equals its `.sha256` |
| `channel-rust-stable.toml` | 893,976 | `3051e859570f64a8` | the same file as 1.100.0 |
| `sem-core-0.29.0.crate` | 1,009,275 | `ffb3d52f7d2d3852` | equals the v0.7.1 `Cargo.lock` checksum; read-only source for the specification |
| `weave-v0.6.2.tar.gz` | 1,839,391 | `e1370c274d4981dd` | unused after the chains were parked |
| `weave-v0.5.4.tar.gz` | 1,487,207 | `e5a2da626bb329b7` | unused after the chains were parked |

**Crates.** `cargo fetch --locked` on the tag's lock downloaded **404 crate files (87 MB)** for
all targets. cargo checked each one against the lock's sha256. The unpacked sources (980 MB) were
then deleted from the cache.

**Task images.** The task images download Rust 1.100.0 for their own architecture from
static.rust-lang.org and check each component against pinned sha256s. The x86_64 values are taken
from the same manifest. The amd64 base uses snapshot.ubuntu.com `20261126T000000Z`; the arm64
snapshot needs authorisation, so arm64 uses the ports archive with git pinned exactly.

## 8. Commits (Phase B, branch `neel/weave-merge-driver-rebuild`, all pushed)

| Commit | What |
| --- | --- |
| `3b6c5df1` | chains parked by the owner (kept as history); difficulty sizing in `notes/DESIGN.md` |
| `794d663a` | spike tooling: case generator, runner, stubs, scoring, mutants, oracle patch, private export, diffy stub, spike Docker files |
| `d872e548` | routing cases in the generator |
| `3cc2d8fe` | README follows the owner's Phase B changes |
| `b02230c9` | bounded core-dump probe; the export refuses inputs above 100,000 bytes |
| `4336322b` | task images, verifier, specification (16 chapters), solution lock and staging script |
| `ef63be0b` | README: Phase B results and dev log |
| (this commit) | `notes/PHASE-B-REPORT.md`; README milestone row |

harbor-lh `neel/swe-m2-ops` (via `push_ops.sh`): the spec reviews and the trim check
(`qa/weave/02-05`), the steps-decision addendum, and the private backup (`weave-private.bundle`,
`phaseB-tools/`).

## 9. Deviations and incidents

- **Job 6 (protection probe) hung for 13.4 h while holding the shared lock.**
  - Its core-dump step sent SIGSEGV. The Rust runtime handles SIGSEGV, so the process survived,
    stayed blocked opening a FIFO, and `wait` never returned.
  - The coordinator stopped the container by exact name. The wrapper then released the lock.
  - Every earlier probe step had passed. The core-dump check was rewritten:
    - every step has a timeout;
    - the FIFO's write end is opened to release a blocked reader;
    - it uses SIGABRT and SIGQUIT, which Rust does not catch;
    - an outer 300 s limit applies.
  - It was re-run alone in the agent image (section 4).
- **The builder image had no `/usr/bin/time`.** The first reference build stopped after 110 s.
  Timing now uses the shell, and peak memory comes from the container's `memory.peak`.
- **arm64 snapshot archive.** `snapshot.ubuntu.com/ubuntu-ports` answers 401, so arm64 images use
  the ports archive with `git=1:2.43.0-1ubuntu7.4` pinned. amd64 task images use the snapshot.
- **Memory gate.** Free memory sat at 25-29% for long stretches, and jobs waited up to about an
  hour for 30%. Nothing ran below the gate.
- **The Write tool was refused for new files in the worktree.** New files were drafted in the
  scratchpad and copied in with `cp`.
- **The specification was written with help.**
  - An agent drafted chapters 3, 5-9, 13, 15 and 16 from the tag.
  - Three independent reviewers checked every chapter against the code (records in harbor-lh
    `ops/swe-marathon-v2/qa/weave/01-04`). Every finding was fixed and re-checked in the code.
  - Two editing passes then cut words without changing a condition.
- **Generator gaps.** The routing sub-family keeps only its marker cases: the diffy program
  reproduces the binary and encoding cases, so they are dropped. No case is larger than 9.4 KB;
  the specification now says inputs are at most 100,000 bytes, and the export refuses anything
  larger.

## 10. Next steps

1. Run QA per `notes/QA-PLAN.md`: at least 20 independent adversarial passes before any run. The
   first lenses are spec-to-case coverage (every graded rule stated, every stated rule exercised
   or declared out of scope), hackability and difficulty.
2. Widen the generator. The binary and encoding routing cases are dropped, and F9 (40) and F5 (80)
   are small, so add recipes where the reference's behaviour turns on one stated rule. Keep each
   family's stub rate low.
3. Size the difficulty with measured trials only after Oddish pre-trial QA passes, per the hard
   rule. Until then run only oracle and nop.
4. Decide with the coordinator whether to adopt the stated 12-hour budget (one parameter, section
   2).
5. Before upload, sweep for cue words and for unexploited information leaks: images, docs and
   help text.
