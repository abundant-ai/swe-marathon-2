# Coverage inventory and kill matrix

Every kept case is tied, through its recipe, to at least one stated rule: yes.

## Features (a mutant moves at least 3 kept cases)

| Feature | Mutant | Family | Kept cases moved | By family |
| --- | --- | --- | --- | --- |
| FT-BINARY | `binary` | F1 | 60 | F1 60 |
| FT-BOXES | `boxes_coalesce` | F4 | 168 | F3 40, F4 120, F9 8 |
| FT-BOXES | `boxes_frame` | F3 | 860 | F3 180, F5 40, F8 600, F9 40 |
| FT-BOXES | `boxes_refine` | F8 | 80 | F3 80 |
| FT-CALLSITES | `callsites` | F3 | 220 | F3 220 |
| FT-CLI | `cli_hint` | F1 | 60 | F4 60 |
| FT-CLI | `cli_nowrite` | F1 | 60 | F1 60 |
| FT-CONTAINER | `container` | F5 | 444 | F5 444 |
| FT-DATA | `data` | F10 | 200 | F10 80, F8 80, F9 40 |
| FT-DATA | `data_sep` | F10 | 60 | F10 40, F9 20 |
| FT-DECORATORS | `decorators` | F7 | 80 | F7 80 |
| FT-ELEMENTS | `elem` | F6 | 504 | F1 120, F4 120, F6 115, F8 109, F9 40 |
| FT-ENCODING | `encoding` | F1 | 32 | F1 32 |
| FT-ENDING | `ending` | F1 | 44 | F1 44 |
| FT-FOLD | `fold` | F4 | 160 | F4 160 |
| FT-GAPS | `gaps` | F2 | 1088 | F1 191, F2 277, F3 529, F4 37, F8 54 |
| FT-GATE | `gate` | F8 | 600 | F8 600 |
| FT-IMPORTS | `imports` | F7 | 112 | F7 41, F8 71 |
| FT-MARKERS | `markers` | F1 | 330 | F1 330 |
| FT-NAMES | `names` | F3 | 240 | F1 60, F3 180 |
| FT-NODEFS | `nodefs` | F1 | 120 | F1 120 |
| FT-NODEFS | `nodefs_route` | F1 | 160 | F1 160 |
| FT-PLACEMENT | `place` | F2 | 260 | F1 23, F2 142, F3 70, F4 25 |
| FT-PLACEMENT | `place_survivors` | F2 | 183 | F1 52, F2 131 |
| FT-REHOME | `rehome` | F3 | 240 | F3 240 |
| FT-RENAME | `rename` | F3 | 362 | F3 302, F9 60 |
| FT-SAMEDEF | `samedef` | F4 | 183 | F4 143, F8 40 |
| FT-SETTLE | `settle` | F9 | 560 | F10 80, F7 40, F8 120, F9 320 |
| FT-SUPERSET | `superset` | F1 | 0 |  |
| FT-SUPERSET | `superset_relaxed` | F1 | not run |  |

Features below 3: FT-SUPERSET.

## Rules of the specification

