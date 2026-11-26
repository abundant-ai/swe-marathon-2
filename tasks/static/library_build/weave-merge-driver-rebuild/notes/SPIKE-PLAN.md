# Weave merge-driver rebuild: probation spike and download list (Phase A, 2026-11-26)

Author notes. **Nothing below may be downloaded or built until the owner approves this list**
(Phase A rule). The spike decides the third library pick: if all four checks pass, Weave is pick 3
(single step); if any fails, or the owner declines to vendor `sem-core`, Weave drops back to
alternate (stop at two, or take syntaqlite fmt). Days 4-5 then settle whether a two-step chain
follows (`STEPS.md` section 5).

## 1. Where things are built

- **All builds and runs on a Linux x86_64 host with Docker** (one of the team's Linux machines, or a
  build VM): the original, the oracle, the mutants and all three images are Linux x86_64 ELF.
  Images are built with `--platform linux/amd64` from one pinned base digest.
- **Not on the shared Mac**: no Docker, no Rust build, no emulation there. The Mac edits text and
  runs small scripts over recorded results only.
- **The task images**, when the task is built, compile the original from the pinned tag at
  image-build time with network allowed at build only, as Goose does; the agent's turn has no
  network.
- Private outputs of the spike (cases, the seed, recorded bytes) go to the task's Git-ignored
  `tests/private/` and `experiment/` on the build host, and to the private bundle in harbor-lh
  (`ops/swe-marathon-v2/next-tasks/weave-merge-driver-rebuild-private/`), never to this repository.

## 2. The four probation checks (days 1-3)

| Day | Check | Pass criterion | Fail means |
| --- | --- | --- | --- |
| 1 | **1. Execute-only build, deterministic.** Build the original from `v0.7.1` (`527ccb3`) in the recording image (pinned base, pinned `git`, pinned Rust); install it execute-only in a draft agent image; record a 200-case sample 3 times plus once perturbed (other `TMPDIR` length, other directory name, one CPU, fresh processes) | identical bytes and status on all 200; as `dev`, read, copy, `strace`, `gdb`, core dump, `LD_PRELOAD` and `/proc/<pid>/mem` all fail; optional cross-check: upstream's published `weave-driver-x86_64-unknown-linux-gnu` writes the same bytes on the sample | alternate |
| 2 | **2. At least 1,000 discriminating cases.** Generator v0 (typed, family-tagged mutation of synthetic modules, written in Rust on the agent's own crates, so it needs no extra download), filtered by Z1-Z6 (take ours, theirs, base; `git merge-file` plain; git labelled diff3 plus the hint; `diffy` plus the hint) | at least 1,000 kept cases that every filter stub fails, with each family at its floor (DESIGN.md section 3) and F8 at least 100 refusals and 100 accept-duals; yield per family recorded | alternate |
| 2-3 | **3. M-gate in band, one family.** Patch the four call sites (VALIDITY.md section 2), build, run all kept cases | F8 net credit 0, every other family 1.0, overall 0.80 (inside 0.6-0.85); two other mutants (M-place, M-elem) move only their own families | alternate |
| 3 | **4. Specification about 30 pages and accurate.** Write chapters 1, 2, 12 and 14 in full and the rest as outlines with page estimates; an independent reviewer checks 30 rules against the tag's source | at most about 30 pages projected; no wrong rule in the sample and none in chapter 12 | alternate |

**Two checks added in Phase A** (they decide solvability, so they gate probation too):

5. **Oracle under the agent's toolset.** Build the tag's `weave-core` and `weave-driver` offline
   against the agent's 82 crates (`sem-core` with `lang-python`, `lang-typescript`, `lang-go`
   only), with the smallest patch that drops `git2`, `rayon` and `memmap2`. Pass: it writes the same
   bytes as the original on at least 99.5% of the generated cases (the rest are dropped). Fail: the
   given toolset cannot reproduce the installed build, so the task is not solvable as specified.
6. **Owner's word** on vendoring `sem-core` (a second Ataraxy crate) and on input corpora licences.

## 3. Days 4-5: the chain measurements

| Measurement | Build | Decides |
| --- | --- | --- |
| 0.6.2 scored on A's cases with A's verifier; count of step-2-only cases (CRLF, missing final newline, entities sharing a line) | `v0.6.2` (`848f66a`) with its lock (`sem-core` 0.28.0) | chain B (sonnet's and haiku's conditions) |
| 0.5.4 scored on A's cases; F8 at 0; fold-tagged step-1 set of about 400; entity differences between `sem-core` 0.23 and 0.29 | `v0.5.4` (`efbdd03`) with its lock (`sem-core` 0.23.0) | chain C (opus's conditions) |
| An idle full-length chain on the platform | the chosen chain's bundle | either chain |

## 4. Exact download list

All items need the owner's approval first. Sizes are approximate except where a byte count is
given.

### Base and system

