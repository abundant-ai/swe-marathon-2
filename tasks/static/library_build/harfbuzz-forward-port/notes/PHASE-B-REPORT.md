# Phase B report: HarfBuzz forward-port (in progress)

Author notes, never shipped. Phase B: the downloads, the spike and the first build milestone, under the shared-machine
rules (heavy lock, at least 30% memory free, containers at 4 GB, 5 GB of disk). This file is filled in as results
land; the summary at the top is rewritten last.

## Plan changes from the owner

- **Single step (2026-11-26).** "we dont have to promote multi-turn as well so make stuff likewise": one instruction,
  one 34,560 s session, graded as the old step 3 (all 56 units against 15.2.0, with the held-fixed duals gate). The
  `steps/` layout is gone (commit `47b8f47`); notes/STEPS.md is kept as history, marked parked. The spike's per-step
  chain measurements were dropped; nothing else in the spike depended on steps.
- **Difficulty (2026-11-27).** "if its hard enough in single turn make sure to have it difficult enough": target
  frontier at most about 0.6. notes/DESIGN.md section 13 holds the sizing.

## Downloads

Fetched with `scripts/fetch_inputs.sh` into `~/Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port/`; the
cache's `MANIFEST.tsv` lists every file with its source URL, size and SHA-256. One URL had moved (the emoji test file
is now under `/Public/18.0.0/emoji/`); the script tries both. The history clone (blobless, 17 MB) fetches blobs on
demand.

| Group | Files | Bytes |
| --- | --- | --- |
| HarfBuzz release tarballs | 4 | 81,493,016 |
| Fonts (Noto, licence files) | 17 | 9,892,742 |
| Python wheels | 3 | 2,454,532 |
| Unicode and language data | 10 | 9,464,863 |
| Specification pages | 51 | 5,318,215 |
| All | 85 | 108,623,368 |

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `harfbuzz-14.3.0.tar.xz` | 19,819,024 | `16070d77cfc4ba1f1e7327e83bf9b3f55898081cabdb94e56a33e04fc8874eae` |
| `harfbuzz-15.0.0.tar.xz` | 20,396,372 | `968536e9abd782f07f7954044c0c4020199fcdd39b41d221ec42d2a3be4a44df` |
| `harfbuzz-15.1.0.tar.xz` | 20,515,628 | `0fc7c565443a5f4be7da65ac5ee5bd737d9b158dc908708b7689a0a5796b0c8d` |
| `harfbuzz-15.2.0.tar.xz` | 20,761,992 | `e2ec49090744383cdbe7df808c1cedaafba06a97be8dc4211fe546ba585f12cb` |
| `fonttools-4.69.1-py3-none-any.whl` | 1,301,769 | `20e9dfac71694d9eeae48bb53c877bdf43b914794d69a769940728a1929cc835` |
| `packtab-1.9.0-py3-none-any.whl` | 44,095 | `5641d7505ea726c21501101af32f21908180db84eae0f04e3b70a5cb40fd10a1` |
| `meson-1.12.1-py3-none-any.whl` | 1,108,668 | `930bc7542cbd9f57009e182fd014eba48cf1a0180a7b9006d2d32d8f168d8b02` |
| `UCD-18.0.0.zip` | 5,657,953 | `7b3e555514060b92290d154f53655c5eb0fa62b16eb04c03434ff72d1a66a0d8` |
| `DerivedCoreProperties-17.0.0.txt` | 1,134,783 | `24c7fed1195c482faaefd5c1e7eb821c5ee1fb6de07ecdbaa64b56a99da22c08` |
| `ucd.nounihan.grouped-18.0.0.zip` | 1,037,692 | `552bef87e5bf69d0047048d1e5762d352ab817aecc1a35b955628e8f1a4707ee` |

Fonts (Noto at `notofonts.github.io@d14cc173`, Korean at `noto-cjk@f8d15753`), the remaining Unicode files and the 51
specification pages are in the manifest with their hashes.

## Spike results

| # | Check | Result | Pass? |
| --- | --- | --- | --- |
| S1 | Fetch, hashes, licences, upstream agent files | All 85 files hashed. Fonts: OFL (each family's `name` table to be read in a container); Unicode data: Unicode License V3; Microsoft and Apple pages: no licence grant found, so they ship as our own digests. `CLAUDE.md` is a symlink to `AGENTS.md`, whose rules (narrow changes, preserve behaviour) fit the work order: kept, minus its `perf/` line. Pruned besides `perf/`: `CODE_OF_AI_CONDUCT.md` ("benchmarks"), `test/vector/README.md` ("golden files"), the benchmark meson wiring | Pass |
| S2 | Product build of the four releases, ragel on and off, time on 4 CPUs | pending | |
| S3 | Driver against upstream's 16 new Khmer lines | pending | |
| S4 | Our own AAT fonts (`trak`, `kerx`, `kern`) | pending | |
| S5 | Attributable changed cases per unit on Noto fonts | pending | |
| S6 | Revert cleanliness | 48 of 56 units revert cleanly on their own (85.7%) with strict `git apply` into an index of each unit's release, once patches cover only the library's build inputs | Pass |
| S7 | Unicode fidelity | Versions: the final 18.0.0 files carry exactly the dates upstream recorded, so upstream used final files (Phase A's "pre-release" corrected); `DerivedCoreProperties` 17.0.0 is the one difference, and we have it. New: the IANA registry is newer (2026-11-18) than the one 15.2.0's tag table used (2026-09-17). Regeneration check pending | Partial |
| S8 | Verifier dry run | pending | |
| S9 | Spec availability | `CBDT` format 19 is in the public `CBDT` page (unit 50 stays); `FeatureVariations` 1.1 and `DMAP` are not public (stay out) | Pass |
| S10 | 3+1 determinism, plus an emulated amd64 sample | pending | |
| S11 | Mutant W prototype | pending | |