| Rule | Chapter | Kept cases of recipes naming it | Mutants listing it |
| --- | --- | --- | --- |
| BIND-1 | 09 | 60 | `callsites` |
| BIND-2 | 09 | 120 | `callsites` |
| BIND-3 | 09 | 120 | `callsites` |
| BIND-4 | 09 | 40 | `callsites` |
| BIND-5 | 09 | 120 | `rehome` |
| BIND-6 | 09 | 60 | `rehome` |
| BIND-7 | 09 | 120 | `rehome` |
| BOX-1 | 14 | 0 |  |
| BOX-2 | 14 | 0 |  |
| BOX-3 | 14 | 80 | `boxes_frame` |
| BOX-4 | 14 | 180 | `boxes_refine` |
| BOX-5 | 14 | 120 | `boxes_coalesce` |
| BOX-6 | 14 | 0 |  |
| BOX-7 | 14 | 270 | `cli_hint` |
| CELL-1 | 05 | 0 |  |
| CELL-10 | 05 | 120 |  |
| CELL-11 | 05 | 240 |  |
| CELL-12 | 05 | 240 |  |
| CELL-13 | 05 | 0 |  |
| CELL-14 | 05 | 0 |  |
| CELL-15 | 05 | 0 |  |
| CELL-16 | 05 | 0 |  |
| CELL-17 | 05 | 0 |  |
| CELL-18 | 05 | 0 |  |
| CELL-2 | 05 | 0 |  |
| CELL-3 | 05 | 0 |  |
| CELL-4 | 05 | 0 |  |
| CELL-5 | 05 | 0 |  |
| CELL-6 | 05 | 0 |  |
| CELL-7 | 05 | 180 | `names` |
| CELL-8 | 05 | 240 | `names` |
| CELL-9 | 05 | 321 |  |
| CLI-1 | 01 | 0 |  |
| CLI-10 | 01 | 120 | `cli_hint` |
| CLI-2 | 01 | 0 |  |
| CLI-3 | 01 | 0 |  |
| CLI-4 | 01 | 0 |  |
| CLI-5 | 01 | 0 |  |
| CLI-6 | 01 | 30 | `cli_nowrite`, `binary` |
| CLI-7 | 01 | 60 | `cli_nowrite`, `binary` |
| CLI-8 | 01 | 0 |  |
| CLI-9 | 01 | 0 |  |
| DATA-1 | 15 | 0 |  |
| DATA-2 | 15 | 0 |  |
| DATA-3 | 15 | 40 | `data` |
| DATA-4 | 15 | 40 | `data` |
| DATA-5 | 15 | 60 | `data` |
| DATA-6 | 15 | 220 | `data` |
| DEC-1 | 08 | 160 | `decorators` |
| ELEM-1 | 07 | 315 | `elem` |
| ELEM-10 | 07 | 120 | `elem` |
| ELEM-11 | 07 | 144 | `elem` |
| ELEM-12 | 07 | 0 | `elem` |
| ELEM-13 | 07 | 0 | `elem` |
| ELEM-14 | 07 | 160 | `elem`, `nodefs` |
| ELEM-2 | 07 | 0 | `elem` |
| ELEM-3 | 07 | 195 | `elem` |
| ELEM-4 | 07 | 0 | `elem` |
| ELEM-5 | 07 | 0 | `elem` |
| ELEM-6 | 07 | 240 | `elem` |
| ELEM-7 | 07 | 0 | `elem` |
| ELEM-8 | 07 | 0 | `elem` |
| ELEM-9 | 07 | 0 | `elem` |
| ENT-1 | 03 | 0 |  |
| ENT-2 | 03 | 0 |  |
| ENT-3 | 03 | 0 |  |
| ENT-4 | 03 | 0 |  |
| ENT-5 | 03 | 0 |  |
| ENT-6 | 03 | 0 |  |
| ENT-7 | 03 | 0 |  |
| ENT-8 | 03 | 120 | `nodefs_route` |
| GATE-1 | 12 | 0 |  |
| GATE-12 | 12 | 0 | `gate` |
| GATE-2 | 12 | 0 |  |
| GATE-3 | 12 | 600 | `gate` |
| GATE-4 | 12 | 0 | `gate` |
| GATE-5 | 12 | 600 | `gate` |
| GATE-6 | 12 | 0 |  |
| GATE-BIND | 12 | 240 | `gate` |
| GATE-DANGLING | 12 | 300 | `gate` |
| GATE-DATA-1 | 12 | 0 | `gate` |
| GATE-DATA-2 | 12 | 160 | `gate` |
| GATE-IOTA | 12 | 40 | `gate` |
| GATE-KEYS | 12 | 429 | `gate` |
| GATE-LINES-1 | 12 | 0 | `gate` |
| GATE-LINES-2 | 12 | 0 | `gate` |
| GATE-LINES-3 | 12 | 0 | `gate` |
| GATE-LINES-4 | 12 | 0 | `gate` |
| GATE-MARK | 12 | 120 | `gate` |
| GATE-PARSE | 12 | 0 | `gate` |
| GATE-REVIVED | 12 | 120 | `gate` |
| IMP-1 | 08 | 0 |  |
| IMP-2 | 08 | 160 | `imports` |
| IMP-3 | 08 | 0 | `imports` |
| IMP-4 | 08 | 0 | `imports` |
| IMP-5 | 08 | 120 | `imports` |
| IMP-6 | 08 | 0 | `imports` |
| IMP-7 | 08 | 0 | `imports` |
| IMP-8 | 08 | 120 | `imports` |
| LAY-1 | 11 | 30 |  |
| LAY-2 | 11 | 0 | `ending` |
| LAY-3 | 11 | 0 | `gaps` |
| LAY-4 | 11 | 0 | `gaps` |
| LAY-5 | 11 | 76 | `encoding` |
| LAY-6 | 11 | 76 | `ending` |
| LAY-7 | 11 | 0 | `data_sep` |
| MATCH-1 | 04 | 0 |  |
| MATCH-10 | 04 | 120 | `names` |
| MATCH-2 | 04 | 0 | `rename` |
| MATCH-3 | 04 | 240 | `rename` |
| MATCH-4 | 04 | 0 | `rename` |
| MATCH-5 | 04 | 0 | `rename` |
| MATCH-6 | 04 | 0 | `rename` |
| MATCH-7 | 04 | 120 | `names` |
| MATCH-8 | 04 | 300 | `rehome` |
| MATCH-9 | 04 | 240 | `rename` |
| OUT-1 | 16 | 0 |  |
| OUT-2 | 16 | 0 |  |
| OUT-3 | 16 | 0 |  |
| OUT-4 | 16 | 0 |  |
| OUT-5 | 16 | 0 |  |
| OUT-6 | 16 | 0 |  |
| OUT-7 | 16 | 0 |  |
| OUT-8 | 16 | 0 |  |
| PLACE-1 | 10 | 251 | `place_survivors` |
| PLACE-2 | 10 | 251 | `place_survivors` |
| PLACE-3 | 10 | 240 |  |
| PLACE-4 | 10 | 0 |  |
| PLACE-5 | 10 | 355 |  |
| PLACE-6 | 10 | 346 | `place` |
| PLACE-7 | 10 | 286 | `place` |
| ROUTE-1 | 02 | 0 |  |
| ROUTE-10 | 02 | 160 | `nodefs` |
| ROUTE-2 | 02 | 390 | `markers` |
| ROUTE-3 | 02 | 0 |  |
| ROUTE-4 | 02 | 180 | `superset` |
| ROUTE-5 | 02 | 0 |  |
| ROUTE-6 | 02 | 280 | `nodefs_route` |
| ROUTE-7 | 02 | 180 | `superset`, `superset_relaxed` |
| ROUTE-8 | 02 | 120 | `superset`, `superset_relaxed` |
| ROUTE-9 | 02 | 120 |  |
| RULE-ANSWER | 13 | 0 | `settle` |
| RULE-D0 | 13 | 0 | `settle` |
| RULE-D1 | 13 | 288 | `settle` |
| RULE-D1X | 13 | 0 | `settle` |
| RULE-D3 | 13 | 68 | `settle` |
| RULE-D3C | 13 | 40 | `settle` |
| RULE-D4 | 13 | 0 | `settle` |
| RULE-D6 | 13 | 100 | `settle` |
| RULE-D6R | 13 | 60 | `settle` |
| RULE-DATA | 13 | 0 | `settle`, `data` |
| RULE-DATA-UNION | 13 | 140 | `settle`, `data` |
| RULE-ENTRY | 13 | 0 | `settle` |
| RULE-LAYOUT | 13 | 100 | `settle` |
| RULE-NEVER | 13 | 120 | `settle` |
| RULE-REGIONS | 13 | 60 | `settle` |
| SAME-1 | 06 | 183 | `samedef` |
| SAME-10 | 06 | 60 | `fold` |
| SAME-11 | 06 | 240 | `fold` |
| SAME-2 | 06 | 303 | `samedef` |
| SAME-3 | 06 | 80 | `samedef` |
| SAME-4 | 06 | 0 |  |
| SAME-5 | 06 | 400 | `container` |
| SAME-6 | 06 | 200 | `container` |
| SAME-7 | 06 | 560 | `container` |
| SAME-8 | 06 | 687 | `container` |
| SAME-9 | 06 | 60 | `fold` |

