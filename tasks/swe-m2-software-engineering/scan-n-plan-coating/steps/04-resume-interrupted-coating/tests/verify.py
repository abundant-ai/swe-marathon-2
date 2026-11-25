"""Run the cumulative coating verifier for this checkpoint."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_process import main

if __name__ == "__main__":
    main()
