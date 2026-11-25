"""Loads the verifier package (steps/01-rebuild-openfoam/tests/verifier) as `openfoam_verifier`.

Another task's checks import a package named `verifier`; one pytest process runs both suites,
so this one is registered under its own name. Its modules import each other relatively.
"""
import importlib.util
import sys
from pathlib import Path

VERIFIER = Path(__file__).resolve().parents[1] / "steps/01-rebuild-openfoam/tests/verifier"

if "openfoam_verifier" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "openfoam_verifier", VERIFIER / "__init__.py", submodule_search_locations=[str(VERIFIER)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["openfoam_verifier"] = module
    spec.loader.exec_module(module)
