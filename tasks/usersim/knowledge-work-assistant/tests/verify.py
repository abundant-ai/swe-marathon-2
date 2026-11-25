"""Run the first-round verifier from the isolated tests directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.entrypoint import main
from verifier.runner import verify

if __name__ == "__main__":
    raise SystemExit(main(verify))
