# Spike plan and download list (Phase A; nothing downloaded yet)

Author notes, never shipped. **Every download below needs the owner's explicit OK first.** Phase A downloaded,
built and ran nothing. The spike is the first piece of Phase B: two to three days on a Linux x86_64 build host.
It decides whether the build goes ahead (pass) or the task is cut down or dropped (fail), and it retires the
unverified claims in [CLAIMS.md](CLAIMS.md).

## Where things are built

| Place | What runs there | Why there |
| --- | --- | --- |
| **Build host**: Linux x86_64, 8+ cores, 16+ GB RAM, Docker. A team GPU server's CPUs or a cloud VM; a private-repo CI matrix on ubuntu-24.04 runners is the second choice | All HarfBuzz builds (base, 15.0.0, 15.1.0, 15.2.0, about 57 R_k, 3 W, 7 stubs), font building with fontTools, the sweep, attribution, gold recording, 3+1 determinism | The reference binaries must be Linux x86_64 and built in the same pinned image as the verifier. About 70 builds of a few minutes each (estimated) do not belong on the shared laptop |
| **Agent image** (built by the platform, network at build only) | Fetch the 14.3.0 tree and docs, install the toolchain | As our other tasks do |
| **Verifier image** (built by the platform, network at build only) | Install the toolchain; copy staged private cases, fonts, gold and driver sources | Gold comes in precomputed, so this image compiles no reference and stays light (DESIGN.md section 4) |
| **Laptop** (this machine) | Authoring only: scripts, documents, ruff | Shared with three watchers and a game build; no downloaded code runs here |

Spike-only fallback if no build host is free: one base/target build pair under local Docker with
`--platform linux/amd64`, behind the memory guard, for S2 and S3 only. No mutant builds locally.

## Download list

Sizes are approximate (from comparable releases; none was fetched). Every pinned item records its SHA-256 at
download, and that hash goes into the Dockerfiles.

### A. HarfBuzz sources (Old MIT)

| # | Item | Source | Size | Why | Used in |
| --- | --- | --- | --- | --- | --- |
| A1 | Release tarball 14.3.0 | https://github.com/harfbuzz/harfbuzz/releases/download/14.3.0/harfbuzz-14.3.0.tar.xz | ~20 MB | The agent's base tree; the base build | agent image, build host |
| A2 | Release tarballs 15.0.0, 15.1.0, 15.2.0 | `…/releases/download/<tag>/harfbuzz-<tag>.tar.xz` | ~20 MB each | Target builds, gold, the oracle patches | build host |
| A3 | Full history from 14.3.0 to 15.2.0 (fill the existing blobless clone, or a fresh `--filter=blob:none` clone with checkouts) | https://github.com/harfbuzz/harfbuzz.git, tags 14.3.0 to 15.2.0 (item commits in the CLAIMS.md inventory) | ~100-300 MB | Per-item reverts R_k; reading `README.md`, `CLAUDE.md`, `AGENTS.md`, `hb-config.hh`; the base tree's cue-word sweep | build host |

Tag commits (from the clone): 14.3.0 `4c2aa804671d7276e8a0eb95da07202ead05c843`, 15.0.0
`35f656a1a2bab548ea7f54a6dd3fba2b09680d14`, 15.1.0 `3df40d9b98d6b32f0e4288d4ecfbb158ddb3a372`, 15.2.0
`ed51d202cfd0c29372d3ee056eb0dc715688a410`. A1-A2 tarballs are checked against these by building from the tag
too (S2).

### B. Fonts (SIL OFL 1.1, checked per file at download)

Pinned to one commit of https://github.com/notofonts/notofonts.github.io (`fonts/<Family>/hinted/ttf/`). Each
family's licence file and `name` table are read before use (C20).

| # | Family (Regular unless noted) | Path under `fonts/` | Size | Why (items) |
| --- | --- | --- | --- | --- |
| B1 | Noto Sans Khmer, Noto Serif Khmer | `NotoSansKhmer/…`, `NotoSerifKhmer/…` | ~0.1-0.3 MB each | 4, 13, Khmer duals |
| B2 | Noto Sans Myanmar | `NotoSansMyanmar/…` | ~0.3 MB | 12, 13 |
| B3 | Noto Sans Devanagari, Noto Sans Bengali | `NotoSansDevanagari/…`, `NotoSansBengali/…` | ~0.3-0.5 MB each | 1, 7, 13, 34 duals |
| B4 | Noto Sans Balinese, Noto Sans Javanese, Noto Sans Tai Tham | `NotoSansBalinese/…`, `NotoSansJavanese/…`, `NotoSansTaiTham/…` | ~0.1-0.3 MB each | 2, 3, 13 (USE) |
| B5 | Noto Sans KR | https://github.com/notofonts/noto-cjk (pinned release, `Sans/OTF/Korean/NotoSansKR-Regular.otf`), subset with fontTools to the Hangul and jamo blocks | ~5-10 MB before subsetting | 5, 29 |
| B6 | Noto Sans Hebrew | `NotoSansHebrew/…` | ~0.1 MB | 8 duals |
| B7 | Noto Sans Syriac, Noto Naskh Arabic, Noto Sans Arabic | `NotoSansSyriac/…`, `NotoNaskhArabic/…`, `NotoSansArabic/…` | ~0.2-0.5 MB each | 9, 10, 11 duals, broad held-fixed |
| B8 | Noto Sans, Noto Serif (variable) | `NotoSans/unhinted/variable-ttf/…`, `NotoSerif/…` | ~1-2 MB each | Broad held-fixed, extents and variation duals |

