"""Launch the ros2-control-recovery verifier from its trusted tests directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkpoint import main

if __name__ == "__main__":
    main()
