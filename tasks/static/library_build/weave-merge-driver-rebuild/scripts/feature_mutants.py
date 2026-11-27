"""Feature-removal mutants of the weave merge driver at tag v0.7.1 (527ccb37a951).

Each mutant is a minimal patch to the tag's source that switches off one instruction-level
feature of FEATURES-DRAFT.md or, where switching off the whole feature would move every case,
one named sub-feature of it. Build the mutant and run the cases: the cases whose status or
output bytes change are the ones that grade that feature.

A patch is (path relative to the source root, old, new). Each `old` must occur exactly once in
its file, and the patches of one mutant apply in order. New early returns are written as
`if true { return ...; }`, so the rest of the function stays reachable and type-checks and
borrow-checks as before. The three mutants carried over from patch_mutants.py (gate, elem,
place) make the same edits as that script, byte for byte.

Usage:
  python3 -I feature_mutants.py SRC_ROOT             check every patch against the tree (reads only)
  python3 -I feature_mutants.py SRC_ROOT NAME        patch SRC_ROOT in place, as patch_mutants.py does
  python3 -I feature_mutants.py SRC_ROOT NAME DEST   copy SRC_ROOT to DEST, then patch the copy
Import: apply_mutant(src_dir, name) patches in place; apply_to_copy(src_dir, name, dest) copies first.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

Patch = tuple[str, str, str]

CORE = "crates/weave-core/src"
DRIVER = "crates/weave-driver/src/main.rs"
BIND = f"{CORE}/v2/bind.rs"
CONFLICT = f"{CORE}/conflict.rs"
CONTAINER = f"{CORE}/container.rs"
DATAUNION = f"{CORE}/dataunion.rs"
ELEMENTS = f"{CORE}/elements.rs"
MATCH = f"{CORE}/v2/match_phase.rs"
MERGE = f"{CORE}/merge.rs"
PLAN = f"{CORE}/v2/plan.rs"
RENDER = f"{CORE}/v2/render.rs"
RESOLVE = f"{CORE}/v2/resolve.rs"
STATEMENT = f"{CORE}/statement.rs"
SUBSUMPTION = f"{CORE}/subsumption.rs"
V2MOD = f"{CORE}/v2/mod.rs"
VERIFY = f"{CORE}/verify.rs"

# The instruction-level features of FEATURES-DRAFT.md; `check` reports any without a mutant.
FEATURES = (
    "FT-CLI",
    "FT-BINARY",
    "FT-MARKERS",
    "FT-SUPERSET",
    "FT-NODEFS",
    "FT-ENCODING",
    "FT-ENDING",
    "FT-RENAME",
    "FT-NAMES",
    "FT-REHOME",
    "FT-CALLSITES",
    "FT-SAMEDEF",
    "FT-CONTAINER",
    "FT-FOLD",
    "FT-ELEMENTS",
    "FT-IMPORTS",
    "FT-DECORATORS",
    "FT-PLACEMENT",
    "FT-GAPS",
    "FT-GATE",
    "FT-SETTLE",
    "FT-BOXES",
    "FT-DATA",
)


def rows(*lines: str) -> str:
    """Source lines exactly as the file has them, each ended by a newline."""
    return "".join(f"{line}\n" for line in lines)


def early(path: str, signature: str, value: str) -> Patch:
    """Make `if true { return VALUE; }` the first statement after `signature` (ending `{`)."""
    ret = f"return {value};" if value else "return;"
    return (
        path,
        signature,
        signature + rows("    if true {", f"        {ret}", "    }"),
    )


def early_none(path: str, signature: str) -> Patch:
    """patch_mutants.py's edit: `return None;` as the first statement after `signature`."""
    return (path, signature, signature + "    return None;\n")


# patch_mutants.py's `place` edit, unchanged.
PLACE_OLD = "ready.sort_by(|a, b| key_of[a].cmp(key_of[b]));"
PLACE_REST_OLD = "rest.sort_by(|a, b| key_of[a].cmp(key_of[b]));"
OURS_FIRST = (
    "|i: &usize| (triples[*i].side_idx(Side::Ours).is_none(), "
    "triples[*i].side_idx(Side::Ours).or(triples[*i].side_idx(Side::Theirs))"
    ".map(|x| arena.get(x).position).unwrap_or(0))"
)

