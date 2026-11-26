# Weave merge-driver rebuild: design (Phase A, 2026-11-26)

Author notes; never shipped to the agent. Phase A is design only: nothing here has been built,
run or measured unless a line says so. Code references are to the deep dive's read-only clone of
`Ataraxy-Labs/weave` at `e52ba82` (2026-11-21), nine commits after the `v0.7.1` tag (`527ccb3`);
where the two differ it is said. Claim checks are in `VALIDITY.md`, the step decision in
`STEPS.md`, the spike and downloads in `SPIKE-PLAN.md`.

## 1. The work order

The agent replaces `weave-driver` 0.7.1 on a merge path for Python, TypeScript, Go, JSON and TOML.
The story (`instruction.md`): a clean-room rewrite under a legal policy, because the team keeps
tools on its merge path in code it maintains; every downstream consumer depends on the bytes and the
exit status (the merge queue's replay, landing agents that trust exit 0, editors that parse the
boxes). The requirement is stated by what depends on it, and the request ends with a cut-over line.
There is no comparison vocabulary beyond "writes `OUT` byte for byte as the installed build writes
it", the accepted form from BasedPL and back office.

### What the agent gets (agent image)

| Item | Detail |
| --- | --- |
| The installed build | `/usr/local/bin/weave-driver`, built at image-build time from the pinned tag (`v0.7.1`, `527ccb3`) with upstream's own features, stripped, `root:<group>` mode 2711 (execute-only, setgid so the process is not dumpable and `LD_PRELOAD` is ignored). No source, `target/` or cargo cache of `weave-*` crates in the final image. `--version` prints `weave-driver 0.7.1`. |
| Our specification | `/app/docs/` (section 7): about 30 pages, written from the tag's code, plus upstream's `LICENSE-MIT` and `LICENSE-APACHE`. Upstream's README, `llms.txt`, docs site and CHANGELOG are not shipped: they contradict the code (VALIDITY.md, C14) and use "benchmark" nine times. |
| `git` | The image's pinned package, the same version as in the verifier and recording images. |
| Rust | A pinned stable toolchain (`rustc`, `cargo`; x86_64-unknown-linux-gnu, minimal profile). |
| Offline registry | 82 crates from `Cargo.lock` (SPIKE-PLAN.md, D-list): `sem-core` 0.29.0 with `lang-python`, `lang-typescript`, `lang-go` and no `git`, `parallel` or `mmap`; `tree-sitter` 0.26.13 and the three grammar crates; `diffy` 0.5.2; `serde_json`, `toml`, `tempfile`; their dependencies. No `weave-*` crate. Cargo is configured to use only this directory. |
| Python 3 | For the agent's own probe scripts. |
| Workspace | `/app/driver/` empty and owned by the agent user; `/app` root-owned and sticky. |

The agent runs as an unprivileged user (`dev`), with no network, for one step of 34,560 s.

### What the agent delivers

`/app/driver/`: a Rust project. `cargo build --release --offline` there builds
`target/release/weave-driver`. The verifier rebuilds it from source in a fresh container (the
delivered `target/` is removed first), so the binary graded is the code delivered, and a delivered
binary cannot stand in for source. A project that does not build gets reward 0 (a candidate defect,
not an evaluation error).

## 2. The hidden original and how it stays invisible

- **Agent image:** only the stripped, execute-only binary (above). Its child processes are visible:
  the reference runs `git merge-file` with three temporary files, and the command line shows in
  `/proc`. That reveals the line route, which the specification documents anyway (deep dive Q3).
  The driver's own diagnostics (`WEAVE_EVENT`, `WEAVE_AUDIT`, `WEAVE_DEBUG_ELEMENTS`, stderr lines
  such as `unverified merge`) stay usable for probing. They reveal rule names, not cases; the
  instruction scopes them out of the replacement.