| Item | Source | Size | Why |
| --- | --- | --- | --- |
| `ubuntu:24.04` pinned by digest (`sha256:73b99939...c4d6a8`, the digest Goose uses) | Docker Hub | about 29 MB compressed | one base for the agent, verifier and recording images |
| `git` (Ubuntu 24.04's 2.43.0 series), pinned to one package version through `snapshot.ubuntu.com` | Ubuntu archive | about 5 MB with its dependencies (`git-man`, `liberror-perl`, `perl` modules about 20 MB) | the driver calls `git merge-file`; one exact version everywhere |
| `build-essential`, `pkg-config` | Ubuntu archive | about 200 MB installed | the C compiler for the tree-sitter grammars and `libgit2-sys` |
| `python3` | Ubuntu archive | about 30 MB | the runner and the agent's own scripts |
| `ca-certificates`, `curl`, `procps`, `util-linux` (`taskset`) | Ubuntu archive | about 5 MB | fetching at build; the perturbed run; process checks |
| `strace`, `gdb` (probe image only, never in the agent image) | Ubuntu archive | about 15 MB | the protection probe tries them as `dev` |

### Rust

| Item | Source | Size | Why |
| --- | --- | --- | --- |
| `rustup-init` for `x86_64-unknown-linux-gnu` | `https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init` | about 15 MB | installs the pinned toolchain |
| Rust stable, minimal profile (`rustc`, `cargo`, `rust-std` for `x86_64-unknown-linux-gnu`), one exact version recorded at the spike, at least 1.85 | `https://static.rust-lang.org/dist/` | about 110 MB download, about 600 MB installed | the closure needs at least 1.85 (`diffy` 0.5.2, `hashbrown` 0.17.1, `indexmap` 2.14.0 and `getrandom` 0.4.3 use edition 2024; `tree-sitter` 0.26.13 needs 1.77), so Ubuntu's own `rustc` is too old |

### Upstream source and releases

| Item | Source | Size | Why |
| --- | --- | --- | --- |
| `weave` at tag `v0.7.1` (`527ccb3a951b...`) | `https://github.com/Ataraxy-Labs/weave/archive/refs/tags/v0.7.1.tar.gz` | about 1.5 MB (the tree is about 4.4 MB, 206 files) | the original, the oracle, the mutants, the specification |
| `weave-driver-x86_64-unknown-linux-gnu.tar.gz` and `checksums.txt` of v0.7.1 (optional) | `https://github.com/Ataraxy-Labs/weave/releases/download/v0.7.1/` | 8,434,507 and 1,917 bytes | cross-check our build's outputs against upstream's published binary |
| `weave` at tag `v0.6.2` (`848f66a`), days 4-5 only | `https://github.com/Ataraxy-Labs/weave/archive/refs/tags/v0.6.2.tar.gz` | about 1.5 MB | chain B measurement |
| `weave` at tag `v0.5.4` (`efbdd03`), days 4-5 only | `https://github.com/Ataraxy-Labs/weave/archive/refs/tags/v0.5.4.tar.gz` | about 1.2 MB | chain C measurement |

### Crates (from crates.io; full list with versions, sizes and checksums: `download-crates.tsv`)

| Set | Count | Size of `.crate` archives | Why |
| --- | --- | --- | --- |
| The agent's offline registry: `sem-core` 0.29.0, `tree-sitter` 0.26.13, `tree-sitter-python` 0.23.6, `tree-sitter-typescript` 0.23.2, `tree-sitter-go` 0.23.4, `diffy` 0.5.2, `serde_json` 1.0.154, `toml` 0.8.23, `tempfile` 3.27.0 and dependencies | 82 | 14.5 MB | vendored for the agent, the oracle and the verifier |
| The original's build, on top of those: the other 30 grammars, `ts-parser-perl`, `git2` and `libgit2-sys`, `rayon`, `memmap2`, `env_logger` and the rest of `Cargo.lock`'s closure | 140 more (222 in all) | 35.9 MB (50.3 MB in all) | `cargo build --locked -p weave-driver` with upstream's own features |
| Days 4-5: the closures of the `v0.6.2` and `v0.5.4` locks (`sem-core` 0.28.0 and 0.23.0 and their grammars) | to be listed from those locks | about 50 MB each, mostly shared | chain measurements |

The lists come from `Cargo.lock` at `e52ba82`, a feature-agnostic superset (it includes weave-core's
development dependencies and Windows-only crates; `cargo build -p weave-driver` fetches fewer).
The first spike step re-derives both lists from the tag's own lock and records any difference.
URL pattern: `https://static.crates.io/crates/<name>/<name>-<version>.crate`; each is checked
against its `Cargo.lock` sha256.

### Input corpora (optional; synthetic modules first)

| Item | Source | Licence | Size | Why |
| --- | --- | --- | --- | --- |
| `pallets/flask`, one pinned tag | GitHub archive | BSD-3-Clause | about 1 MB | realistic Python base files |
| `colinhacks/zod`, one pinned tag | GitHub archive | MIT | about 2 MB | realistic TypeScript base files |
| `spf13/cobra`, one pinned tag | GitHub archive | Apache-2.0 | about 0.5 MB | realistic Go base files |

No GPL inputs. No pip packages: the generator, filters and runner use the agent's own crates and
Python's standard library.

### Totals

About 50 MB of crates, about 5 MB of source, about 140 MB of toolchain and about 300 MB of system
packages per image build (cached across builds); optional: 8.4 MB release binary and about 3.5 MB
of corpora; days 4-5 add about 50 MB.

## 5. What the spike leaves behind

- The pinned digests, the `git` package version and the Rust version, recorded.
- `recording.json` for the sample (determinism, timing), `yield.json` per family, `band.json` for
  M-gate, M-place and M-elem, the oracle patch, chapters 1, 2, 12 and 14 of the specification, and
  the reviewer's accuracy note.
- A README development-log entry that states what ran and what did not, and the go or no-go.