GATE_RULES = [
    "GATE-3",
    "GATE-4",
    "GATE-5",
    "GATE-MARK",
    "GATE-LINES-1",
    "GATE-LINES-2",
    "GATE-LINES-3",
    "GATE-LINES-4",
    "GATE-DATA-1",
    "GATE-DATA-2",
    "GATE-PARSE",
    "GATE-KEYS",
    "GATE-BIND",
    "GATE-DANGLING",
    "GATE-REVIVED",
    "GATE-IOTA",
    "GATE-12",
]
SETTLE_RULES = [
    "RULE-ENTRY",
    "RULE-NEVER",
    "RULE-LAYOUT",
    "RULE-D4",
    "RULE-D6",
    "RULE-D1X",
    "RULE-DATA",
    "RULE-REGIONS",
    "RULE-D0",
    "RULE-D1",
    "RULE-D3",
    "RULE-DATA-UNION",
    "RULE-D3C",
    "RULE-D6R",
    "RULE-ANSWER",
]

MUTANTS: dict[str, dict] = {
    # ---- carried over from patch_mutants.py --------------------------------------------
    "gate": {
        "feature": "FT-GATE",
        "rules": GATE_RULES,
        "family": "F8",
        "why": "Every fail-closed check passes (verify, structured_data, duplicate_keys and "
        "iota_refusal answer None), so no composed result is refused and the fallback never runs.",
        "patches": [
            early_none(
                VERIFY,
                rows(
                    "pub fn verify(",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    merged: &str,",
                    "    file_path: &str,",
                    "    registry: &ParserRegistry,",
                    "    renames: &[(String, String)],",
                    ") -> Option<Unverified> {",
                ),
            ),
            early_none(
                VERIFY,
                rows(
                    "pub fn structured_data(",
                    "    ours: Option<&str>,",
                    "    theirs: Option<&str>,",
                    "    merged: &str,",
                    "    file_path: &str,",
                    ") -> Option<Unverified> {",
                ),
            ),
            early_none(
                VERIFY,
                rows(
                    "pub fn duplicate_keys(",
                    "    file_path: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    merged: &str,",
                    "    registry: &ParserRegistry,",
                    ") -> Option<Unverified> {",
                ),
            ),
            early_none(
                MERGE,
                rows(
                    "fn iota_refusal(",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    merged: &str,",
                    "    file_path: &str,",
                    "    host: &Host,",
                    ") -> Option<crate::verify::Unverified> {",
                ),
            ),
        ],
    },
    "elem": {
        "feature": "FT-ELEMENTS",
        "rules": [f"ELEM-{n}" for n in range(1, 15)],
        "family": "F6",
        "why": "The element union refuses every collection (elements::union returns None), "
        "which also stops the disjoint form that gaps and definition-less files reach through it.",
        "patches": [
            early_none(
                ELEMENTS,
                rows(
                    "pub(crate) fn union(",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    path: &str,",
                    "    host: &Host,",
                    ") -> Option<String> {",
                ),
            ),
        ],
    },
    "place": {
        "feature": "FT-PLACEMENT",
        "rules": ["PLACE-6", "PLACE-7"],
        "family": "F2",
        "why": "Additions sharing one anchor are ordered OURS' first, in OURS' order, instead of "
        "by the versions' order and then by identity key.",
        "patches": [
            (PLAN, PLACE_OLD, f"ready.sort_by_key({OURS_FIRST});"),
            (PLAN, PLACE_REST_OLD, f"rest.sort_by_key({OURS_FIRST});"),
        ],
    },
    # ---- chapter 1: command line ---------------------------------------------------------
    "cli_hint": {
        "feature": "FT-CLI",
        "rules": ["BOX-7", "CLI-10"],
        "family": "F1",
        "why": "The hint is appended to every closing marker line of width 7, not only to the "
        "first one.",
        "patches": [
            (
                CONFLICT,
                rows("        if !done && is_close {"),
                rows("        if is_close {"),
            ),
        ],
    },
    "cli_nowrite": {
        "feature": "FT-CLI",
        "rules": ["CLI-6", "CLI-7"],
        "family": "F1",
        "why": "OUT receives a copy of OURS before the inputs are read, so a run that ends with "
        "status 2 leaves a file behind instead of writing nothing.",
        "patches": [
            (
                DRIVER,
                rows("    let theirs_path = &positional[2];"),
                rows(
                    "    let theirs_path = &positional[2];",
                    "    if let Some(out) = output_override.as_deref() {",
                    "        let _ = fs::copy(ours_path, out);",
                    "    }",
                ),
            ),
        ],
    },
    "binary": {
        "feature": "FT-BINARY",
        "rules": ["CLI-6", "CLI-7"],
        "family": "F1",
        "why": "Binary inputs are merged instead of refused, and non-UTF-8 inputs are decoded "
        "lossily, so neither ends with status 2.",
        "patches": [
            (
                DRIVER,
                rows(
                    "    if is_binary(&base) || is_binary(&ours) || is_binary(&theirs) {"
                ),
                rows(
                    "    if false && (is_binary(&base) || is_binary(&ours) || is_binary(&theirs)) {"
                ),
            ),
            (
                DRIVER,
                rows(
                    "    fs::read_to_string(path).map_err(|source| Refusal::UnreadableInput {"
                ),
                rows(
                    "    fs::read(path)",
                    "        .map(|bytes| String::from_utf8_lossy(&bytes).into_owned())",
                    "        .map_err(|source| Refusal::UnreadableInput {",
                ),
            ),
        ],
    },
    # ---- chapter 2: routing ------------------------------------------------------------
    "markers": {
        "feature": "FT-MARKERS",
        "rules": ["ROUTE-2"],
        "family": "F1",
        "why": "Inputs that carry conflict markers are merged like any other instead of being "
        "written back as they are with status 1.",
        "patches": [
            (
                MERGE,
                rows(
                    "    if has_conflict_markers(base) || has_conflict_markers(ours)"
                    " || has_conflict_markers(theirs) {"
                ),
                rows(
                    "    if false",
                    "        && (has_conflict_markers(base) || has_conflict_markers(ours)"
                    " || has_conflict_markers(theirs))",
                    "    {",
                ),
            ),
        ],
    },
    "superset": {
        "feature": "FT-SUPERSET",
        "rules": ["ROUTE-4", "ROUTE-7", "ROUTE-8"],
        "family": "F1",
        "why": "No side is ever found to hold the other's edits (subsuming_side answers None), "
        "so such files go to the entity merge instead of being answered with that side's file.",
        "patches": [
            early(
                SUBSUMPTION,
                rows(
                    "pub(crate) fn subsuming_side(",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    separator: Option<&str>,",
                    ") -> Option<Superset> {",
                ),
                "None",
            ),
        ],
    },
    "nodefs": {
        "feature": "FT-NODEFS",
        "rules": ["ROUTE-10", "ELEM-14"],
        "family": "F1",
        "why": "A file without definitions keeps git's conflict: the whole-file union in its "
        "disjoint form is never tried after the line route.",
        "patches": [
            (
                MERGE,
                rows(
                    "    if lines.conflicts.is_empty() {",
                    "        return lines;",
                    "    }",
                ),
                rows(
                    "    if true || lines.conflicts.is_empty() {",
                    "        return lines;",
                    "    }",
                ),
            ),
        ],
    },
    "nodefs_route": {
        "feature": "FT-NODEFS",
        "rules": ["ROUTE-6", "ENT-8"],
        "family": "F1",
        "why": "Files both sides created and files with 10 or more equal names go to the entity "
        "merge instead of the line route.",
        "patches": [
            (
                V2MOD,
                rows(
                    "    if base.trim().is_empty() && !ours.trim().is_empty()"
                    " && !theirs.trim().is_empty() {",
                    "        return Err(Unsupported::BothCreated);",
                ),
                rows(
                    "    if false && base.trim().is_empty() && !ours.trim().is_empty()"
                    " && !theirs.trim().is_empty() {",
                    "        return Err(Unsupported::BothCreated);",
                ),
            ),
            (
                V2MOD,
                rows(
                    "    if crate::merge::has_excessive_duplicates(&base_top, max_duplicates)",
                    "        || crate::merge::has_excessive_duplicates(&ours_top, max_duplicates)",
                    "        || crate::merge::has_excessive_duplicates(&theirs_top, max_duplicates)",
                    "    {",
                ),
                rows(
                    "    if false",
                    "        && (crate::merge::has_excessive_duplicates(&base_top, max_duplicates)",
                    "            || crate::merge::has_excessive_duplicates(&ours_top, max_duplicates)",
                    "            || crate::merge::has_excessive_duplicates(&theirs_top,"
                    " max_duplicates))",
                    "    {",
                ),
            ),
        ],
    },
    # ---- chapter 11: encoding and the end of the file -------------------------------------
    "encoding": {
        "feature": "FT-ENCODING",
        "rules": ["LAY-5"],
        "family": "F1",
        "why": "A byte-order mark and CRLF are no longer removed before the entity merge, so a "
        "one-sided conversion reads as an edit of everything and the restore step doubles them.",
        "patches": [
            early(
                V2MOD,
                rows("pub(crate) fn normalize_encoding(input: &str) -> Cow<'_, str> {"),
                "Cow::Borrowed(input)",
            ),
        ],
    },
    "ending": {
        "feature": "FT-ENDING",
        "rules": ["LAY-6", "LAY-2"],
        "family": "F1",
        "why": "The file ends as its last definition ends: a missing final newline is not "
        "supplied, and gaps left waiting after the last definition are dropped.",
        "patches": [
            (
                RENDER,
                rows(
                    "        push_entity(&mut out, text, sep);",
                    "        first = false;",
                ),
                rows(
                    "        push_entity(&mut out, text, sep);",
                    r"        if position + 1 == emitting.len() && !text.ends_with('\n')"
                    r" && out.ends_with('\n') {",
                    "            out.pop();",
                    "        }",
                    "        first = false;",
                ),
            ),
            (
                RENDER,
                rows("        .filter(|text| !text.trim().is_empty())"),
                rows("        .filter(|_| false)"),
            ),
        ],
    },
    # ---- chapters 4, 5 and 9: matching, both-added, call sites ------------------------------
    "rename": {
        "feature": "FT-RENAME",
        "rules": ["MATCH-2", "MATCH-3", "MATCH-4", "MATCH-5", "MATCH-6", "MATCH-9"],
        "family": "F3",
        "why": "No rename is inferred on either side, so a renamed definition is a deletion "
        "plus an addition.",
        "patches": [
            early(
                MATCH,
                rows(
                    "fn infer_renames(",
                    "    arena: &Arena,",
                    "    base_all: &[Idx],",
                    "    branch_all: &[Idx],",
                    "    reserved: &HashSet<Idx>,",
                    "    base_names: &HashSet<&str>,",
                    "    pairing: &mut HashMap<Idx, (Idx, Link)>,",
                    ") {",
                ),
                "",
            ),
        ],
    },
    "names": {
        "feature": "FT-NAMES",
        "rules": ["MATCH-7", "MATCH-10", "CELL-7", "CELL-8"],
        "family": "F3",
        "why": "Additions both sides made under one identity key are neither withheld from "
        "rename inference nor paired, so each stays a lone addition.",
        "patches": [
            (
                MATCH,
                rows("    if !reserved_ours.is_empty() {"),
                rows("    if false && !reserved_ours.is_empty() {"),
            ),
            (
                MATCH,
                rows(
                    "    let theirs_added_by_key = key_index(&arena, &theirs_pool.remaining());"
                ),
                rows("    let theirs_added_by_key = key_index(&arena, &[]);"),
            ),
        ],
    },
    "rehome": {
        "feature": "FT-REHOME",
        "rules": ["MATCH-8", "BIND-5", "BIND-6", "BIND-7"],
        "family": "F3",
        "why": "The re-home and extraction evidence is ignored, so the moved-twice, "
        "extracted-and-edited and both-extracted rules never act.",
        "patches": [
            (
                BIND,
                rows(
                    "    rehome_duplication(arena, triples, relational, resolved, ctx);",
                    "    extracted_edit_landing(arena, triples, relational, resolved, ctx);",
                    "    contested_extraction(arena, triples, relational, resolved, ctx);",
                ),
                rows(
                    "    rehome_duplication(arena, triples, &[], resolved, ctx);",
                    "    extracted_edit_landing(arena, triples, &[], resolved, ctx);",
                    "    contested_extraction(arena, triples, &[], resolved, ctx);",
                ),
            ),
        ],
    },
    "callsites": {
        "feature": "FT-CALLSITES",
        "rules": ["BIND-1", "BIND-2", "BIND-3", "BIND-4"],
        "family": "F3",
        "why": "Renames are not carried to call sites, and the deleted-but-called, "
        "shadowing and lost-local checks never turn a decision into a conflict.",
        "patches": [
            (
                BIND,
                rows(
                    "    let references_rewritten = rename_repair(arena, triples, resolved);",
                    "    delete_vs_new_caller(arena, triples, cells, resolved, ctx);",
                    "    shadowed_binding(arena, triples, cells, resolved, ctx);",
                    "    local_dangling(arena, triples, resolved, ctx);",
                ),
                rows("    let references_rewritten = 0;", "    let _ = cells;"),
            ),
        ],
    },
    # ---- chapter 6: one definition edited by both sides -------------------------------------
    "samedef": {
        "feature": "FT-SAMEDEF",
        "rules": ["SAME-1", "SAME-2", "SAME-3"],
        "family": "F4",
        "why": "A definition both sides edited skips the diffy text merge and the "
        "whitespace-only shortcut and starts at the decorator rung.",
        "patches": [
            (
                RESOLVE,
                rows(
                    "    if let Some(merged) = crate::merge::diffy_merge(base_rc, ours_rc,"
                    " theirs_rc) {"
                ),
                rows("    if let Some(merged) = None::<String> {"),
            ),
            (
                RESOLVE,
                rows("    if !ctx.indent_sensitive && rename.is_none() {"),
                rows("    if false && !ctx.indent_sensitive && rename.is_none() {"),
            ),
        ],
    },
    "container": {
        "feature": "FT-CONTAINER",
        "rules": ["SAME-5", "SAME-6", "SAME-7", "SAME-8"],
        "family": "F5",
        "why": "Classes and the other container kinds are never merged member by member "
        "(container_merge answers None).",
        "patches": [
            (
                CONTAINER,
                rows("    let b = decompose(base, base_children, base_start_line)?;"),
                rows(
                    "    if true {",
                    "        return None;",
                    "    }",
                    "    let b = decompose(base, base_children, base_start_line)?;",
                ),
            ),
        ],
    },
    "fold": {
        "feature": "FT-FOLD",
        "rules": ["SAME-9", "SAME-10", "SAME-11"],
        "family": "F4",
        "why": "The statement fold never answers, so a definition the earlier rungs refused is "
        "one box over its three texts instead of statement-scoped boxes.",
        "patches": [
            early(
                STATEMENT,
                rows(
                    "pub(crate) fn statement_merge(",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    fmt: &ScopeMarkers<'_>,",
                    ") -> Option<InnerMergeResult> {",
                ),
                "None",
            ),
        ],
    },
    # ---- chapter 8: gaps, imports, decorators -----------------------------------------------
    "imports": {
        "feature": "FT-IMPORTS",
        "rules": ["IMP-2", "IMP-3", "IMP-4", "IMP-5", "IMP-6", "IMP-7", "IMP-8"],
        "family": "F7",
        "why": "A gap both sides changed is always boxed (no whitespace rung, import union, "
        "diffy or disjoint union), and no import is kept for the other side's new uses.",
        "patches": [
            (
                MERGE,
                rows(
                    "                .find(|text| keeps_everything(text) && keeps_additions(text));"
                ),
                rows(
                    "                .find(|text| false && keeps_everything(text)"
                    " && keeps_additions(text));"
                ),
            ),
            (
                V2MOD,
                rows(
                    "    let kept_imports = crate::binding::imports_kept_for_new_uses(base, ours,"
                    " theirs);"
                ),
                rows("    let kept_imports: Vec<String> = Vec::new();"),
            ),
        ],
    },
    "decorators": {
        "feature": "FT-DECORATORS",
        "rules": ["DEC-1"],
        "family": "F7",
        "why": "The decorator merge never answers, in a definition or in a container member.",
        "patches": [
            early(
                MERGE,
                rows(
                    "pub(crate) fn try_decorator_aware_merge(",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    decorators_compose: bool,",
                    ") -> Option<String> {",
                ),
                "None",
            ),
        ],
    },
    # ---- chapters 10 and 11: placement and gaps ----------------------------------------------
    "place_survivors": {
        "feature": "FT-PLACEMENT",
        "rules": ["PLACE-1", "PLACE-2"],
        "family": "F2",
        "why": "A side's reordering of the surviving definitions is never detected, so the "
        "survivors always keep BASE's order.",
        "patches": [
            (
                PLAN,
                rows(
                    "    let ours_moved = ours_seq != restrict(&base_seq, &ours_seq);",
                    "    let theirs_moved = theirs_seq != restrict(&base_seq, &theirs_seq);",
                ),
                rows(
                    "    let ours_moved = false && ours_seq != restrict(&base_seq, &ours_seq);",
                    "    let theirs_moved = false && theirs_seq != restrict(&base_seq,"
                    " &theirs_seq);",
                ),
            ),
        ],
    },
    "gaps": {
        "feature": "FT-GAPS",
        "rules": ["LAY-3", "LAY-4"],
        "family": "F2",
        "why": "Blank gaps that lead one definition are concatenated instead of joined into the "
        "tallest, and no separator is written where no gap leads a definition.",
        "patches": [
            (
                RENDER,
                rows(
                    "        if text.trim().is_empty() {",
                    "            if blank.is_none() || width(text) > width(blank.unwrap()) {",
                ),
                rows(
                    "        if false && text.trim().is_empty() {",
                    "            if blank.is_none() || width(text) > width(blank.unwrap()) {",
                ),
            ),
            (
                RENDER,
                rows(
                    "            if !first {",
                    "                out.push_str(&interstitials.separator);",
                    "            }",
                ),
                rows(
                    "            if false && !first {",
                    "                out.push_str(&interstitials.separator);",
                    "            }",
                ),
            ),
        ],
    },
    # ---- chapter 13: settling rules --------------------------------------------------------
    "settle": {
        "feature": "FT-SETTLE",
        "rules": SETTLE_RULES,
        "family": "F9",
        "why": "No conflicted result is offered to the settling rules; merge::settle returns "
        "the conflict as it came.",
        "patches": [
            early(
                MERGE,
                rows(
                    "fn settle(",
                    "    conflicted: MergeResult,",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    file_path: &str,",
                    "    registry: &ParserRegistry,",
                    "    host: &Host,",
                    ") -> MergeResult {",
                ),
                "conflicted",
            ),
        ],
    },
    # ---- chapter 14: conflict boxes (one mutant per sub-feature) -----------------------------
    "boxes_frame": {
        "feature": "FT-BOXES",
        "rules": ["BOX-3"],
        "family": "F3",
        "why": "No frame is cut: lines every section shares at its start or end stay inside "
        "the box.",
        "patches": [
            (
                CONFLICT,
                rows("        if present.len() < 2 {"),
                rows("        if true || present.len() < 2 {"),
            ),
        ],
    },
    "boxes_refine": {
        "feature": "FT-BOXES",
        "rules": ["BOX-4"],
        "family": "F8",
        "why": "No box is ever split into narrower boxes by the line-level three-way merge.",
        "patches": [
            early(
                CONFLICT,
                rows(
                    "pub(crate) fn refine_box(",
                    "    base: &str,",
                    "    ours: &str,",
                    "    theirs: &str,",
                    "    fmt: &MarkerFormat,",
                    "    header: &str,",
                    "    footer: &str,",
                    ") -> Option<String> {",
                ),
                "None",
            ),
        ],
    },
    "boxes_coalesce": {
        "feature": "FT-BOXES",
        "rules": ["BOX-5"],
        "family": "F4",
        "why": "Boxes at most 6 lines apart in an entity-merge output stay separate boxes.",
        "patches": [
            early(
                CONFLICT,
                rows(
                    "pub(crate) fn coalesce_adjacent_boxes(content: &str, fmt: &MarkerFormat)"
                    " -> String {"
                ),
                "content.to_string()",
            ),
        ],
    },
    # ---- chapter 15: JSON and TOML (one mutant per sub-feature) ------------------------------
    "data": {
        "feature": "FT-DATA",
        "rules": [
            "DATA-3",
            "DATA-4",
            "DATA-5",
            "DATA-6",
            "RULE-DATA",
            "RULE-DATA-UNION",
        ],
        "family": "F10",
        "why": "The value-carried and key-union rules never apply to JSON or TOML "
        "(dataunion::applies answers false).",
        "patches": [
            (
                DATAUNION,
                rows(
                    "pub(crate) fn applies(path: &str) -> bool {",
                    "    format(path).is_some()",
                    "}",
                ),
                rows(
                    "pub(crate) fn applies(path: &str) -> bool {",
                    "    format(path).is_some() && false",
                    "}",
                ),
            ),
        ],
    },
    "data_sep": {
        "feature": "FT-DATA",
        "rules": ["LAY-7"],
        "family": "F10",
        "why": "The JSON member separator is neither stripped when definitions are read nor "
        "put back when they are written.",
        "patches": [
            (
                V2MOD,
                rows("    let separator = entity_separator(file_path);"),
                rows("    let separator: Option<&str> = None;"),
            ),
        ],
    },
}


