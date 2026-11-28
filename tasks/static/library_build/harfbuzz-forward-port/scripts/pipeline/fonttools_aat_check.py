"""Which AAT tables the agent image's fontTools can write (fix round 2, the tier rule's fontTools facts).

usage (inside the agent image, as any user): python3 -I fonttools_aat_check.py OUT.json FONT...

For every `morx`, `mort`, `kerx`, `kern`, `trak`, `ankr` and `JSTF` table in the given fonts: the fontTools class
that holds it, whether the table is structured (fields a font author can set) or raw bytes, the `kern` subtable
formats and coverage bytes, and whether the table survives the round trip an author would use: the table written
to TTX XML, read back into a copy of the font without it, compiled, and compared with the original bytes. The fonts
are data: shipped test fonts of the 14.3.0 tree and synthetic fonts of our own; nothing in them is executed.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import fontTools
from fontTools.ttLib import TTFont, getTableClass
from fontTools.ttLib.tables.DefaultTable import DefaultTable

TAGS = ("morx", "mort", "kerx", "kern", "trak", "ankr", "JSTF")


def check(path: Path, tag: str) -> dict:
    font = TTFont(path, lazy=False)
    original = font.reader[tag]
    table = font[tag]
    row: dict = {
        "font": path.name,
        "tag": tag,
        "class": type(table).__name__,
        "structured": not (
            type(table) is DefaultTable or type(table).__name__ == "DefaultTable"
        ),
        "registered_class": getTableClass(tag).__name__,
    }
    if tag == "kern":
        row["kern_subtables"] = [
            {
                "format": getattr(st, "format", None),
                "class": type(st).__name__,
                "coverage": getattr(st, "coverage", None),
                "apple": getattr(st, "apple", None),
                "raw": type(st).__name__.startswith("KernTable_format_unk"),
            }
            for st in getattr(table, "kernTables", [])
        ]
    if tag in ("morx", "mort"):
        chains = getattr(getattr(table, "table", None), "MorphChain", []) or []
        row["morph_types"] = sorted(
            {
                getattr(st, "MorphType", None)
                for chain in chains
                for st in (chain.MorphSubtable or [])
            }
            - {None}
        )
    try:
        xml = io.StringIO()
        font.saveXML(xml, tables=[tag])
        fresh = TTFont(path, lazy=False)
        del fresh[tag]
        fresh.importXML(io.StringIO(xml.getvalue()))
        compiled = fresh[tag].compile(fresh)
        row["xml_round_trip"] = (
            "equal"
            if compiled == original
            else f"differs ({len(compiled)} vs {len(original)} bytes)"
        )
    except Exception as exc:  # noqa: BLE001 - report every failure, whatever it is
        row["xml_round_trip"] = f"failed: {type(exc).__name__}: {str(exc)[:160]}"
    return row


def main() -> None:
    out, fonts = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    rows = []
    for path in fonts:
        try:
            tags = set(TTFont(path, lazy=True).keys())
        except Exception as exc:  # noqa: BLE001 - a font fontTools cannot read is a finding too
            rows.append(
                {"font": path.name, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
            )
            continue
        for tag in TAGS:
            if tag in tags:
                rows.append(check(path, tag))
    summary = {
        "fonttools": fontTools.version,
        "kerx_module": getTableClass("kerx").__name__,
        "rows": rows,
    }
    out.write_text(json.dumps(summary, indent=1))
    by = {}
    for r in rows:
        if "tag" in r:
            key = r["tag"]
            by.setdefault(key, []).append(
                f"{r['font']}: {r['class']}, {'structured' if r['structured'] else 'raw'}, {r['xml_round_trip']}"
            )
    print(
        json.dumps(
            {
                "fonttools": fontTools.version,
                "kerx_module": summary["kerx_module"],
                "by_table": by,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
