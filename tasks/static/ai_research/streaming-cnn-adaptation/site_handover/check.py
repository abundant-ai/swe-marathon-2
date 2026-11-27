"""Check the chart intervention, identical object footage and the paired scoring boundary."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def files(root: Path) -> dict:
    """Fingerprint shipped files, normalizing the registry name and excluding the chart."""
    result = {}
    for path in root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        key = path.relative_to(root).as_posix()
        if key == "environment/public/site-handovers.png":
            continue
        data = path.read_bytes()
        if key == "task.toml":
            data = data.replace(root.name.encode(), b"TASK")
        result[key] = hashlib.sha256(data).hexdigest()
    return result


def check(matrix: Path) -> dict:
    """Ensure that deleting or reversing the commissioning image is the sole intervention."""
    correct, swapped, absent = (
        next(matrix.glob(f"*-{arm}")) for arm in ("correct", "swapped", "none")
    )
    manifest = files(correct)
    assert manifest == files(swapped) == files(absent)
    sheet = Path("environment/public/site-handovers.png")
    assert not (absent / sheet).exists()
    with Image.open(correct / sheet) as a, Image.open(swapped / sheet) as b:
        left, right = np.split(np.asarray(a), 2, axis=1)
        np.testing.assert_array_equal(
            np.concatenate((right, left), axis=1), np.asarray(b)
        )
        assert not np.array_equal(left, right)

    tests = correct / "tests"
    sys.path[:0] = [str(tests), str(tests / "public")]
    from crossed_grade import crossed_credit
    from test_stream import visit

    data = tests / "private"
    with np.load(data / "site-handovers.npz", allow_pickle=False) as fixtures:
        protocol = dict(fixtures)
    counts = {"paired_stock_frames": 0, "chart_pairs": 0}
    for world in ("a", "b"):
        rows = []
        for schedule, seed in (("clips", 51429), ("switches", 28371)):
            generators = [np.random.default_rng(seed), np.random.default_rng(seed)]
            labels = [[], []]
            for phase in ("arrival", "middle", "return"):
                members = [
                    visit(
                        data,
                        protocol,
                        world,
                        schedule,
                        phase,
                        (phase == "middle") ^ order,
                        rng,
                    )
                    for order, rng in enumerate(generators)
                ]
                a, b = members
                for key in ("rgb", "ids", "source_indices"):
                    np.testing.assert_array_equal(a[key], b[key])
                np.testing.assert_array_equal(a["probe"][0], b["probe"][0])
                assert a["second"] == b["second"]
                for first, second in zip(a["charts"], b["charts"], strict=True):
                    assert not np.array_equal(first, second)
                    counts["chart_pairs"] += 1
                counts["paired_stock_frames"] += len(a["rgb"])
                for sequence, member in zip(labels, members, strict=True):
                    sequence.extend(member["y"].tolist())
            for order, truth in zip((4201, 7303), labels, strict=True):
                rows.append(
                    {
                        "schedule": schedule,
                        "order": order,
                        "stock_targets": truth,
                        "stock_predictions": truth,
                    }
                )
        results = {"cnn": {"a": rows}}
        assert crossed_credit(results, {"cnn": {"credit": 1.0}})[0] == 1.0
        # An otherwise perfect submission copies the first room's answers only on the second schedule.
        rows[3]["stock_predictions"] = rows[2]["stock_predictions"]
        assert crossed_credit(results, {"cnn": {"credit": 1.0}})[0] == 0.0
    # A full installation pair differs only in the initial image and answers.
    for schedule, seed in (("clips", 51429), ("switches", 28371)):
        assert not np.array_equal(
            protocol[f"renewal_a_{schedule}"], protocol[f"renewal_b_{schedule}"]
        )
        for first in (0, 1):
            rngs = [np.random.default_rng(seed) for _ in (0, 1)]
            for phase in ("arrival", "middle", "return"):
                site = first ^ int(phase == "middle")
                a, b = [
                    visit(data, protocol, w, schedule, phase, site, rng)
                    for w, rng in zip(("a", "b"), rngs, strict=True)
                ]
                for key in ("rgb", "ids", "charts", "source_indices"):
                    np.testing.assert_array_equal(a[key], b[key])
                assert (a["y"] != b["y"]).mean() >= 0.5
                counts["same_post_renewal_frames"] = counts.get(
                    "same_post_renewal_frames", 0
                ) + len(a["rgb"])
    return dict(identical_files=len(manifest), **counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path)
    print(json.dumps(check(parser.parse_args().matrix), indent=2))