def read(path: Path) -> str:
    """A source file's text, byte for byte (no newline translation)."""
    return path.read_bytes().decode("utf-8")


def patched_texts(src_dir: str | Path, name: str) -> dict[Path, str]:
    """The mutant's files with every edit applied in memory, in order; stops on a bad `old`."""
    if name not in MUTANTS:
        raise SystemExit(f"unknown mutant {name!r}; known: {', '.join(MUTANTS)}")
    root = Path(src_dir)
    patches = MUTANTS[name]["patches"]
    texts = {root / rel: read(root / rel) for rel, _, _ in patches}
    for i, (rel, old, new) in enumerate(patches, 1):
        path = root / rel
        found = texts[path].count(old)
        if found != 1:
            head = old.splitlines()[0].strip()
            raise SystemExit(
                f"{name} {i}/{len(patches)} {rel}: expected one {head!r}, found {found}"
            )
        texts[path] = texts[path].replace(old, new)
    return texts


def apply_mutant(src_dir: str | Path, name: str) -> list[Path]:
    """Patch the tree at src_dir in place, as patch_mutants.py does; nothing is written on error."""
    root = Path(src_dir)
    texts = patched_texts(root, name)
    for path, text in texts.items():
        path.write_bytes(text.encode("utf-8"))
        print(f"patched {path.relative_to(root)}")
    return list(texts)


