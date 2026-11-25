"""The calls the reward counts: none returns a result its unit returns for a documented call (with
the type of a value left out, as a printed result does not show it), and the documented list names
only recorded calls. Runs on the prepared private inputs when present."""

from __future__ import annotations

import collections
import json
import pickle
import sys

import pytest


def test_no_counted_call_returns_a_documented_result_of_its_unit(task_root):
    private = task_root / "steps" / "01-restore-bodies" / "tests" / "private"
    paths = [private / "vectors" / name for name in ("inputs.pkl", "gold.json", "documented.json")]
    if not all(path.is_file() for path in paths):
        pytest.skip("prepared private inputs are not present")
    sys.path.insert(0, str(task_root / "steps" / "01-restore-bodies" / "tests" / "verifier" / "lib"))
    from canon import same_loose

    with open(paths[0], "rb") as f:
        payload = pickle.load(f)  # noqa: S301 - the task's own build output
    gold = json.loads(paths[1].read_text())
    documented = set(json.loads(paths[2].read_text())["calls"])
    assert documented <= set(gold), "the documented list names calls that are not recorded"
    calls = collections.defaultdict(list)
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            calls[uid].append(vid)
    assert {vid for vids in calls.values() for vid in vids} == set(gold), "inputs and reference results disagree"
    counted = 0
    for uid, vids in calls.items():
        shown = [gold[v] for v in vids if v in documented]
        for vid in vids:
            if vid in documented:
                continue
            counted += 1
            assert not any(same_loose(gold[vid], result) for result in shown), (uid, vid)
    assert counted > 0
