"""Verify that a corrupted private scorer cannot produce a numeric candidate result."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile


def check(task):
    tests = task / "tests"
    inventory = json.loads((tests / "fixture-digests.json").read_text())
    private = tests / "private"
    paths = {p.relative_to(private).as_posix(): p for p in private.rglob("*") if p.is_file()}
    assert set(paths) == set(inventory)
    for name, path in paths.items():
        with path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == inventory[name]

    spec = importlib.util.spec_from_file_location("telephone_verifier", tests / "verify.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        verifier.TESTS = root / "tests"
        verifier.PRIVATE = verifier.TESTS / "private"
        verifier.OUTPUT = root / "output"
        verifier.WORK = root / "work"
        verifier.WORK.mkdir()
        verifier.OUTPUT.mkdir()
        for name, source in paths.items():
            dest = verifier.PRIVATE / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(source.resolve())
        (verifier.TESTS / "fixture-digests.json").write_text(json.dumps(inventory))
        for name in ("dense-telephone-parts/telephone_score.py", "dense-telephone-parts/raster.c"):
            changed = verifier.PRIVATE / name
            changed.unlink()
            changed.write_bytes(paths[name].read_bytes() + b"\n")
            (verifier.OUTPUT / "reward.txt").write_text("1")
            try:
                verifier.main()
            except RuntimeError as error:
                assert str(error) == "Wrong trusted fixture " + name
            else:
                raise AssertionError("Corrupted grading input succeeded")
            fault = json.loads((verifier.OUTPUT / "infrastructure.json").read_text())
            assert fault["error_domain"] == "verifier"
            assert not (verifier.OUTPUT / "reward.txt").exists()
            changed.unlink()
            changed.symlink_to(paths[name].resolve())
    return len(paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task",type=Path)
    print(check(parser.parse_args().task), "trusted files verified")
