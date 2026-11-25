"""Grade checkpoint 2 of the BARN navigation qualification from the trusted tests directory."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grader import main

if __name__ == "__main__":
    main(level=2)