About 15-25 MB in all. Hidden: they sit only in the verifier and on the build host, never in the agent image.

### C. Python packages (pinned versions, wheels with hashes)

| # | Package | Source | Size | Why | Used in |
| --- | --- | --- | --- | --- | --- |
| C1 | fontTools (latest 4.x at download) | https://pypi.org/project/fonttools/ | ~5 MB | Building test fonts (us and the agent) | build host, agent image |
| C2 | packTab | https://pypi.org/project/packtab/ (upstream's make file installs it from https://github.com/harfbuzz/packtab) | <0.1 MB | `gen-ucd-table.py` and `gen-use-table.py` import it (C34) | agent image, build host |
| C3 | meson (the version 15.2.0's CI uses, at least the minimum in 14.3.0's `meson.build`) | https://pypi.org/project/meson/ | ~2 MB | Build system (Ubuntu's 1.3.2 may be too old; checked in S2) | all three |
| C4 | Not installed, on purpose: uharfbuzz, skia-python, anything bundling HarfBuzz | – | – | A newer HarfBuzz in the agent image would be the answer | – |

### D. System packages (Ubuntu 24.04, apt pinned to one snapshot.ubuntu.com date)

| # | Packages | Size | Why | Used in |
| --- | --- | --- | --- | --- |
| D1 | `ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8` (the digest Goose pins) | ~30 MB | One base for gold host, agent and verifier | all three |
| D2 | `build-essential` (gcc/g++ 13), `pkg-config`, `ninja-build`, `python3`, `python3-venv`, `python3-pip`, `ca-certificates`, `git` | ~250 MB installed | Toolchain | all three |
| D3 | `ragel` (6.10) | ~1 MB | `src/meson.build` regenerates the `.rl` machines when ragel 6.10 is present (C39) | agent image, verifier, build host |
| D4 | `libglib2.0-dev` | ~10 MB | So the agent can build `util/hb-shape` for its own experiments (the product build disables GLib) | agent image only |

### E. Documents for `/app/docs` (licences checked before shipping; fallback is our own digest)

