# Spike plan and the exact download list (Phase A, 2026-11-26)

> **2026-11-27:** single-step now. S2's 1.1.2 build is skipped (the coordinator's note: it was only
> needed for the no-upgrade anchor, which is gone). S2 took its named fallback: the static musl
> build failed Cedar evaluations at random, so the release is a glibc build with mode 2711.
> Results are in PHASE-B-REPORT.md.


Author notes, never shipped.

**Nothing on this page has been downloaded, built or run.** Phase A used only:
- a read-only clone that already existed;
- read-only API metadata from GitHub and crates.io;
- AWS's AgentCore page.

The spike starts when the owner approves the list in section 2.

**Order:** S's assets first (1.2.0), then 1.1.2, as the panel's opus vote asked. The step-1 work
is committed only after the long-chain probe (S9) grades step 2 reliably.

## 1. The spike: what it settles, with a pass criterion each

| # | Item | Pass criterion | If it fails |
| --- | --- | --- | --- |
| S1 | Fetch the two pinned sources (1.2.0 `8ffd2106`, 1.1.2 `929f49e7`) and the two `dogwood-cli` `.crate` files; record SHA-256s | Checksums recorded. The clone's measurements hold for the 1.2.0 tag: the 5 commits after the tag touch CI, `AGENTS.md`, one line of `CHANGELOG.md`, 17 lines of `RELEASE_NOTES.md` and Lean files only (GitHub compare) | n/a |
| S2 | Freeze one `Cargo.lock` per release. Prefer the lock packaged in `dogwood-cli-<ver>.crate` if it has one; otherwise generate it, pinning `cedar-policy` 4.11.0 for 1.1.2 and the dated `vstd` for 1.2.0. Build `dogwood-cli` with `--features experimental-arithmetic --target x86_64-unknown-linux-musl --offline --locked` from a vendored directory | Both build offline and statically. `vstd =0.0.0-2026-09-20-0158` resolves from the vendor directory. Peak RAM and time recorded | Use a glibc build with mode 2711; record why |
| S3 | Run every shipped bundle of each tag through its build (1.2.0: 93 `explain.out`, 56 `expected.out`; 1.1.2 likewise) | Byte-identical to the shipped files | Regenerate the shipped outputs from our build and note it in the dev log; any drift gets a reason, such as a floated dependency |
| S4 | Determinism | 3+1 identical per-case verdict files on 200 generated bundles per version. At least 10 repeats of multi-permit replays (does `[rules: …]` move?), multi-environment `validate` on 1.1.2 (how many messages move?) and `lower --emit cedar-schema`/`cedar-json` (does Cedar's printer order move?). Rhai provider outputs that iterate maps are checked too | Moving outputs are normalised only if they are one of the two documented orders; anything else is dropped |
| S5 | Mutants on 1.2.0 first: M-dedup, M-scope, M-naive, M-global from patched source; then on 1.1.2 | Over the 56 shipped replay bundles, M-dedup changes none (predicted), and M-scope changes none unless combined with M-global. Over 300 generated bundles tagged by intent, each mutant's failures fall in its family. M-dedup projects to 0.70-0.85 under the DESIGN weights | Fix the tagging or the weights before any QA pass. A mutant that leaks into other families means the dual templates need work |
| S6 | Generator yield. Adapt upstream's conformance generator: trace knobs set to strictly increasing and in-contract; 1.2-only constructs filtered for step 1. Run fresh seeds | At least 3 discriminating cases per feature id for a first inventory sample of 60 ids. Changed-partition share between 1.1.2 and 1.2.0 measured per family. Stub pass rates measured for Z4, Z6, Z8, Z9 and Z10 | Write targeted templates for thin ids; raise the changed quota with 1.2.0 item templates |
| S7 | Protection probe in a local `linux/amd64` container, as a non-root user against the mode-2711 static binary | Read, copy, `ptrace`, `LD_PRELOAD`, `/proc/<pid>/{exe,mem}` and core dump all fail; the staging directory cannot be listed | Change the modes or the group design |
| S8 | Verifier timing. In a verifier-like container (toolchain plus the same registry, no network), build the 1.2.0 source as if it were a submission, then run 1,200 cases with 4 workers. Also run a worst-case submission that sleeps on every case | Build plus cases well under 2,700 s; the worst case is cut cleanly by the global deadline | Cut the case count, not agent time (panel) |
| S9 | Long-chain idle probe on the platform (later phase, owner's go and no Oddish in Phase A): reference and no-op, full-length steps, a large `target/` at collection | Both steps graded in 2 of 2 chains; total at most about 42,000 s | Ship the single-step fallback S |

**Where things are built:**
- **Reference binaries (the authoritative ones):** built inside the agent image's builder stage,
  Linux x86_64, at image build time. During the spike this happens in local Docker; on the
  platform it happens at upload. Network is allowed only at build. Gold is recorded with the
  binary copied out of that image, run in a `linux/amd64` container.
- **Mutants (2 versions x 40-80) and generator batches:** run on a Linux x86_64 build machine with
  Docker, 8+ cores and 16+ GB of memory.
- **The shared laptop (RAM-tight, with three watchers and a game build):** does only the light
  items: S1, S3's runs and S7. It uses `--platform linux/amd64` under the memory guard. A Rust
  release build of `dogwood-cli` under amd64 emulation on Apple silicon is expected at 30-60
  minutes and 3-5 GB, so it is not the place for mutant builds.
- **Not needed:** meson, ninja and fontTools, which belong to the HarfBuzz pick. Lean and `elan`
  are not needed either: we do not run upstream's Lean conformance.

## 2. Exact download list (for the owner's approval)

Sizes come from the GitHub and crates.io APIs where marked; the others are estimates. Every item is
checksum-pinned at first download, and the checksums go into the dev log.

### Sources

| # | Item | Source URL | Size | Why |
| --- | --- | --- | --- | --- |
| D1 | Dogwood 1.2.0 source, tag commit `8ffd2106daf08cc3350a45b36866d75b41234ca3` | `https://codeload.github.com/dogwood-policy/dogwood/tar.gz/8ffd2106daf08cc3350a45b36866d75b41234ca3` | About 15-25 MB compressed, about 175 MB unpacked (137 MB of it is an unused Cedar fuzz corpus); repository pack 12.9 MB per the API | Step 2's reference build and oracle; the 1.2.0 guide, bundles and release notes to trim; the conformance generator (4,087 lines, stdlib-only Python) |
| D2 | Dogwood 1.1.2 source, tag commit `929f49e7305534ac61ef06cf8e47269c596dc851` | `https://codeload.github.com/dogwood-policy/dogwood/tar.gz/929f49e7305534ac61ef06cf8e47269c596dc851` | About 15-20 MB compressed (estimate) | Step 1's reference build and oracle; the 1.1.2 guide and bundles |
| D3 | `dogwood-cli` 1.2.0 package | `https://static.crates.io/crates/dogwood-cli/dogwood-cli-1.2.0.crate` | 26,868 B (crates.io) | Whether upstream published a `Cargo.lock` with the binary crate: the sanctioned dependency versions for 1.2.0 |
| D4 | `dogwood-cli` 1.1.2 package | `https://static.crates.io/crates/dogwood-cli/dogwood-cli-1.1.2.crate` | 31,981 B (crates.io) | The same for 1.1.2 |

### Rust toolchain

| # | Item | Source URL | Size | Why |
| --- | --- | --- | --- | --- |
| D5 | Rust 1.100.0 (released 2026-11-12, today 14 days old; upstream CI's "stable" when 1.2.0 was cut), minimal profile: `rustc`, `cargo`, `rust-std` for `x86_64-unknown-linux-gnu`. Fallback 1.99.1 (2026-10-16), which was stable when 1.1.2 was cut | Pinned official image `docker.io/library/rust:1.100.0-slim-bookworm` (by digest), or `https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init` plus `https://static.rust-lang.org/dist/2026-11-12/` channel files | Image about 250-300 MB compressed (estimate); rustup route about 120 MB download, 600 MB installed | Build both references; the agent's and the verifier's toolchain. All dependencies need at least 1.89 (Cedar 4.11/4.14, `rustc-literal-escaper` 0.0.8 `rust-version`) |
| D6 | `rust-std` for `x86_64-unknown-linux-musl` (same release) | `https://static.rust-lang.org/dist/2026-11-12/rust-std-1.100.0-x86_64-unknown-linux-musl.tar.xz` | About 30-40 MB (estimate) | Static, execute-only reference binaries (no dynamic loader for `LD_PRELOAD`). Builder stage only |

### Crates

| # | Item | Source URL | Size | Why |
| --- | --- | --- | --- | --- |
| D7 | crates.io index entries for the dependency graphs | `https://index.crates.io/` (sparse) | A few MB | Resolving and freezing the two locks |
| D8 | Every `.crate` in the two frozen locks (union). Top-level, with crates.io sizes where known: | `https://static.crates.io/crates/<name>/<name>-<version>.crate` | About 150-250 crates and about 30-60 MB in all (estimate; the exact list is the two locks, committed in the spike) | Reference builds; the agent's and the verifier's offline registry |
| | - `cedar-policy` 4.11.0 (212,905 B) and 4.14.0 (270,345 B) | | | |
| | - `cedar-policy-core` 4.11.0 (692,284 B) and 4.14.0 (759,778 B) | | | |
| | - `rhai` 1.x (1.27.0 is 525,072 B; the version comes from the lock) | | | |
| | - `pest` and `pest_derive` 2.x (2.9.7 is 145,186 B and 22,579 B) | | | |
| | - `vstd` `0.0.0-2026-09-20-0158` (328,288 B, MIT; 1.2.0 only) | | | |
| | - `rustc-literal-escaper` 0.0.7 (1.1.2) and 0.0.8 (14,104 B; 1.2.0) | | | |
| | - `cedar-policy-mcp-schema-generator` 0.6.x (1.1.2 build only) | | | |
| | - `miette` 7.6.0 (114,499 B), `clap` 4.x, `regex` 1.x, `rust_decimal` 1.x, `serde`/`serde_json`, `sha2` 0.10.x, `smol_str`, `nonempty` 0.12.0 (13,105 B), `thiserror`, `lalrpop-util` | | | |

The agent's registry is a subset of D8: the allow-list in DESIGN section 1, with no `dogwood-*`
crate.

### Images and packages

| # | Item | Source URL | Size | Why |
| --- | --- | --- | --- | --- |
| D9 | Debian base for runtime stages | Pinned `docker.io/library/debian:bookworm-slim` (by digest), if the runtime stages do not use D5's image | About 28 MB compressed (estimate) | Agent and verifier runtime stages |
| D10 | Debian packages: `python3` (verifier, generator), `ca-certificates`; `musl-tools` only if a dependency compiles C (none expected) | `deb.debian.org` bookworm | About 30-60 MB (estimate) | Verifier runtime; case generation and recording |

### Explicitly not downloaded

- Lean/`elan` and cedar-lean;
- the Dogwood LSP, the local engine, the wasm and python packages;
- Node, mdBook, Hypothesis and pip packages;
- MCP crates beyond what 1.1.2's lock needs to build;
- upstream's other repositories.

**Network after the spike:**
- Only image builds reach the network, as `task.toml`'s `open_internet_justification` says.
- The agent and the verifier run with no network.
- Downloads at image build are pinned by commit and checksum, so a rebuilt image is the same
  image.
