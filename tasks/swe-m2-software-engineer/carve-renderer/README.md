# Carve renderer from the specification

Author notes. Nothing in this file is shipped to the agent or to either image.

The agent gets the normative specification of Carve, a markup language derived from Djot, and the
pages of its documentation site, and writes `/app/rebuild/carve`, a renderer that must turn any
Carve document into exactly the HTML that carve-rs 0.1.14's `carve` command writes. It never sees
carve-rs, any other Carve engine, the executable spec model, the conformance corpus or pack, or a
single rendered example beyond what the specification and the documentation pages themselves
show. This is idea 10 of the owner's sheet, "spec only, no binary": implement a post-cutoff tool
from its docs alone, graded by hidden tests recorded from the real one. A judge panel chose the
target (harbor-lh `ops/swe-marathon-v2/decisions/`).

One step is implemented. See [Remaining work](#remaining-work).

## Pins

| What | Pin |
| --- | --- |
| Specification | markup-carve/carve (MIT), tag `0.1.14`, commit `51c5631541efb60faad51f81ac7dbf881150b757` (2026-11-12) |
| Original | markup-carve/carve-rs (MIT), tag `0.1.14`, commit `0a56283f1e745643bc78cdd6fb11ac7344fb88c7` (2026-11-12); its `tests/spec` submodule pins the spec commit above, and its release notes say it implements the 0.1.14 spec |
| Original's build | the release asset `carve-0.1.14-x86_64-unknown-linux-musl.tar.gz`, sha256 `af082997672a9dc12a36a48a2dc4a72d0541b7418eb6a1c57b57f1068c0fc4ac`; its `carve` binary (static-pie, 16,216,144 bytes) sha256 `05d0898dd1c8918adee5a3b2e5a1ae1b5697acd75c7b692bf4a4ea0e4fae2048` |
| Local build (selection and checks only) | `carve-0.1.14-aarch64-apple-darwin.tar.gz`, sha256 `6787862ceef5241f0967326520d33fbff378d5db45110f2c81294e37c605f9ba`; binary sha256 `10257b84a0eff11cf26455914707cbab1ee049022204a61c06914f654422c591` |
| Spec model and Djot engine (selection and the baseline only) | carve's `scripts/spec/` at the spec commit with ohm-js 17.5.0; djot.js (`@djot/djot`) 0.3.2, the version the spec repository locks |

All pins live in `scripts/carve_text.py`; `package_step.py` and `install.py` refuse any other
archive or binary.

## Development log

### 2026-11-19

- Started from the judge panel's choice for idea 10: Carve, pinned at spec tag 0.1.14, graded
  against carve-rs 0.1.14's release build, HTML rendering only (no includes, importers, lint, AST
  JSON or migration).
- **Upstream.** The spec repository (3,547 commits; first commit "Init." 2026-03-30, renamed to
  Carve 2026-05-13, spec 0.1.0 on 2026-07-14) holds the normative specification as 30 EBNF modules
  plus structured contracts (`resources/spec/`, 1.06 MB; `resources/grammar.ebnf` is their
  byte-for-byte aggregate), the documentation site (69 Markdown pages, 1.1 MB), a conformance
  corpus of 4,631 `.crv`/`.html` pairs, a conformance pack of about 12,000 model-generated mutants,
  and an executable spec model (`scripts/spec/`, 22,000 lines of JavaScript on an Ohm grammar).
  carve-rs is about 199,000 lines of Rust; its parser alone is 67,800 lines and its HTML path
  (parser, renderer, escaping, citations, profiles) about 80,000. The release attaches Linux,
  macOS and Windows builds; no local build was needed.
- **Agreement.** On the 4,631 corpus documents the spec model renders the corpus's own HTML for
  all of them, and carve-rs agrees with the model on 4,626 (5 differ, all in comment runs inside
  list items). The model refused nothing.
