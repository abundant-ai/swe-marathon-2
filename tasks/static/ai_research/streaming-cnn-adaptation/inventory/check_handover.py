"""Audit the photographic treatment independently of the grader and commissioning algorithm."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def files(package):
    return {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package.rglob("*") if p.is_file()
    }


def audit(root):
    inventories = {arm:files(next(root.glob("*-"+arm))) for arm in ("correct","swapped","none")}
    common = inventories["correct"]
    optical = {"environment/public/inventory.png","environment/public/preview.png"}
    for arm,snapshot in inventories.items():
        assert {k:v for k,v in snapshot.items() if k not in optical|{"task.toml"}} == {
            k:v for k,v in common.items() if k not in optical|{"task.toml"}}
        assert not any("__pycache__" in k or k.endswith(".pyc") for k in snapshot)
    assert inventories["swapped"]["environment/public/preview.png"] == common["environment/public/preview.png"]
    assert inventories["swapped"]["environment/public/inventory.png"] != common["environment/public/inventory.png"]
    assert optical.isdisjoint(inventories["none"])
    private=next(root.glob("*-correct"))/"tests/private"
    checked=0
    for name in ("arrival","middle","return","probe","middle_probe"):
        with np.load(private/f"a_{name}.npz") as a,np.load(private/f"b_{name}.npz") as b:
            for key in ("x","x_alt","ids"):
                assert np.array_equal(a[key],b[key])
            for key in ("y","y_alt"):
                assert (a[key] != b[key]).all()
                assert np.array_equal(np.sort(a[key]),np.sort(b[key]))
            checked+=len(a["y"])
    return {"identical_camera_records_across_installations":checked,
            "swapped_changes_only_the_stock_photo":True, "absent_has_neither_photo":True}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("packages",type=Path)
    print(json.dumps(audit(parser.parse_args().packages),indent=2))
