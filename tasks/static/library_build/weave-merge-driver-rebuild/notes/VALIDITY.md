# Weave merge-driver rebuild: are the reasons valid? (Phase A, 2026-11-26)

Every claim that the library-picks report or the Weave deep dive uses to justify this task,
re-checked against primary evidence. Sources: the deep dive's read-only clone of `weave` at
`e52ba82` and of `sem` at `e98c27d` (read, never built or run); GitHub's API (repository, releases,
tags, per-path commits, `compare`); crates.io's API (versions, features, dependencies, sizes); the
Hacker News API; Cursor's blog page text. All read on 2026-11-26. Line counts come from a script
that drops blank lines, `//` lines and `#[cfg(test)] mod` blocks, like the deep dive's.

**Verdicts:** ✅ verified · ✏️ verified with a correction · ❌ invalid · ❔ unverified here.
**Tally:** 43 claims: 21 ✅, 14 ✏️, 1 ❌, 7 ❔.

## 1. Claims

| # | Claim (where used) | Verdict | Primary evidence |
| --- | --- | --- | --- |
| C1 | Weave is an entity-level git merge driver: tree-sitter parsing, merges functions, classes and keys instead of lines (report, deep dive) | ✅ | `weave-core` and `weave-driver` package descriptions; driver `--help` |
| C2 | Licence is MIT OR Apache-2.0, not Apache-2.0 alone (deep dive Q1) | ✅ | every crate's `license = "MIT OR Apache-2.0"`; README "Dual-licensed"; crates.io: `weave-core`, `sem-core` and `diffy` all MIT OR Apache-2.0. GitHub's detector says Apache-2.0 and `docs/llms.txt` says MIT, both wrong |
| C3 | 1,364 stars (report) | ✅ | 1,365 on 2026-11-26; 48 forks, 6 open issues |
| C4 | Dates from 6 February 2026 (report) | ✅ | `created_at` 2026-02-06T18:15:59Z; v0.1.0 released 2026-02-08 |
| C5 | Hacker News front page in March, 188 points (report) | ✏️ | item 47241976, "Weave – A language aware merge algorithm based on entities", posted by the project's author, 188 points, 113 comments, 2026-03-04T01:52Z. Front-page placement is inferred from the points, not recorded by the API |
| C6 | The v2 matching and placement engine landed 12 August (report) | ✅ | first commit of `v2/plan.rs`, `v2/mod.rs`, `v2/match_phase.rs`: 2026-08-12T04:33Z; v0.5.0 released the same day, 15:57Z |
| C7 | The gate, region rules and element union landed 3 October (report) | ✅ | first commit of `verify.rs` and `determinate.rs` 2026-10-03T18:19Z, `elements.rs` 18:22Z |
| C8 | They shipped in 0.6.0 on 19 October (report) | ✅ | v0.6.0 released 2026-10-19T13:24Z (tag `2fd8769`); crates.io `weave-core` 0.6.0 the same day |
| C9 | 0.6.0 reversed 0.4's statement-level composition (report) | ✏️ | CHANGELOG 0.6.0: "the statement fold no longer answers clean, and the token-level expression fold is gone"; `expression.rs` (45,674 bytes at v0.5.4) deleted between v0.5.4 and v0.6.0. Correction: 0.4.0 exists only in the CHANGELOG; it has no GitHub release, no tag and no crates.io version |
| C10 | What models could have seen, v1's "ours-side ordering", now points the wrong way (report) | ✅ | README "How It Works" step 5 and `llms.txt` line 47 still say "preserving ours-side ordering"; `v2/plan.rs`: "Nothing consults 'which side is ours'". The last release before a June 2026 cutoff is v0.3.6 (2026-06-05), before v2 |
| C11 | Cursor's old swarm harness: about 68,000 commits in two hours, over 70,000 merge conflicts (report) | ✏️ | Cursor's text: "The old run produced 68,000 commits in its first two hours" and "accumulated more than 70,000 conflicts before we paused it". The 70,000 are not within the two hours |
| C12 | The gate exists because two agents' `case 3:` insertions "merged clean and broke the build twice in a multi-agent run" (report) | ✏️ | CHANGELOG 0.6.0: "Two features that each added `case 3:` (different bodies) to one Go switch merged clean and broke the build twice in a multi-agent run". "Two features", not "two agents"; the quote itself is exact |
| C13 | No Forge task or public rebuild benchmark contains a merge engine (report) | ✏️ | Forge: 664 tasks; name matches only `implement-diff`, `bsdiff`, `implement-jsonpatcher`, `implement-gitleaks`, `rewrite-gitleaks-rs` and two non-software tasks; no instruction mentions three-way merges, diff3, merge drivers, Mergiraf or semistructured merge. ProgramBench and FrontierSWE lists: ❔ (the deep dive's, not re-fetched) |
| C14 | README, `llms.txt` and the docs site contradict the code on ordering, languages, timeouts, binary handling, rename scoring and licence, so we must write the spec (report) | ✅ | ordering: C10. Languages: README badge 38 and "Vue, Svelte, ERB and Haskell are parsed but deliberately not claimed" against `llms.txt` "23 languages + 5 data formats" listing Vue, Svelte and ERB. Timeouts: `llms.txt` "Configurable: WEAVE_TIMEOUT" and `docs.html` against `merge.rs` "There is no longer a watchdog thread here". Binary: README "binary files ... fall back to Git's line-level merge" against the driver's `BinaryInput` refusal (exit 2). Rename scoring: `llms.txt` "0.95/0.8/0.6 scoring" against the constants (C24). Licence: C2 |
| C15 | With extraction supplied, the merge logic in scope is about 16.5-17k code-only lines (report) | ✅ | `weave-core` 17,266 code-only lines (deep dive 17,267) plus `weave-driver` 488, less `git.rs` 217, `explain.rs` 264, `stats.rs` 126 and `diagnose.rs` 170: 16,977. The exercised core is smaller still once changelog rules (228), stderr-only warnings (`validate.rs`, 198), prose and other languages' branches are left out: about 14.5-16k (estimate) |
| C16 | Nonblank lines 27,765 (core), 56,402 (workspace); 900 test attributes (deep dive) | ✅ | reproduced exactly; 900 counts `#[tokio::test]` too (MCP's 34) |
| C17 | README's "441 tests" badge cannot be reconciled with 900 (deep dive) | ✅ | badge "tests-441_passing"; 900 attributes; the badge is older (inference) |
| C18 | `sem-core` is a separate crate of about 13k code-only extraction lines (deep dive) | ❔ | the lock pins `sem-core` 0.29.0 ✅; the 12,960 and 11,739 counts were taken on `sem` HEAD 0.30.1 and not re-measured for 0.29.0 |
| C19 | 33 `tree-sitter-*` grammar crates plus `ts-parser-perl` in the lock (deep dive) | ✅ | 33 counted, plus `ts-parser-perl` 1.2.1; 411 packages in all |
| C20 | An offline registry can carry `sem-core` 0.29.0 with only the Python, TypeScript and Go grammars and no `weave-*` crate (report) | ✏️ | crates.io: features `lang-python`, `lang-typescript`, `lang-go` exist; `git`, `parallel`, `mmap` are optional (defaults: `git`, `parallel`, `grammar-all`, `mmap`). Lock closure: 82 crates, 14.5 MB. Correction: upstream's own crates need `git`, `parallel` and `mmap`, so the oracle needs a small source patch to build with that set; whether it then writes the same bytes is ❔ until the spike |
| C21 | The code says `diffy` and git "disagree often enough" on bytes (report) | ✅ | `host.rs`: "The two algorithms disagree often enough, on both the clean/conflict verdict and on the exact bytes of merges they both call clean" |
| C22 | Driver contract `weave-driver base ours theirs -o out -l 7 -p path`, exit 0/1/2; positional `%L` keeps enhanced markers, only `-l` gives standard ones (deep dive) | ✏️ | `weave-driver/src/main.rs` lines 81-82, 311-331, 348-353. Additions: non-UTF-8 input also exits 2 (`read_to_string`); binary means a NUL in the first 8,192 bytes of any input; nothing is written on exit 2; `-l abc` silently falls back to enhanced markers |
| C23 | Enhanced markers expose internal guard names; `-l 7` avoids them (report) | ✏️ | `conflict.rs` `to_conflict_markers`: enhanced mode writes a `refused_by:` line and a complexity and confidence label; standard mode writes plain diff3 markers. Correction: standard mode still puts the hint ` · weave: run 'weave explain <path>' ...` on the first closing marker, so `-p` is part of the output |
| C24 | Rename constants 0.7, 0.3, 12, 0.7 and 4 appear only in source (report) | ✏️ | `v2/match_phase.rs` lines 35-59 confirm all five; a sixth, `REHOME_MIN_OVERLAP = 0.6` (line 62), was missed; it must be published too |
| C25 | Only C/C++, ML-family, shell and SQL are order-sensitive; Python, TypeScript and Go are not (deep dive) | ✅ | `v2/types.rs` `EntityOrder::of_path`, a 20-extension list |
| C26 | The separator is the file's most frequent gap, ties to the shorter, then lexicographic, made total against hash order (report) | ✅ | `v2/render.rs` lines 130-166 |
| C27 | Upstream property-tests determinism (L6), side-swap byte identity on disjoint merges (L3b); notes dated 2026-08-29 (deep dive) | ✅ | `tests/laws_merge_NOTES.md` |
| C28 | No clock reads on the merge path (deep dive) | ❔ | not re-checked; the spike's 3+1 recording is the evidence |
| C29 | Upstream releases only glibc builds, no musl (deep dive) | ✅ | `.github/workflows/release.yml`: two Linux gnu, two macOS and one Windows target |
| C30 | Weave beat a plain line merge on only 344 of 4,971 replayed real file merges (report) | ✏️ | README: 344 wins and 86 regressions in 4,971 file merges. Corrections: the 0.5.3 engine on 2026-09-01, before the gate; the "clean line merge" baseline was `diffy`, not `git merge-file`; a win means the line merge conflicted and weave was clean |
| C31 | So most replayed merges are stub-solvable and synthetic generation must do most of the work (report) | ❔ | an inference; the spike's second check measures the yield |
| C32 | The graded behaviour dates from August to October 2026 (report) | ✏️ | v2 2026-08-12, gate 2026-10-03/19, lossless split 2026-10-30. Correction: 0.7.1 changed no merge-path file (`compare v0.7.0...v0.7.1`), so the graded engine is 0.7.0's; crates.io's latest `weave-core` and `weave-driver` are 0.7.0, whose source docs.rs and crates.io have shown since 2026-10-30 |
| C33 | The deep dive describes 0.7.1 (deep dive header) | ✏️ | its clone is `e52ba82`, nine commits after the `v0.7.1` tag (`527ccb3`). Two of them change `verify.rs`: TypeScript parameter lists in definition keys now read up to 60 lines from the name (#231), and `.qmd` counts as prose (#217). The gate can therefore differ between the clone and the release for TypeScript overloads and decorated items. The specification must be written from the tag |
| C34 | The brief's split: "0.6 engine, then 0.7.1's gate and changes" | ❌ | the gate is 0.6.0's (C7, C8). Within scope, 0.6.x to 0.7.1 changes `region.rs` (+79/-40) and `binding.rs` (+29/-13) in 0.7.0 and nothing in 0.7.1. The real boundary is 0.5.4 to 0.6.0 (27 merge-path files, weave-core source 778 KB to 1,131 KB). Fix: put options A, B, C and D to the panel with these facts (`STEPS.md`) |
| C35 | M-gate drops the gate family to about 0-10% while every other family stays at 100% by construction; at 15% weight it lands near 0.86 (report) | ✏️ | valid once the family is defined by the mutant (section 2). Corrections: the patch is four call sites, not one; at weight w the mutant scores exactly 1 - w (0.85 at 15%, 0.80 at 20%); refusals whose fallback is git's own conflict are stub-reproducible and leave the family; an "always one box" stub then needs paired accept-duals |
| C36 | The composition ladder is "`diffy` 0.5, then `git merge-file`" (report) | ✏️ | inside a definition: `diffy` diff3, then a whitespace-only shortcut (not for indentation-sensitive languages), the decorator-aware merge, member-wise container merge (`diffy`, then git's plain merge as second opinion, `container.rs`), the element union (`v2/resolve.rs` `intra_entity`). Git's labelled diff3 is the line route and the gate's fallback; `diffy` is the line route only when git is missing; `diffy`'s diff3 also narrows conflict boxes (`conflict.rs` refinement) |
| C37 | crates.io: `weave-core` first published 2026-03-14, 15 versions; `sem-core` about 112,894 downloads, max 0.30.1 (deep dive) | ✅ | 2026-11-26: `weave-core` 1,632 downloads, 15 versions; `sem-core` 112,923 downloads, max 0.30.1, 61 versions; `sem-core` 0.29.0 published 2026-10-30, 0.28.0 2026-10-19 |
| C38 | 36 releases: v0.1.0 2026-02-08 to v0.7.1 2026-11-02; 26 in February-June, 10 in August-November; none for 0.4.x (deep dive) | ✅ | releases API; no 0.4.x tag either |
| C39 | Root commit 2026-02-06T18:16:44Z; 379 commits on main (deep dive) | ❔ | not re-counted (shallow clone); not load-bearing |
| C40 | The author said two well-known git maintainers reviewed Weave favourably in private emails (deep dive) | ❔ | not re-read; already marked unverified upstream; nothing in the task rests on it |
| C41 | `verify` can be disabled without touching the element union's own refusals (deep dive gap) | ✅ | `elements.rs` has its own guards ("Refusals (each leaves the conflict as it was)") and calls nothing in `verify.rs`; the gate's call sites are listed in section 2 |
| C42 | Execute-only works for a native ELF as in Goose and BasedPL (deep dive) | ❔ | a design claim; the spike's protection probe settles it |
| C43 | Scores: frontier 0.45-0.70, mid-tier 0.15-0.40; cost 15-22 person-days (report) | ❔ | estimates from proxies, not claims of fact; unchanged by Phase A |

**What did not survive:** the brief's step split (C34). **What changed the design:** the gate is
0.6.0's (C34); the specification must come from the tag (C33); the gate family's shape (C35); the
oracle needs a source patch to build with the agent's crates (C20); a sixth constant (C24); the
hint line depends on `-p` (C23). **What remains open:** C18, C28, C31, C42 and the external
benchmark lists in C13, all spike or later items.

## 2. The failure sentence and its proof plan

### The sentence

> A capable agent merges edits to different definitions correctly, but returns clean merges where
> 0.7.1 refuses, because its own composition looks valid line by line: it does not check the
> composed file for a name declared twice, a repeated key or case label, a renumbered `iota`
> constant, a name left unbound, or a file that no longer parses or loads, and does not fall back
> to the one whole-file conflict box 0.7.1 writes when git's line merge is clean but fails the same
> checks.

B is F8, the fail-closed gate, 20% of the reward. This refines the report's sentence (C35); its
content is unchanged.

### Documented: a careful agent can learn the rule

- **Specification**, chapter 12 (DESIGN.md section 7): each check per language and data format,
  with the line arithmetic (`o + t - n` copies when either side added, `min(o, t)` when both only
  deleted; only significant lines count), what counts as a declaration, a binding and a keyed
  element in each language, the `iota` rule, and the fallback (git's labelled diff3; its clean
  answer if that passes the checks; its conflict if it conflicts; otherwise one whole-file box with
  the frame cut and the hint).
- **Instruction**: the landing agents' paragraph says the installed driver refuses merges it
  cannot justify, and that a clean exit there is the failure that matters.
- **Probing**: one command should show it. Both sides add `case 3:` to one Go switch at different
  places: by the code, `diffy` composes the two bodies, the keys check refuses, `git merge-file` is
  clean but fails the same check, and the installed build exits 1 with one whole-file box (a
  prediction from reading `fail_closed`; the spike records the actual bytes). The derivation path
  (doc paragraph, probe command, observed bytes) is written down per check in the spike, before
  upload, as the guide's step 2 requires.

### Plausibly missed, and why

1. **Frequency.** The gate fires only on compositions that are invalid. An agent probing ordinary
   merges never sees it; it has to construct adversarial triples.
2. **Breadth.** Six checks across three languages and two data formats, with per-language import
   reading and references in any position: about 2,000-2,700 code-only lines (`verify.rs` 1,102,
   `binding.rs` 567, part of `v2/bind.rs` 1,025, the `iota` part of `elements.rs`). That is a large
   share of the code for a small share of the merges.
3. **The prior.** git, Mergiraf, semistructured merge and Weave's own pre-cutoff releases all return
   line-disjoint edits clean. Upstream itself shipped clean answers here until 0.6.0 (C9).
4. **The fallback is layered.** git's verdict first, its clean answer kept only if it passes, a box
   otherwise. An agent that refuses but writes the wrong shape still fails the case.

What could falsify it: the instruction names refusals, and frontier agents read specifications
closely. The band check and the post-run labels are there to catch that.

### Provable: M-gate moves only its family

**The mutant.** The tag's source with four call sites forced to pass (lines are at `e52ba82` and
are re-located on the tag): `verify::verify` returns `None`; `iota_refusal` returns `None`;
`verify::duplicate_keys` returns `None` (this disables the `keys_hold` backstop, merge.rs 333-376);
the `structured_data` check in `take_superset` (merge.rs 720-734) is skipped. `elements.rs`'s own
guards, the import-region rule (`region_binds_twice`) and subsumption's `block_restated` stay, since
they belong to F6, F7 and F1. `settle` also calls `verify` (merge.rs 437-455), so a D-rule settlement
the gate refused becomes clean under the mutant.

**Family membership by construction.** A kept case is in F8 exactly when the original and M-gate
disagree on it. Every other family's cases, including settled ones, are cases where they agree, so
M-gate passes 100% of F1-F7, F9 and F10 by definition. F8 then holds:

- *refusals*: the original writes one whole-file box (git's line merge clean but failing a check;
  or the `keys_hold` backstop); M-gate writes its composition, exit 0. Refusals whose fallback is
  git's own conflict are reproduced by stub Z5 and filtered out;
- *accept-duals*, at least as many: the same construction made valid (distinct case labels,
  distinct names, a use whose import survives, an `iota` insertion after the last constant). Both
  the original and M-gate merge them clean; they are F8 cases because they test the gate's
  boundary. An "always one box" stub fails them.

**Signature to show before any model run** (grading guide section 13):

| Check | Pass criterion |
| --- | --- |
| Drop | F8's raw pass rate falls from 1.0 to the duals' share (about 0.5); net `g_F8` falls from 1.0 to 0 |
| Others | every other family at 1.0 (by construction; measured anyway) |
| Band | overall 1 - w_F8 = 0.80, inside 0.6-0.85 |
| Uniqueness | no other mutant (M-place, M-rename, M-fold, M-frame, M-container, M-elem, M-import, M-decor, M-D, M-data, M-layout) moves F8 alone; M-gate moves nothing but F8 |
| Duals | the "always one box" stub nets 0 on F8; M-gate passes every dual |
| Difficulty ordering | on the code-share and rule-count proxies above, F8 ranks hardest per case; F1 and F2 rank easiest |
| Counts | at least 100 refusals and 100 duals after filtering, each check with at least 10 refusals across at least two languages |

**After the first trials.** `metrics.json` labels every failing case by family and feature. The
sentence holds if F8 is the lowest net family in most trials, and if most failed refusals were
written as exit 0 (a clean merge), not as a wrong box. If another family dominates, re-check that
family's specification and cases before touching F8.

### Secondary diagnostic (not headlined)

Placement: agents that follow the README's "ours-side ordering", or v1 and Mergiraf habits, put
concurrent additions in ours-first order instead of by anchor rank, input order and identity key.
M-place (v1's ours skeleton) proves F2's signature. Count "ours-first" outputs after the first
trials as a recall marker.