- **What the agent sees** (`carve_text.specification`, `carve_text.documentation`): `/app/spec`
  is `resources/spec/` (the modules, `README.md`, the JSON contracts, `plus-ownership.crv`) with
  `resources/normative-clauses.txt` and the licence; `/app/docs` is every `docs/**/*.md` page with
  the licence, leaving out the site's theme and build files (`.vitepress/`, `public/`). Left out on
  purpose: the aggregate grammar (the same bytes as the modules), `resources/carve-core.ohm` and
  `scripts/spec/` (the preamble calls them derived checkers: the executable model), the corpus,
  the pack, and the four example pages the site generates from the corpus (`resources/examples/`,
  about 1,300 source/HTML pairs). The documentation's own pages keep the examples they hold.
- **Cases** (`scripts/make_cases.py`, `documents.py`, `rewrite.py`, `features.py`): 2,142 private
  cases from the private seed. See [Case mix](#case-mix). Every rendering case's answer from the
  macOS build equals the spec model's rendering of it (trimmed, as the spec repository's own pack
  compares); 8 candidates where they differ were dropped. Its sha256 travels with the case, and
  the build's recording on Linux drops any case whose answer differs from it.
- **Verifier** (from the Goose task's round 6, the most re-checked of ours): separate image, root,
  answers recorded in a builder stage that the final image keeps nothing of but three root-only
  JSON files. See [Verification](#verification). New here: the delivery mark of the collect hook
  (from the backoffice task's round 7), read before anything runs.
- **Collect hook** (`environment/prepare-delivery`, root-only in the agent image): ends the agent's
  processes, turns links the platform's copy refuses into ones it keeps (absolute links inside
  `/app/rebuild` become relative; links to files or directories outside become copies; dangling
  links, pipes, sockets and devices go), refuses a delivery over 2 GB or 200,000 entries, and marks
  what it lets through. A check proves a virtual environment with an absolute interpreter link, a
  cargo tree with hard links and a link to an outside directory survive a tar and Python's
  `data`-filter extraction, which is how Harbor 0.25 copies an artifact.
- **Instruction.** A docs team moving its build into an audited environment where only its own
  code may run asks for a renderer written from the published specification; the consumers of the
  exact bytes are a page cache and CDN keyed by the HTML's checksum, a review bot that diffs
  rendered HTML, and an archive that signs published pages. It states carve-rs's command-line
  defaults, `--safe` and `--html`, input decoding, the errors and their exit status, the run
  conditions as behaviour (user, directory, environment, pipes, limits, 2 s, 4 GB, 1 GB and
  100,000 files written, the size cap on `/app/rebuild`), what is out of scope, and gives no
  example, budget or grading.
- **Toolchain.** The instruction promises Python 3.12, Go and Rust with their standard libraries,
  the three languages the requester's audited build allows, from Ubuntu 24.04's archive (python3
  3.12, golang-go 1.22, rustc and cargo 1.75), plus gcc and libc6-dev (rustc links through `cc`)
  and python3-venv. Each fits a renderer: Python for a quick start, Go or Rust for speed on long
  documents. The verifier image installs the same packages, so whatever the agent builds runs
  there.
- **Checks.** 36 task checks (registered in the root `pyproject.toml`) and the repository checks
  pass with Python 3.13; `check_repository.py` passes. Packaged twice to the same hash; Oddish
  preflight passes; graded locally from the bundle (see [Validation](#validation)).
- **Deadline.** The verifier's one deadline is 5,400 s inside a 6,000 s step, so that every one of
  the 2,142 cases can take the whole stated 2 s plus the sweeps between cases; agent and verifier
  together stay under 11.3 hours, inside Oddish's 12-hour attempt.
- **The platform's egress window** (harbor-lh `ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md`,
  found by the BasedPL QA today): Harbor gives the sandbox its public setup egress back when the
  agent's turn ends, before the delivery is collected, so a process the agent leaves behind could
  fetch carve-rs (every GitHub release attaches Linux builds), the `carve-lang` wheels on PyPI or
  the carve-go module into `/app/rebuild`. The judges' conditions for exposed tasks (decision
  2026-11-19, A 2-1) are in this version: the collect hook first records whether four public hosts
  answer (TCP 443, 3 s each) and the agent's live processes with their command lines
  (`/var/lib/delivery/session.json`), then kills them and counts the rounds, and writes a root-owned
  record `.delivery.json` beside the mark: the session record, the kill rounds, and every entry with
  type, size, modification and change times and sha256. `reserve-delivery-room` (setup begin and
  complete) sets aside 64 MiB and 64 inodes the hook gives back, so a full disk still leaves room
  for the record and the mark. The verifier refuses (reward 0, with a note) any delivered file
  whose sha256 is one of 275 published builds (`scripts/upstream_builds.py`: every carve-rs release
  asset's digest, the `carve` binary of each x86-64 Linux archive of all 15 releases, all 26 x86-64
  Linux `carve-lang` wheels and the files in them, all 12 carve-go versions and their `.wasm`), or
  that holds two of 23 strings every such build holds and no renderer written from the
  specification would: carve-rs's own usage lines and messages of its importers, lint and
  round-trip code, absent from the shipped text and from plain Rust builds. Any transformation
  (compression, a rebuild from source) defeats these tripwires, as the judges noted; the record is
  for the audit of every trial. The reference solution delivers the release build with exactly
  those 23 strings overwritten in place by `x` (`install.py --blank`; same length, nothing on the
  HTML path), so it is not refused; the recording uses the build unchanged.
- Not built on Oddish and not run, on the owner's rule.

## Current implementation

| Part | State |
| --- | --- |
| Step `01-implement-renderer` | Implemented: instruction, agent image with the specification and the documentation, collect hook, separate verifier image recording at build, reference solution. |
| Further steps | Not designed. Candidates: the next spec release (0.1.x changes behaviour in patch releases), or a second target (canonical Carve with `fmt`, or Markdown) on the same renderer. |
| The original | carve-rs 0.1.14's static Linux release archive, fetched by `scripts/setup_tools.py` into `experiment/original/` (not in Git) and packaged as released into the verifier's build context and the solution. |
| Hooks | `environment/reserve-delivery-room` (setup begin and complete) and `environment/prepare-delivery` (the one root collect hook), both root-only in the agent image. |
| Published builds | `steps/01-implement-renderer/tests/verifier/upstream_builds.json` from `scripts/upstream_builds.py`: 275 sha256 and 23 strings for the refusal of fetched builds. |
| Private inputs | `steps/01-implement-renderer/tests/private/cases.json`, Git-ignored, from `scripts/make_cases.py` and `experiment/seeds.json`. Answers are recorded when the verifier image is built; `recording.json` beside them describes the recording and appears in `metrics.json`. |
| Oracle | The original itself, installed from its release archive by `solve.sh` (as the agent's user), with the 23 tripwire strings blanked in place. |
| Ratings (`harbor check`) | Not run. |

## Design dimensions

### Novelty

MirrorCode-style rebuilds (Epoch AI and METR; our Goose and BasedPL tasks) let the agent run the
original as often as it likes. Here there is no original to run: the agent has a normative
specification and documentation and nothing executable, and must produce the reference
implementation's exact bytes. That turns the task from black-box probing into reading and
implementing a large, precise, recent specification, the way a second implementation of a
standard is written. SWE-Marathon v1's markup and parser tasks target languages with public test
suites the models know; the markdown-linter rebuild had a binary and examples. The language was
first published in May 2026 and its 0.1.14 specification a week before this task; see
[Recall risk](#recall-risk).

### Verifiability

Standard output and exit status are compared byte for byte with what carve-rs 0.1.14 printed when
the verifier image was built. Every kept rendering case was also rendered identically by Carve's
executable spec model, so each answer has two independent derivations: the Rust engine and the
JavaScript model of the specification. Partial progress is the share of cases that match.

### Realism

Teams that standardize on a markup language do implement it again from its specification (the
CommonMark and Djot ecosystems each have several engines), and environments that admit only
in-house code are common in regulated industries. Byte-exact HTML matters wherever rendered pages
are cached or archived by checksum or reviewed as diffs. The documents are of the kinds such a team
keeps (READMEs, release notes, runbooks, meeting notes, API references, reports), and the edge
cases come from the specification's own conformance material, renamed.

### Difficulty

The renderer must implement PART 0's line-ownership automaton (lazy lines, the `+` attachment,
nesting by content column, tabs, exact-length colon fences), a two-pass inline pairing with
word-boundary guards and braced, combined and editorial forms, attributes with ranked
serialization, smart typography, headings and section wrappers with case-preserving slugs,
references, cross-references with cloned text, footnotes (reference and inline) and numbered
captions, tables with spans, alignment and continuation rows, definition lists, admonitions, line
blocks, comments, raw passthrough and safe mode, input normalization, and PART 10's serialization
down to indentation. The in-scope specification is several hundred KB of dense normative prose;
carve-rs spends about 80,000 lines on it. Upstream's own engines still disagree with the model on
5 of 4,631 corpus documents. Not yet measured with a model; QA passes give estimates.

Floors without an implementation (measured on the private cases, `recording.json` `baselines`):
the command line's answers plus one constant answer per kind 1.12%; the largest share of any one
answer 0.28%; printing one newline 0.23%; printing nothing and exiting 0, 0%. A few lines of code
that wrap each paragraph in `<p>` and escape it pass 1.2%. A stock Djot engine passes 2.88% (see
[Case mix](#case-mix)).

### Initial feasibility

Solved by construction: the original passes every kept case, and so does the spec model, so an
implementation written from the specification alone can pass all of them. For an agent: unknown.

## Case mix

2,142 private cases, by kind and by area (`recording.json` `kinds_kept` and `areas_kept`; the
area of a corpus case is read from its source by `features.area`):

| Kind | Document | Inline | Block | Attributes | Layout | Resolution | Divergence | Edge | CLI | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `document` | 520 | | | | | | | | | 520 |
| `construct` | | 99 | 93 | 105 | 110 | 98 | 95 | | | 600 |
| `snippet` | | 46 | 117 | 66 | 303 | 68 | | | | 600 |
| `composite` | | | 7 | 12 | 130 | 11 | | | | 160 |
| `mutant` | | | | | | | | 240 | | 240 |
| `cli` | | | | | | | | | 22 | 22 |

| Kind | What it asks | Source | Median size |
| --- | --- | --- | --- |
| `document` | whole documents: READMEs, articles, meeting notes, changelogs, API references, recipes, handbooks with an FAQ, quarterly reports, postmortems, course notes, release announcements, journals | `documents.document`, written for this task with seeded content | 42 lines (up to 135) |
| `construct` | one area of the language in a short source: dense inline markup; everyday blocks; attributes on blocks, spans and list markers; layout (nesting by column, `+`, lazy lines, quotes, tabs); resolution (headings and references, footnotes, abbreviations, numbered captions); and one of the 21 places Carve parses differently from Djot, in context | `documents.construct` | 8 lines |
| `snippet` | one edge case of the normative clauses | a conformance-corpus document, renamed | 4 lines |
| `composite` | two to four edge cases in one document | corpus documents joined, renamed | 13 lines |
| `mutant` | an edge case no published example shows | a corpus document after one to three local edits (`rewrite.mutate`), renamed | 4 lines |
| `cli` | the command line's own answers, one case per behaviour: missing file, directory, two files, unknown options, `--`, standard input with and without `-`, `--safe` and `--html` before and after the file, nested paths, empty input, a byte order mark, CRLF, ill-formed UTF-8 in a file and on standard input, NUL, no final newline | `make_cases.cli_cases` | |

Deliveries: 515 cases come on standard input (199 of them with `-`), the rest as a file; 171 use
`--safe` (most of the documents that hold raw HTML) and 87 `--html`.

Rewrites (private seed, `rewrite.py`): every corpus-based case is renamed: each ASCII word in prose
position becomes an unused word of the same length and letter case, consistently, so references,
labels and abbreviations still resolve; container types, fence info strings, attribute keys and
values, entities, schemes, task states, letter and roman markers, `(tm)` forms, backslash words and
file extensions are kept. Of up to three renamings the first whose answer differs from the
unrenamed source's and keeps its element structure is kept (993 cases), else the first whose answer
differs (7); a case with no answer-changing renaming is dropped (57). Nothing the agent can read
becomes a case: no corpus document the shipped specification or documentation shows, or whose
skeleton (letters and digits abstracted) any shipped example has (297 left out), no case of the
public pack or a renamed copy of one, and no source with an include (`{{`); the generator checks
every kept case again and packaging repeats the check on the real files.

Weight toward Djot's divergences: corpus documents are drawn with weights by the divergence
features they show (`features.DIVERGENCE`, from `docs/divergence-from-djot.md`), and one construct
area exists for them. 94.9% of the rendering cases touch at least one divergence feature other
than smart typography; the most common are visual-mnemonic emphasis (43%), heading ids (38%),
mentions and tags (37%), editorial marks (32%), block openers interrupting paragraphs (30%),
content columns (29%), colon fences (26%), semantic spans (19%), captions (17%), the `+` marker
(17%), comments (17%), definition lists (16%), heading references (16%), tables (16%) and typed
containers (14%).

**Stock Djot engine.** djot.js 0.3.2 run on the most obvious rewrite of each source into Djot
(`features.to_djot`: `/i/` to `_i_`, `_u_` to `{+u+}`, `~s~` to `{-s-}`, `=h=` to `{=h=}`, braced
super- and subscripts to bare ones, `. ` items to `1. `, `%%` to `{% %}`, `::`/`:` definitions to
Djot's, a `|=` header row to a row and a separator) passes **2.88%** of the rendering cases
exactly, and 4.72% if layout between tags is forgiven. By area: inline 13.8%, divergence 7.4%,
attributes 5.5%, edge 5.0%, block 3.2%, resolution 2.3%, layout 0.2%, whole documents 0.0%.

## Recall risk

The spec repository dates from March 2026 (as Carve from 2026-05-13), carve-rs's first release from
2026-07-14, and the pinned 0.1.14 from 2026-11-12. Models trained after mid-2026 may have seen the
specification, the documentation, the corpus with its expected HTML, and carve-rs's source. The
mitigations: every case is new (generated documents and constructs) or renamed or mutated under
the private seed, so no answer is one upstream publishes; corpus-based cases keep the structure of
public edge cases, though (`settled` in `recording.json` counts them). Behaviour also moves between
0.1.x patch releases (the changelog records breaking changes in each), so recall of an older
version is not enough. The pre-run QA should probe how much a model recalls without the files.

## Workload

A run is one trial of 9.6 hours (one task row per experiment, no continuation tasks). The
instruction states no time budget.

## Verification

1. The collect hook runs as root in the agent's container when the session ends (above): it
   records egress and the agent's processes, kills them, fixes links, and writes
   `/app/rebuild/.delivered` (`delivered ENTRIES BYTES` with its notes, or `refused`) and the
   record `/app/rebuild/.delivery.json`.
2. `/app/rebuild` arrives as the declared artifact in a fresh verifier container. The verifier
   reserves `.reward.tmp` and `metrics.json` before anything runs (no `reward.txt` exists until
   the real end, so an evaluation cut short is an error, never a 0), and requires 512 MB free in
   `/tmp` and `/logs/verifier`. It reads the delivery: nothing at all, no mark, an unreadable mark,
   or fewer entries or bytes than the mark counts is an evaluation error (the copy failed); a
   refused delivery scores 0 with a note.
3. It picks a uid inside the user namespace's map for submitted code and checks the unprivileged
   run first (no_new_privs from the status file or `prctl`, ids, groups, capabilities, limits, and a
   set-id root copy of `id` that must report that uid); a failure is an evaluation error. It seals
   `/app/rebuild` (root-owned, read-only, no set-id bits, at most 200,002 entries and 2 GiB): a
   submission that cannot be sealed gets reward 0 with a note. Then every delivered file is hashed
   and searched once: a published build of the original, or a file holding two of its strings,
   gets reward 0 with a note. The record goes to `metrics.json` (`delivery_record`), never scored.
4. Before each case it kills that uid's processes, sweeps what it left in every world-writable
   directory and its System V IPC objects, and writes the case's files into a new `/tmp/carve-case`
   with new empty `HOME` and `TMPDIR`. `/app/rebuild/carve` runs there as that uid with
   no_new_privs, the case's arguments and standard input, no network, the stated environment and
   limits, 2 seconds, 4 GB of memory in use, 1 GB and 100,000 files added to the disk, and at most
   1,000,000 bytes of output.
5. A case passes when the exit status and the bytes of standard output equal the recorded ones.
   A case that cannot be set up or started, runs too long, prints too much or passes a limit fails;
   none of that is an evaluation error.
6. One deadline (5,400 s from the start, inside the step's 6,000 s) covers the delivery check,
   sealing, scans, cleanup and cases; it leaves room for every case to take the whole stated 2 s
   plus the sweeps, so only a renderer slower than stated loses cases to it; the cases left count
   as failed. At the end the verifier cleans up, writes the reward into
   its reserved file and renames it to `reward.txt`, then writes `metrics.json` (by kind, by area,
   timings, the recording).

The recording (verifier image build, builder stage): each case runs twice and once perturbed
(another binary path, 4 KB of environment padding, a stack 256 KB smaller, one CPU); it is kept
when all three print the same, it exits 0 or 2 without a panic or signal, each run takes at most
1 s and 0.25 s of CPU, and its answer's sha256 equals the one the generator checked against the
spec model. Then any one answer is capped at 1.5% of the cases, cases whose input holds their
answer are dropped, and cases are dropped until a dispatcher with the command line's answers and
one constant per kind passes at most 5%. More than 2% unsteady, crashed, perturbed or differing
cases, or fewer than 90% kept, fails the build.

### Reward formula

```
reward = cases_passed / cases_kept
```

- Continuous, fixed denominator per image build (the private cases kept by the recording). No
  executable: reward 0.
- An evaluation error (not root, privileges cannot be dropped or the drop does not hold, private
  inputs unreadable, too little disk before grading, the delivery missing or cut short) leaves no
  reward file.
- One step; `multi_step_reward_strategy = "final"`.
- Implementation: `tests/verify.py` and `tests/verifier/runcases.py`; `tests/verifier/recording.py`
  describes the recording for `metrics.json` (cases kept by kind and area, drops by reason, how the
  generator settled them, spec-model agreement, run times, the baselines, the Djot engine's share,
  the divergence share, the build).

## Hackability assessment

Highest unresolved severity: 🟡 YELLOW / UNASSESSED (findings 1, 4, 8, 9, 10, 11, 13). Finding 1 is the
platform's egress window, shared by every task whose original is public.

| # | Attack and impact | Boundary | Evidence | Mitigation | Residual risk | Next validation | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Get carve-rs or another engine and deliver it, or call it: during the turn, or by a process left running into the platform's egress window after it | Agent network; the platform's egress window; agent image | Dockerfile read: no engine, no node, no carve source; Harbor 0.25's restore of setup egress read by the coordinator | `network_mode = "no-network"` during the turn; the hook records egress and live processes and kills them; 275 published builds and 23 of their strings refused by the verifier (check `test_a_fetched_build_of_the_original_is_refused`); the record lists every entry with its change time for the audit | The window stays open until the platform keeps the agent's policy through collection; a transformed or rebuilt engine passes the tripwires; the judges' run policy applies (audit every trial, void exploits, pause on the first) | Read `delivery_record` (egress, processes, latest changes) of every trial; the platform fix | 🟡 YELLOW |
| 2 | Read the recorded answers | Separate verifier image; file modes | Same layout as Goose and BasedPL (their QA 07 passes) | Answers recorded in a builder stage; final image keeps three JSON files under root-only `/tests` (0700); submitted code runs as a mapped uid with no_new_privs | A kernel bug | Keep | 🟢 GREEN / LOW |
| 3 | Copy answers from what is shipped | Case generation and packaging | Checked: leak index of every shipped page (fenced blocks, inline code, one-line `SOURCE -> RESULT` examples, the JSON contracts' sources); 297 corpus documents left out; checked again at packaging | No case is a shipped example or a skeleton copy of one; the generated example pages and the corpus are not shipped | The documentation's own examples teach behaviour by design | Keep | 🟢 GREEN / LOW |
| 4 | Recall upstream's published answers | Rewrites | Every corpus-based case renamed with a changed answer (993 same structure, 7 changed) | Private-seed renaming; new documents and constructs (1,120 of 2,142); mutants | Structure of public edge cases is kept; models trained after mid-2026 may know the language | Pre-run QA recall probe; read `settled` | 🟡 YELLOW |
| 5 | Pass cases with no renderer: constant answers, a command-line table | Case mix and selection | Recording: dispatcher 1.12%, largest answer 0.28%, a paragraph wrapper 1.2% | Answer cap 1.5% and floor 5% enforced at build; `recording.json` measures them | None found | Read `baselines` in the first baseline's `metrics.json` | 🟢 GREEN / LOW |
| 6 | Port a Djot engine | Case mix | Measured: djot.js 2.88% exact, 4.72% layout forgiven | Mix weighted to Carve's divergences (94.9% touch one) | None | Keep | 🟢 GREEN / LOW |
| 7 | Deliver a link to something else, or replace `/app/rebuild` | Agent image modes; collect hook | Checked in the Dockerfile; links rewritten or copied by the hook | `/app` root's and sticky, `/app/rebuild` root's and writable; the hook leaves only relative links inside the delivery | None found | First trial as `dev` | 🟢 GREEN / LOW |
| 8 | Make the copy fail so grading errors (deep paths, sparse or huge files, inode exhaustion, link mazes past the hook's two minutes, a full disk before the mark) | Platform copy | Reasoned from Harbor 0.25's `tar -czf` and `extractall(filter="data")`; the backoffice QA 07f-07g found these | The hook walks by descriptor, refuses over 2 GB or 200,000 entries and marks what it lets through; a missing or short arrival is an evaluation error, never a reward | [HOSTILE-ERROR]: a hostile submission can turn its own 0 into an evaluation error; run policy: one attempt per trial, read every errored trial, score 0 when its files show the submission caused it | Read errored trials | 🟡 YELLOW |
| 9 | An honest delivery refused or cut short (a venv's absolute links, cargo's hard links, links to files outside) | Collect hook; platform copy | Check `test_the_collect_hook_lets_honest_deliveries_through_the_copy` (tar plus `data` filter on such a tree) | Links fixed as the agent's user; copies counted against the limits | Modal's GNU tar on the real platform unmeasured; a delivery over the stated limits is refused | First baselines and trials: read the marks in `metrics.json` notes | 🟡 YELLOW / UNASSESSED |
| 10 | Answers that depend on the machine | Recording | Local: 2,142 of 2,142 steady, none perturbed; the Linux build must reproduce the macOS answer the model agreed with | Two runs and a perturbed one; `differs` dropped; static-pie musl build | The Linux build has not run yet (no Linux here) | Read `dropped_differs` and `dropped_unsteady` in the first recording | 🟡 YELLOW / UNASSESSED |
| 11 | Tamper with the result files, or force an evaluation error from inside a run | Separate verifier; reward placeholder | Goose QA 07e passed on the same code; delivery check added here | Reward reserved and renamed only at the end; bounded reads; one deadline; every per-case exception a failed case | The delivery check is new code | Narrow re-check in the QA round | 🟡 YELLOW / UNASSESSED |
| 12 | Run as root in the verifier through a set-id or capable file | Privilege drop and sealing | Goose QA pass 10 F6; checks here | Sealed root-owned without set-id bits; `setpriv --no-new-privs`; the drop is checked or nothing is graded | A kernel that ignores no_new_privs (the probe then refuses to grade) | First baseline's verifier log | 🟢 GREEN / LOW |
| 13 | Infer an evaluation from the files and text | Instruction and image | Checked: no grading, hidden, budget or session wording; no examples shipped | Requester's voice; the hook is root-only and names no judging | An agent can still guess that pages exist to test it | Read the first trajectories | 🟡 YELLOW / UNASSESSED |
| 14 | A case where carve-rs and the specification disagree | Selection | 8 candidates dropped by the model check; 5 corpus documents known to differ | Only cases the model renders identically are kept | None | Keep | 🟢 GREEN / LOW |
| 15 | Behaviour outside the stated scope graded | Case generation | No source holds an include; options only `--safe`, `--html`, and unknown ones; CLI cases one per stated behaviour | Out-of-scope list in the instruction | None found | QA lens 12 | 🟢 GREEN / LOW |

Licences: the specification, documentation and carve-rs are MIT. The spec's `LICENSE` ships in
`/app/spec` and `/app/docs`, carve-rs's with the reference solution.

## Validation

| Check | Revision | Result |
| --- | --- | --- |
| `checks/` (36 tests) with `ci_checks`, Python 3.13, and `check_repository.py` | working tree, 2026-11-19 | pass |
| Tripwires on the reference | `install.py --blank` on the pinned Linux build | sha256 `353fa8cdaa863fcb8fb55b67aee6eb44c198d04041247a3d783732bbc351cf89` (same size), in no list, none of the 23 strings left; the unchanged build and the macOS build are refused |
| Corpus agreement, spec model against carve-rs (macOS release) | spec `51c5631`, carve-rs 0.1.14 | 4,626 of 4,631 equal; model equals the corpus HTML on all |
| Case generation | cases `8c021e92` (2,142) | 8 dropped as model disagreements, 57 with no answer-changing renaming, 108 shown in the docs, spec or pack |
| Local recording with the macOS release build, through the bundle's recorder | bundle `f738bb170bc6` | 2,142 of 2,142 kept; none slow, unsteady, crashed, differing or perturbed; slowest run 35 ms; kept ids sha256 `23c9858a` |
| Packaging twice | `scripts/package_step.py` | the same hash both times: `f738bb170bc67dcf366708fb815fde774812ea2d0d810aa0a6c39388b838b1d5`, 139 files, 16,957,329 bytes |
| Oddish preflight | bundle `f738bb170bc6` | pass |
| Local grading from the bundle (`scripts/grade_locally.py`, no sandbox) | bundle `f738bb170bc6` | reference (the macOS build blanked as `solve.sh` does, re-signed, as `/app/rebuild/carve`, marked by the bundle's hook, passing the tripwires) 1.0 (2,142/2,142, 25 s); an empty delivery 0.0; a program that prints nothing 0.0 |
| Oddish baselines, QA, `harbor check` | none | not run |

## Build and deliver

```bash
git clone https://github.com/markup-carve/carve ../.cache-src/carve   # beside the repository checkout; read by hash
python scripts/setup_tools.py              # the release builds (sha256-checked) and the spec model with ohm-js and djot.js
python scripts/upstream_builds.py          # published builds (GitHub, PyPI, Go proxy) -> tests/verifier/upstream_builds.json
python scripts/make_cases.py               # private cases from experiment/seeds.json, checked against the model
python scripts/package_step.py             # experiment/dist/bundles/<hash>/...; add --flat for a bundle without steps
python scripts/grade_locally.py <bundle>   # the reference and two no-ops through the bundle's own verifier
```

The seed comes from `experiment/seeds.json`, which `scripts/seeds.py` makes once at random and
which is never committed: anyone with the generator, the pinned checkouts and the seed could
regenerate the hidden cases. `make_cases.py` needs Node 24 for the spec model; nothing in either
image needs it.

## Remaining work

- The 20 QA passes (owner's rule), then the judge panel's go for baselines of the current bundle
  under the task's one experiment: the first Linux recording (read `recording` in the reference
  run's `metrics.json`: `dropped_differs`, unsteady, the baselines), the first run of the collect
  hook and of the delivery check, and the first run of the privilege checks as root. Two oracle
  trials should each score exactly 1.0; a no-op 0.
- A recall probe: ask the models under test about Carve without the files.
- The platform fix for the egress window (keep the agent's network policy through collection, or
  kill the agent's processes before the restore), proved by the canary in
  `ops/swe-marathon-v2/canary/`; until then, the scripted audit of every trial.
- `harbor check` and ratings.
