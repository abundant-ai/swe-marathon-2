"""Prepare calibration observations and crossed stock labels for the shared-scanner study."""

import json

# Physical scanner board responses from the preceding CORe50 capture simulation.
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
from renewal import photograph
from site_photos import cards, exposure, sheet

spec = spec_from_file_location(
    "site_camera", Path(__file__).resolve().parents[1] / "routed/prepare.py"
)
camera = module_from_spec(spec)
spec.loader.exec_module(camera)


def prepare(private: Path, public: Path, arm: str) -> None:
    """Generate identical camera captures for opposite stockroom itineraries, with independent chart photos."""
    rng = np.random.default_rng(7821)
    site_cards = cards(38201)
    if arm != "none":
        sheet(site_cards if arm == "correct" else site_cards[::-1]).save(
            public / "site-handovers.png"
        )
    matrices = np.asarray(camera.RESPONSES["a"])
    payload = {}
    ordering = np.random.default_rng(49821)
    for schedule in ("clips", "switches"):
        new_cards = cards(int(rng.integers(1, 2**31)))
        for world in ("a", "b"):
            assigned = new_cards if world == "a" else new_cards[::-1]
            payload[f"renewal_{world}_{schedule}"] = photograph(
                site_cards, assigned, ordering.permutation(2)
            )
        world = "a"
        for visit, phase in enumerate(("arrival", "middle", "return")):
            first = int(rng.integers(2))
            for interval, mode in enumerate((first, 1 - first)):
                gain = rng.uniform(0.82, 1.10, 3)
                mix = np.diag(gain)
                key = f"{world}_{schedule}_{phase}_{interval}"
                payload[key + "_gain"] = gain
                payload[key + "_mode"] = np.array(mode)
                for site in (0, 1):
                    # Same optics, framing and noise for each member of the site counterfactual.
                    payload[key + f"_site{site}"] = exposure(
                        new_cards[site],
                        mix @ matrices[mode],
                        np.random.default_rng(117 + visit * 3 + interval),
                    )
    np.savez_compressed(private / "site-handovers.npz", **payload)
    (private / "site-protocol.json").write_text(
        json.dumps({"schema": 1, "orders": [4201, 7303], "one_scanner": True}) + "\n"
    )
