"""Print each font's copyright, licence and licence URL name records as JSON (spike S1, the font licences).

Runs inside the pipeline image: `/opt/py/bin/python -I /pipe/font_names.py FONT_DIR...`. Development tooling.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fontTools.ttLib import TTFont


def main() -> None:
    out = {}
    for folder in sys.argv[1:]:
        for path in sorted(Path(folder).glob("*.[ot]tf")):
            name = TTFont(str(path), lazy=True)["name"]
            out[path.name] = {
                str(i): (name.getDebugName(i) or "")[:200] for i in (0, 1, 5, 13, 14)
            }
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