def apply_to_copy(src_dir: str | Path, name: str, dest: str | Path) -> Path:
    """Copy the tree at src_dir to dest (which must not exist yet) and patch the copy."""
    patched_texts(src_dir, name)
    target = Path(dest)
    shutil.copytree(Path(src_dir), target, symlinks=True)
    apply_mutant(target, name)
    return target


def check(src_dir: str | Path) -> int:
    """Print one line per patch (occurrences in the tag, then in order); return the failures."""
    root = Path(src_dir)
    failures = 0
    for name, mutant in MUTANTS.items():
        patches = mutant["patches"]
        texts: dict[Path, str] = {}
        for i, (rel, old, new) in enumerate(patches, 1):
            path = root / rel
            where = f"{name} {i}/{len(patches)} {rel}"
            if not path.is_file():
                print(f"FAIL {where}: no such file")
                failures += 1
                continue
            pristine = read(path)
            current = texts.get(path, pristine)
            in_tag, in_order = pristine.count(old), current.count(old)
            ok = in_tag == 1 and in_order == 1 and old != new
            if in_order == 1:
                texts[path] = current.replace(old, new)
            if not ok:
                failures += 1
            head = old.splitlines()[0].strip()
            print(
                f"{'ok  ' if ok else 'FAIL'} {where}: {in_tag} in the tag, "
                f"{in_order} in order | {head}"
            )
    covered = {m["feature"] for m in MUTANTS.values()}
    missing = [f for f in FEATURES if f not in covered]
    print(
        f"{len(MUTANTS)} mutants, {sum(len(m['patches']) for m in MUTANTS.values())} patches, "
        f"{len(FEATURES) - len(missing)}/{len(FEATURES)} features covered"
        + (f"; no mutant for {', '.join(missing)}" if missing else "")
        + f"; {failures} failing"
    )
    return failures + len(missing)


def main() -> None:
    """Check every patch (one argument), or apply one mutant in place or to a copy at DEST."""
    args = sys.argv[1:]
    if len(args) == 1:
        raise SystemExit(1 if check(args[0]) else 0)
    if len(args) == 2:
        apply_mutant(args[0], args[1])
    elif len(args) == 3:
        apply_to_copy(args[0], args[1], args[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
