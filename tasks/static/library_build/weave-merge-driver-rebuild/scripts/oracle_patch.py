"""Patch an extracted weave v0.7.1 tree so it builds from the agent's offline registry only.

Usage: python3 -I oracle_patch.py SRC_ROOT
The patch: the workspace holds only weave-core and weave-driver; sem-core gets only the
lang-python, lang-typescript and lang-go features (no git, parallel, mmap or other grammars);
weave-driver drops env_logger, the optional weave-crdt dependency and its `crdt` feature;
development dependencies and benches go. No merge code changes. Each edit must match once.
"""

from __future__ import annotations

import sys
from pathlib import Path

SEM_OLD = 'sem-core = { version = "0.29", default-features = false, features = ["git", "parallel", "grammar-all", "mmap"] }'
SEM_NEW = 'sem-core = { version = "0.29", default-features = false, features = ["lang-python", "lang-typescript", "lang-go"] }'


def replace_once(text: str, old: str, new: str, where: str) -> str:
    """Replace one exact occurrence or stop."""
    if text.count(old) != 1:
        raise SystemExit(f"{where}: expected one occurrence of {old!r}")
    return text.replace(old, new)


def cut_from(text: str, marker: str, where: str) -> str:
    """Drop everything from `marker` to the end of the file."""
    if text.count(marker) != 1:
        raise SystemExit(f"{where}: expected one {marker!r}")
    return text[: text.index(marker)].rstrip() + "\n"


def main() -> None:
    """Apply the patch in place."""
    root = Path(sys.argv[1])
    ws = root / "Cargo.toml"
    text = ws.read_text()
    start, end = text.index("members = ["), text.index("]", text.index("members = ["))
    ws.write_text(
        text[:start]
        + 'members = ["crates/weave-core", "crates/weave-driver"]'
        + text[end + 1 :]
    )

    core = root / "crates/weave-core/Cargo.toml"
    text = replace_once(core.read_text(), SEM_OLD, SEM_NEW, "weave-core")
    core.write_text(cut_from(text, "[dev-dependencies]", "weave-core"))

    drv = root / "crates/weave-driver/Cargo.toml"
    text = replace_once(drv.read_text(), SEM_OLD, SEM_NEW, "weave-driver")
    text = replace_once(
        text,
        'weave-crdt = { path = "../weave-crdt", version = "0.7.1", optional = true }\n',
        "",
        "weave-driver",
    )
    text = replace_once(text, 'env_logger = "0.11"\n', "", "weave-driver")
    text = replace_once(
        text, '[dev-dependencies]\ntempfile = "3"\n', "", "weave-driver"
    )
    text = replace_once(text, '[features]\ncrdt = ["weave-crdt"]\n', "", "weave-driver")
    drv.write_text(text)

    main_rs = root / "crates/weave-driver/src/main.rs"
    main_rs.write_text(
        replace_once(main_rs.read_text(), "    env_logger::init();\n", "", "main.rs")
    )
    print("oracle patch applied")


if __name__ == "__main__":
    main()
