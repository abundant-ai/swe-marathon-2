"""Launch the workcell verifier from its trusted tests directory."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkpoint import main

if __name__ == "__main__":
    main()