| # | Document | Source | Size | Why |
| --- | --- | --- | --- | --- |
| E1 | Unicode 18.0.0 UCD files: `UnicodeData.txt`, `Scripts.txt`, `Blocks.txt`, `ArabicShaping.txt`, `DerivedCoreProperties.txt`, `IndicSyllabicCategory.txt`, `IndicPositionalCategory.txt`, `PropertyValueAliases.txt` | https://www.unicode.org/Public/18.0.0/ucd/ (`UCD.zip`, ~7 MB) | ~7 MB | Table generators' inputs (`update-unicode-tables.make`). **Versions must match those 15.2.0 recorded (C33)**; if the dated pre-release files are gone, S7 decides which code points stay |
| E2 | `DerivedCoreProperties.txt` 17.0.0 | https://www.unicode.org/Public/17.0.0/ucd/DerivedCoreProperties.txt | ~3 MB | 15.2.0's USE table was generated from the 17.0.0 copy (C33) |
| E3 | `ucd.nounihan.grouped.zip` 18.0.0 | https://www.unicode.org/Public/18.0.0/ucdxml/ucd.nounihan.grouped.zip | ~1.5 MB | `gen-ucd-table.py`'s input |
| E4 | `emoji-data.txt`, `emoji-test.txt` (18.0) | https://www.unicode.org/Public/18.0.0/ucd/emoji/emoji-data.txt, https://www.unicode.org/Public/emoji/18.0/emoji-test.txt | ~1 MB | `gen-emoji-table.py`'s inputs |
| E5 | IANA language subtag registry (the `File-Date` 15.2.0's tag table used) | https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry | ~0.9 MB | `gen-tag-table.py`; item 35 |
| E6 | OpenType language system tags page | https://learn.microsoft.com/en-us/typography/opentype/spec/languagetags | ~0.3 MB | `gen-tag-table.py`; item 35 |
| E7 | OpenType specification pages: `otff`, `chapter2`, `gsub`, `gpos`, `gdef`, `base`, `jstf`, `cmap`, `glyf`, `head`, `hhea`, `vhea`, `hmtx`, `vmtx`, `OS2`, `STAT`, `fvar`, `avar`, `gvar`, `HVAR`, `MVAR`, `otvarcommonformats`, `COLR`, `CPAL`, `CBDT`, `CBLC`, `kern`, `featuretags` and the feature registry pages, `scripttags` | https://learn.microsoft.com/en-us/typography/opentype/spec/ | ~5-10 MB HTML | The notes' table semantics (items 30, 31, 38-42, 49, 50); confirms `CBDT` format 19 (C30) |
| E8 | Microsoft script development specs: Khmer, Myanmar, Devanagari, Bengali, USE, Hangul, Hebrew, Arabic | https://learn.microsoft.com/en-us/typography/script-development/ (`khmer`, `myanmar`, `devanagari`, `bengali`, `use`, `hangul`, `hebrew`, `arabic`) | ~2 MB | Script items 1-9, 12-13 |
| E9 | Apple TrueType Reference Manual, AAT tables: `morx`, `mort`, `kerx`, `kern`, `trak`, `ankr`, `feat`, and the font feature registry | https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6morx.html (and `Chap6mort`, `Chap6kerx`, `Chap6kern`, `Chap6trak`, `Chap6ankr`, `Chap6feat`), `RM09/AppendixF.html` | ~1-2 MB | F4 items; the binary layouts our assembler and the agent need |
| E10 | UAX #29 (text segmentation) | https://www.unicode.org/reports/tr29/ | ~0.3 MB | Cluster levels and graphemes (items 28, 29) |
| E11 | Microsoft's Universal Shaping Engine override files for Unicode 18: `IndicSyllabicCategory-Additional.txt`, `IndicPositionalCategory-Additional.txt` | Upstream history (A3) at `cdbe72ca` (14.5.0, "[USE] Update the data files for Unicode 18.0") | ~10 KB | Upstream changed both in 14.5.0, and they cannot be derived from the UCD (CLAIMS.md C40). Shipped as specification data beside E1, not as code |

## Spike checks (pass/fail)

| # | Check | Pass | If it fails |
| --- | --- | --- | --- |
| S1 | Fetch A, D and E; record hashes; read the licences (C18, C20, Unicode); read 14.3.0's `README.md` (C1), `CLAUDE.md`, `AGENTS.md`, `CODE_OF_AI_CONDUCT.md` | All hashes recorded; licences allow shipping, or a digest plan exists per document; the agent files judged keep/remove | Replace a document with our digest; remove agent files that steer or cue |
| S2 | Build 14.3.0, 15.0.0, 15.1.0 and 15.2.0 with the product command (DESIGN.md section 3) in the pinned image, ragel present and absent | All four build; on 4 CPUs each takes at most 6 min; outputs identical with and without ragel on a smoke set | Adjust options or meson version; a build over 10 min reopens the verifier budget |
| S3 | Driver smoke: our driver on the inputs of the 16 new `khmer-misc.tests` lines with upstream's own test font (spike only, never shipped), base against 15.2.0 | 8 lines differ (the commit says eight fail before the fix); 15.2.0's outputs equal upstream's expectations | Fix the driver before anything else |
| S4 | Synthetic AAT fonts: (a) a fontTools `trak` font, vertical text, item 22; (b) a `kerx` format 0 and format 2 font from our assembler with a `GPOS` that has no kerning feature, item 23; (c) an AAT `kern` format 1 cross-stream font, item 20. Also check whether the newest fontTools has gained a `kerx` writer | (a) and (b) give base ≠ 15.2.0 outputs that R_k reverts | Without (b), F4 loses units 23, 25a, 25b and 27: cut them and say so |
| S5 | Noto yield for items 1, 2, 3, 4, 7 and 12: 10,000 generated strings per item, attributed with R_k | At least 20 attributable changed cases for at least 4 of them; at least 3 for every item kept | Cut or merge low-yield items; add synthetic fonts |
| S6 | Revert every item's candidate commits (CLAIMS.md inventory) on its release, build R_k | At least 80% of units revert cleanly alone; the rest revert as merged stacks | Merge units whose reverts conflict; drop units no stack isolates |
| S7 | Unicode fidelity: regenerate 14.3.0's tables from the shipped E1-E4 and E11 files with the generators as a competent maintainer would (new script values added), build, compare Unicode property queries and shaping with 15.0.0 | Mismatches confined to code points we can drop, with at least 20 cases per Unicode unit left | Ship the exact pre-release files if obtainable; otherwise drop the mismatched code points, or cut 33/34 |
| S8 | Verifier dry run: build a candidate tree (15.2.0) and run about 2,000 cases in the verifier layout on 4 CPUs | Done in at most 10 min | Fewer cases per item; split batches |
| S9 | Spec availability: `CBDT` format 19 in the public `CBDT` page (C30); whether `FeatureVariations` 1.1 is publicly specified (item 32) | Format 19 present | Cut 50; item 32 stays out unless public |
| S10 | 3+1 determinism on base and 15.2.0 for the S3 and S5 cases | Byte-identical verdicts | Find the source; drop the case class |
| S11 | Mutant W prototype for items 4, 21 and 23 with 20 duals each | W passes the changed cases and fails at least half of each item's duals | Rethink the duals or the failure sentence (CLAIMS.md, section 5) |

**Go/no-go.** S2, S3, S6, S8 and S10 must pass. S4, S5, S7, S9 and S11 may fail item by item; the task goes ahead if
at least 40 units survive and every family keeps at least 2. The result and the per-item yield go into the README's
development log and the private item catalogue.