- **Verifier image:** holds no original. Two ways to get recorded outputs; the spike picks one:
  1. *Recorded at verifier-image build* (Goose's accepted pattern): a build stage compiles the tag,
     runs every private case 3+1 times, applies the filters and writes `expected.json`; only the
     kept cases and outputs reach the final stage. Gold always matches the image's own `git`; the
     cost is a heavy image build after the agent's turn (the platform graded such a build after a
     capped 9.6 h run on 2026-11-24, n = 1).
  2. *Recorded in the spike's recording image* and shipped as `tests/private/expected.json`:
     a light verifier image, but the recording and verifier images must share the base digest and
     the exact `git` package, and a check must prove it at every build.
  Recommendation: option 1 for the first upload (proven on the platform), option 2 only if the
  idle full-length canary shows the heavy build is a problem.
- **Private inputs** (cases, seed, recorded outputs) never enter this public repository: Git-ignored
  `tests/private/`, plus a private backup bundle in harbor-lh
  (`ops/swe-marathon-v2/next-tasks/weave-merge-driver-rebuild-private/`).

## 3. Grading: one process per case, ten families

Each case is `(base, ours, theirs, path)` plus a family tag and feature ids. The runner, as root,
drops to a random uid for the submission, creates a fresh scratch directory outside any repository,
writes the three inputs, and runs `weave-driver base ours theirs -o out -l 7 -p <path>` with
`HOME` an empty directory, `TMPDIR` a fresh directory, `GIT_CONFIG_NOSYSTEM=1`,
`GIT_CONFIG_GLOBAL=/dev/null`, `LC_ALL=C.UTF-8`, `TZ=UTC`, no `WEAVE_*`, the pinned `git` first on
`PATH`, a 10 s limit, 2 GB of memory and a 16 MB output cap. A case passes when the exit status
equals the recorded one and the bytes of `out` equal the recorded bytes (for status 2: `out` must
not exist). Standard error is ignored (the instruction says so).

