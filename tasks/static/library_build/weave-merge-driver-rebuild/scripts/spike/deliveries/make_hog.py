"""Turn a staged copy of the upstream solution into a submission that misbehaves on a few cases.

Usage: python3 -I make_hog.py STAGED_SOURCE_DIR
On a case whose BASE is a multiple of 200 bytes long it hangs. On other residues it first does
something hostile and then merges normally:
- 1: leaves 64 sleeping children;
- 2: prints 64 MB to standard output;
- 3: plants a file in /tmp.
A bounded runner should lose only the hanging cases.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOSTILE = """fn main() {
    {
        let args: Vec<String> = std::env::args().collect();
        let n = args.get(1).and_then(|p| std::fs::metadata(p).ok()).map(|m| m.len()).unwrap_or(1);
        match n % 200 {
            0 => loop {
                std::thread::sleep(std::time::Duration::from_secs(1));
            },
            1 => {
                for _ in 0..64 {
                    let _ = std::process::Command::new("sleep").arg("600").spawn();
                }
            }
            2 => {
                use std::io::Write;
                let block = vec![b'x'; 1 << 20];
                let mut out = std::io::stdout();
                for _ in 0..64 {
                    let _ = out.write_all(&block);
                }
            }
            3 => {
                let _ = std::fs::write("/tmp/planted-by-submission", b"x");
            }
            _ => {}
        }
    }
"""


def main() -> int:
    """Patch weave-driver's main in place."""
    path = Path(sys.argv[1]) / "crates/weave-driver/src/main.rs"
    text = path.read_text(encoding="utf-8")
    if text.count("fn main() {\n") != 1:
        raise SystemExit("main() not found exactly once")
    path.write_text(text.replace("fn main() {\n", HOSTILE, 1), encoding="utf-8")
    print("hostile prologue added to", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
