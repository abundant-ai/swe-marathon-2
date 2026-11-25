"""Write the verifier's table of the language's primitive functions from the documentation.

usage: function_table.py   (BASEDPL_CHECKOUT, as for package_step.py)

tests/verifier/functions.json holds, as {"functions": [...]}, the glyph of every page the
documentation calls a function (bpl_text.function_table). The recording step of the verifier image applies each of
them to the private cases' literals (tests/verifier/derivations.py). Packaging refuses a bundle whose table is not
the one the shipped documentation gives, so run this whenever upstream's documentation changes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpl_text

TASK_ROOT = Path(__file__).resolve().parent.parent
TABLE = TASK_ROOT / "tests" / "verifier" / "functions.json"


def table_text(functions: list[str]) -> str:
    """functions.json's text for a table: one key, the glyphs in the documentation's page order.

    Args:
        functions: bpl_text.function_table's result.

    Returns:
        The file's text, ending in a newline.
    """
    return json.dumps({"functions": functions}, ensure_ascii=False) + "\n"


def main() -> None:
    """Write TABLE from the checkout's documentation and print how many functions it holds."""
    checkout = Path(
        os.environ.get(
            "BASEDPL_CHECKOUT", TASK_ROOT.parents[4] / ".cache-src" / "basedpl"
        )
    )
    functions = bpl_text.function_table(bpl_text.documentation(checkout))
    TABLE.write_text(table_text(functions), encoding="utf-8")
    print(f"{len(functions)} functions written to {TABLE.relative_to(TASK_ROOT)}")


if __name__ == "__main__":
    main()