Rules with neither a targeting recipe nor a mutant: 49.

| Why | Rules | Coverage |
| --- | --- | --- |
| every case | CLI-1 CLI-2 CLI-3 CLI-4 CLI-5 CLI-8 ENT-1 ENT-2 ENT-3 ENT-4 ENT-5 ENT-6 ENT-7 MATCH-1 CELL-1 CELL-2 CELL-3 CELL-4 CELL-5 CELL-6 IMP-1 LAY-1 | the invocation, the entity model, identity and the basic cell dispositions have no off state: every case passes through them, and a build that gets one wrong fails broadly |
| every conflict or check | CLI-9 GATE-1 GATE-2 GATE-6 BOX-1 BOX-2 BOX-6 CELL-17 SAME-4 | the order and hand-off of the checks, the scope and line endings of boxes, git's own boxes and the no-loss guard run on every conflicted or checked result (the gate, refinement and settle mutants move them) |
| every rename or data case | CELL-13 CELL-14 CELL-15 CELL-16 CELL-18 DATA-1 DATA-2 PLACE-4 | the rename cells, the names carried to chapter 9, the JSON and TOML readers and the survivor union apply to every rename, data or modify/delete case (the rename, call-site and data mutants move them) |
| fast paths a trivial program reproduces | ROUTE-1 ROUTE-3 | identical sides and one side unchanged give one input back; every such candidate is reproduced by taking one side, so none is kept |
| not behaviour | ROUTE-5 OUT-1 OUT-2 OUT-3 OUT-4 OUT-5 OUT-6 OUT-7 OUT-8 | a stub kept for numbering, and the chapter 16 list of what the replacement need not do |

Unclassified: none.

## Stated restrictions

| Restriction | Failing case or enforcing check |
| --- | --- |
| Called as `BASE OURS THEIRS -o OUT -l 7 -p PATH` | every case uses that form; `-p` decides the file type and the hint's path |
| Status 2 writes nothing | the binary and non-UTF-8 cases (90 kept); mutant `cli_nowrite` |
| Binary means a NUL in the first 8,192 bytes | NUL at 8,001-8,191 (status 2) paired with a NUL after 8,192 (merged); mutant `binary` |
| Input that is not UTF-8 ends with status 2 | the non-UTF-8 cases; mutant `binary` |
| 10 seconds and 4 GB per merge | enforced by the runner (timeout and address-space limit) |
| Build with `cargo build --release --offline` in `/app/driver` | the verifier builds that way, as an unprivileged user, with no network |
| Only the toolchain and the offline registry | the verifier's registry holds the same 64 crates only |
| Must not call the installed build | the verifier image has none; a wrapper around it scores 0 |
| Inputs of at most 100 KB | our promise: the export refuses larger cases (largest kept 9.4 KB) |
| Hint on the first closing marker only | two boxes far apart (60 kept); mutant `cli_hint` |
