"""Exercise the public dtype contract and float32 encoders through four future orders."""

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def check_contract(path):
    spec = importlib.util.spec_from_file_location("installation_contract", path)
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    arrays = [np.zeros(shape) for shape in ((2, 28, 48), (2, 28), (2, 4, 28), (28, 28))]
    for dtype in {np.float16, np.float32, np.float64, np.longdouble}:
        supported = np.dtype(dtype).itemsize in (4, 8)
        for field in range(5):
            outputs = list(arrays)
            rates = np.ones((2, 2, 28))
            if field == 4:
                rates = rates.astype(dtype)
            else:
                outputs[field] = arrays[field].astype(dtype)
            try:
                contract.validate(*arrays, *outputs)
                contract.validate_pace(rates)
            except ValueError:
                assert not supported
            else:
                assert supported


if __name__ == "__main__":
    for path in ("environment/public/contract.py", "tests/contract.py"):
        check_contract(ROOT / path)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--training-runtime",
        type=Path,
        default=ROOT,
        help="Restored task revision whose numerical training loop should be exercised",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(args.training_runtime / "tests/private/precision-pilot"))
    from inspection_eval import BANK, REGISTER, SEEDS, branch_seed, simulate, station

    sequences = 0
    for site, seed in enumerate(SEEDS):
        for target in (0, 1):
            original = [
                station(branch_seed(seed, field))
                for field in (BANK[target, site], REGISTER[target, site])
            ]
            updated = [
                {
                    key: a.astype(np.float32)
                    if key in ("W", "b", "legacy", "bridge")
                    else a
                    for key, a in bank.items()
                }
                for bank in original
            ]
            rates = [np.ones((2, 2, 28), np.float32) for bank in original]
            for rep in (411, 939, 1411):
                run = simulate(site, target, rep, original, updated, rates)
                assert (
                    len(run["revisit_by_phase"]) == 4
                    and np.isfinite(run["initial"]).all()
                )
                sequences += 1
    print(
        f"NumPy {np.__version__}: {sequences} production sequences, {4 * sequences} float32 deployment orders."
    )