| Id | Family | Weight | Kept cases (target) | What it exercises | Its mutant |
| --- | --- | --- | --- | --- | --- |
| F1 | Disjoint entity edits, routing, layout sub-family | 10% | 150 | identity matching; edits to different definitions that a line merge conflicts on; markers in an input; status 2 for binary and non-UTF-8 inputs (near-boundary duals: a NUL after byte 8,192); the 1,000,000-byte limit from below; a small layout sub-family (CRLF, BOM, missing final newline, separator ties) | M-D1 (identity off), M-layout |
| F2 | Placement and ordering | 15% | 170 | anchor rank, input order, identity key, one side reordering, both reordering (base order for all three languages) | M-place (v1's ours skeleton) |
| F3 | Renames | 10% | 120 | identical-body and edited renames, call-site corroboration, short bodies, rare tokens, rehoming; every case at least 0.15 from each threshold | M-rename (identity only) |
| F4 | Edits by both sides to one definition; conflict boxes | 13% | 150 | the in-definition ladder (diffy, whitespace shortcut outside Python, decorator-aware merge), adjacent-line conflicts, scoped boxes, the frame cut, box refinement, the hint on the first closing marker | M-fold (0.4-style statement fold), M-frame |
| F5 | Containers | 7% | 90 | classes and type bodies merged member by member, git's plain merge as second opinion, member conflicts | M-container |
| F6 | Element union and its refusals | 8% | 100 | Go maps and keyed structs, TS object literals and export lists, Python dicts, tagged switches without fallthrough, `const` blocks, slices in test files; the element guards (duplicate key, both-changed element, type or tagless switch, no reparse) | M-elem |
| F7 | Imports and decorators | 7% | 90 | import-region union only when only import lines changed and no name binds twice; name lists; different decorators conflict in Python and TS | M-import, M-decor |
| **F8** | **Fail-closed gate (B)** | **20%** | **at least 200: at least 100 refusals, at least 100 paired accept-duals** | a composition that states a line too often or drops one both sides kept, re-declares a name, repeats a key or case label, renumbers an `iota` constant, leaves a name unbound, stops parsing, or makes JSON or TOML stop loading or repeat a key; refusals whose answer is one whole-file box (git's line merge is clean but fails the same checks), and accept-duals built the same way that pass | **M-gate** |
| F9 | Region rules | 5% | 70 | D0/D1 agreement and subsumption, D3 import set union, D4 layout-equal creations, D6 layout-only side; never for modify/delete, two renames, or markers | M-D |
| F10 | JSON and TOML | 5% | 60 | key paths as entities, data union, sections | M-data |

About 1,200 kept cases. Families map to capabilities, not to generator buckets; every case has
exactly one family. Rename cases closer than 0.15 to a threshold are dropped. Layout is uniform
(one blank line between top-level definitions, LF, a final newline, no BOM) outside F1's layout
sub-family, so a layout slip cannot erase the per-family signature (deep dive Q5).

**Why F8 needs accept-duals.** `fail_closed` (merge.rs 815-875) falls back to git's labelled
diff3 when a composition fails the checks. When git conflicts, the answer is git's own conflict
plus the hint line, which a "git plus hint" stub reproduces, so those cases are filtered out. What
remains is the case where git's line merge is clean but fails the same checks: one whole-file box
(`to_conflict_markers(..., "fail_closed")`), which an "always one box" stub reproduces. Paired
accept-duals (the same construction made valid: distinct labels, distinct names, a use whose
import survives) make that stub score at most half the family, and the per-family netting below
takes it to 0. An agent with every other feature but no gate passes the duals and fails the
refusals; its F8 credit is 0.

### Reward

```
p_f = passed_f / kept_f                      (fixed denominator per build)
s_f = max over the netting stubs of their pass rate in f   (measured at each build)
g_f = max(0, (p_f - s_f) / (1 - s_f))
reward = sum_f w_f * g_f
```

No delivery, or a project that does not build: 0. Infrastructure faults (a case that cannot be set
up, the verifier's own crash, an unreadable private input) are evaluation errors: no reward file.
`metrics.json` carries, per family, `p_f`, `s_f`, `g_f`, the case count and the failing feature
ids, so the first trials can confirm or refute the failure sentence.

## 4. Stub filters

| Stub | What it does | Use |
| --- | --- | --- |
| Z1 take ours | copy OURS, exit 0 | **filter**: drop every case it solves |
| Z2 take theirs | copy THEIRS, exit 0 | filter |
| Z3 take base | copy BASE, exit 0 | filter |
| Z4 git plain | `git merge-file -p OURS BASE THEIRS`; exit 0 if clean, else 1 | filter |
| Z5 git labelled plus hint | `git merge-file -p --diff3 -L ours -L base -L theirs`, then the hint on the first closing marker (`conflict::teach_on_marker`) | filter |
| Z6 diffy plus hint | `diffy` 0.5.2 diff3, then the hint | filter |
| N1 always one box | one whole-file box with the frame cut and the hint, exit 1 | **net** per family |
| N2 always status 2 | write nothing, exit 2 | net |
| N3 routing only | status 2 on a NUL in the first 8,192 bytes or non-UTF-8 input, else Z5 | net |
| N4 Z5 forced clean | Z5's text, exit 0 | net |
| V1 v1-style engine | sem-core's own matcher, ours-skeleton placement, diffy inside entities | **calibration only**: real partial work, never netted; expected well below frontier |

Gate item 3 (QA-PLAN.md): after filtering and netting, every stub's reward is 0.000, recorded per
build. The filter keeps a case only if every Z-stub fails it, the original is stable over 3+1 runs,
and the original built against the agent's own crates and features (the oracle, section 6) writes
the same bytes.

## 5. Determinism controls

- One base image digest for the agent, verifier and recording images; `git` installed at one exact
  package version (a snapshot archive pins it); the same Rust toolchain.
- Every case runs outside any repository (`git check-attr weave-set` then fails, which the driver
  reads as "not declared"), with `HOME`, `TMPDIR`, git's config, locale and time zone fixed, and no
  `WEAVE_*`.
- Recording: 3 runs plus 1 perturbed (another `TMPDIR` path length, another working-directory name,
  one CPU through `taskset`, a fresh process each run so Rust's `RandomState` differs). Any case
  whose bytes or status move is dropped; more than 0.5% moving fails the build.
- Upstream already property-tests determinism (law L6, "fresh `RandomState` per call") and orders
  its interstitial answers with a `BTreeSet`; the separator's tie-break was made total for the
  same reason (`v2/render.rs`). The platform recording is still the evidence.

## 6. Oracle and solvability

The oracle is upstream's own `weave-core` and `weave-driver` at the tag, built offline against
exactly the agent's 82 crates and three grammar features, with the smallest source patch needed to
drop `git2`, `rayon` and `memmap2` (`git.rs` and the parallel and mmap paths are off the merge
path). The spike proves that this build writes the same bytes as the installed build on every kept
case; any case where they differ is dropped, so the task is solvable with exactly what the agent is
given. `solution/solve.sh` stages that patched source into `/app/driver` (staged by packaging from
the pinned tag, never committed). Oracle 1.0 twice and nop 0 twice are pre-upload gates.

## 7. Scope cuts and the specification we must write

### Scope cuts (all from the deep dive, plus three from Phase A)

1. Standard markers only, `-l 7`. The annotated markers (`refused_by:` guard names, complexity and
   confidence) and the positional git form are out.
2. No `weave-set`: every case runs outside a repository.
3. No `WEAVE_*` variables; no audit, findings or statistics files.
4. No `weave` CLI, MCP server, CRDT layer, certify or GitHub app.
5. No prose, Markdown, INI, YAML, CSV or changelog rules; only `.py`, `.ts`, `.go`, `.json`,
   `.toml` paths.
6. `diffy` 0.5.2 vendored, and the ladder documented (diffy inside definitions, git's plain merge
   as the container second opinion, git's labelled diff3 as the line route and the gate's
   fallback, diffy's diff3 for box refinement).
7. The matching constants published (0.7, 0.3, 12 tokens, 0.7, document frequency 4, and the
   rehoming overlap 0.6 that the deep dive missed); rename cases kept 0.15 from each.
8. *New:* the specification is written from the `v0.7.1` tag, not from `e52ba82`: two later
   commits change `verify.rs` (TypeScript parameter lists in definition keys; `.qmd` as prose).
   TypeScript overload and decorator cases near that difference are excluded.
9. *New:* inputs up to 2 MB; the 1,000,000-byte route is graded from below only (above it the
   answer is git's, which Z5 reproduces).
10. *New:* `-p` paths are realistic repository paths; the test-file rule of the element union is
    graded with paths such as `pkg/x_test.go`, `tests/test_x.py`, `src/x.test.ts`.

### The specification (agent-visible, about 30 pages, written from the tag's code)

| Ch. | Content | Code it is written from | Pages |
| --- | --- | --- | --- |
| 1 | Command line, files, exit status 0/1/2 (unreadable, not UTF-8, NUL in the first 8 KB), what is written for each | `weave-driver/src/main.rs` | 1.5 |
| 2 | Routing before the entity merge: identical sides, markers in an input, the two one-sided fast paths, the superset side, the size limit, the extension table | `merge.rs` (`compose`, `has_conflict_markers`), `subsumption.rs` | 2 |
| 3 | The entity model: what sem-core 0.29 extracts per language, top-level filtering, identity keys, regions and interstitials, the duplicate-name limit (10), files with no entities | `v2/mod.rs`, `region.rs`, sem-core | 3 |
| 4 | Matching: exact identity, the rename index and its constants, tie-breaks | `v2/match_phase.rs` | 2 |
| 5 | The cell table: each pair of side actions and its disposition | `v2/classify.rs`, `v2/resolve.rs` | 2 |
| 6 | Edits by both sides to one definition: the ladder | `v2/resolve.rs`, `merge.rs` (decorators), `container.rs` | 2.5 |
| 7 | Element union per language, ordering of insertions, the guards, `iota` | `elements.rs` | 2.5 |
| 8 | Imports and the import-region union | `merge.rs` (imports), `binding.rs` | 1.5 |
| 9 | Binding renames to call sites | `v2/bind.rs` | 1 |
| 10 | Placement and ordering | `v2/plan.rs`, `v2/types.rs` | 1.5 |
| 11 | Layout: interstitial merges, gaps, the separator, blank runs, line endings, BOM, final newline | `v2/render.rs`, `layout.rs`, `region.rs` | 2 |
| 12 | The fail-closed checks per language and data format, and what is written when one fails | `verify.rs`, `merge.rs` (`fail_closed`, `keys_hold`, `iota_refusal`) | 4 |
| 13 | Rules that settle a conflicted merge (D0, D1, D3, D4, D6) and when they never apply | `determinate.rs` | 2 |
| 14 | Conflict boxes: markers, the frame cut, refinement, scoped boxes, the hint line | `conflict.rs` | 2 |
| 15 | JSON and TOML | `datafile.rs`, `dataunion.rs` | 1.5 |
| 16 | What the driver also does that the replacement need not (scope) | | 0.5 |

About 31 pages: the spike's fourth check (about 30 pages, accurate) is tight but plausible. Rules
are stated as rules, with one small worked triple per rule where words are ambiguous; examples
never introduce a requirement. Each rule carries a feature id that the inventory (QA-PLAN.md)
maps to cases.

## 8. Expected score bands (untested)

Per family, frontier / mid-tier (the deep dive's guesses): F1 0.85/0.6, F2 0.65/0.35, F3
0.55/0.25, F4 0.65/0.4, F5 0.65/0.4, F6 0.45/0.2, F7 0.55/0.3, F8 0.35/0.1, F9 0.45/0.2, F10
0.65/0.4. Weighted: about 0.58 frontier, about 0.33 mid-tier, inside both target bands
(frontier 0.45-0.8, mid-tier 0.15-0.45). Netting does not move these: F8's credit is the share
of refusals an agent gets right while keeping its accept-duals. If layout were not controlled, both
could fall to 0.1-0.2. The mid-tier floor of 0.10 ("risks looking unfair or broken") is the
number to watch in the first trials.

## 9. Effort

| Item | Person-days |
| --- | --- |
| Spike (four checks; SPIKE-PLAN.md) | 3 |
| Reference, oracle patch, images, `git` pin | 2-3 |
| Specification from the tag's code, independent accuracy review | 4-6 |
| Case generator, filters, duals, tagging | 3-5 |
| Mutants, kill matrix, stub zoo, band check | 2-3 |
| Verifier and runner | 1-2 |
| QA lenses and audit rounds | 3-4 |
| **Total (single step)** | **15-22, plus the 3-day spike** (the spike's work is reused) |

A chain (STEPS.md) adds 3-5 (B) or 6-10 (C) person-days, and is adopted only on measured evidence.

## 10. Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Our own specification becomes the documented surface | Every sentence is an audit obligation; errors are unfair cases | Feature ids per rule; inventory diff; an independent accuracy review against the tag; when the build and the text disagree the instruction says the build is right, but every such case is still fixed in the text before upload |
| Undocumented heuristics (rename thresholds, separator ties, box refinement) | Unfair or unexplained failures | Publish constants; 0.15 margin; refinement documented as "diffy's diff3 narrows a box when it shrinks it" with the exact rule |
| Byte dependence on `git` and `diffy` | A different version moves bytes | One base digest, one `git` package, `diffy` 0.5.2 vendored; 3+1 recording |
| Most real merges are stub-solvable (upstream's own replay: 344 wins in 4,971 file merges on the 0.5.3 engine) | Too few cases survive | Synthetic, typed mutation aimed at the discriminating cases; the spike's second check measures the yield |
| The oracle needs a source patch to build with the agent's crates | If it cannot match the installed build, the task is unsolvable as given | Spike check (section 6); drop any case where they differ |
| The deep dive read a later commit than the tag | Spec errors for TypeScript | Write from `527ccb3`; exclusion (scope cut 8) |
| Proximus cannot run a chain | Chains need a flat bundle anyway | A is the flat bundle (STEPS.md) |
| Evaluation awareness from the text | Rejected verdict | Requester voice; the README's "benchmark" pages never ship; cue sweep over the binary's `--help` too (QA-PLAN.md) |
| Provenance: a small, visibly AI-assisted project, self-reported numbers, private endorsements | Reviewers question why these heuristics deserve reproduction | Frame the task around the gate (a safety property with a real incident) and post-cutoff behaviour; no claim rests on the endorsements |
| Exposure decay | 0.7.0's source is on crates.io and docs.rs since 2026-10-30 | Re-cut per model generation; tag cases by feature so recall shows up as a jump |
| Owner preferences unknown | Vendoring a second Ataraxy crate (`sem-core`); input corpora licences | Ask with the spike's download list; permissive corpora only (SPIKE-PLAN.md) |
