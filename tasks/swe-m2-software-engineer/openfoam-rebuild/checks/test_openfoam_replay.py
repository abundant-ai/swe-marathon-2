"""Replaying a recorded run with a stand-in program: each check passes only when the program
reproduces that part of the recorded outcome."""
import hashlib
import json

import pytest

from openfoam_verifier import recorded as R
from openfoam_verifier.checks import test_recorded_runs as runs
from openfoam_verifier.contracts import Test as Case

CONTROL = "FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }\nendTime 1;\n"
OUT = "value 1.25\n"
CHECKS = ("exit", "files", "stdout", "stderr", "file out.txt")


def store(files_dir, text):
    data = text.encode()
    h = hashlib.sha256(data).hexdigest()
    (files_dir / h[:2]).mkdir(parents=True, exist_ok=True)
    (files_dir / h[:2] / h).write_bytes(data)
    return h


@pytest.fixture
def dataset(tmp_path):
    """A one-record dataset like the published one: records/*.json and files/<h[:2]>/<h>."""
    files = tmp_path / "files"
    (tmp_path / "records").mkdir()
    record = {"command": {"root": "/tmp/run/cavity", "cwd": ".", "program": "", "args": [],
                          "host": "recorder", "home": "/home/dev"},
              "input": {"system/controlDict": store(files, CONTROL)},
              "output": {"out.txt": store(files, OUT)}, "removed": [], "exit": 0,
              "stdout": "Reading /tmp/run/cavity/system/controlDict\nEnd\n", "stderr": ""}
    return tmp_path, record


def program(tmp_path, body):
    path = tmp_path / "prog.sh"
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(0o755)
    return str(path)


GOOD = 'echo "Reading $PWD/system/controlDict"; echo End; printf "value %s\\n" "${V:-1.25}" > out.txt\n'


def replay(dataset, body, timeout=10.0):
    root, record = dataset
    record = {**record, "command": {**record["command"], "program": program(root, body)}}
    (root / "records" / "r.json").write_text(json.dumps(record))
    test = Case("records/r.json", "src", "prog", CHECKS, (), {}, timeout / runs.SLOWDOWN)
    return runs.replay(test, str(root), str(root / "app"), None, None, str(root))


def failing(result):
    return {name for name, (ok, _) in result.items() if not ok}


def test_faithful_program_passes_every_check(dataset):
    assert failing(replay(dataset, GOOD)) == set()


def test_rounding_in_last_digit_passes(dataset):
    assert failing(replay(dataset, "V=1.26; " + GOOD)) == set()


def test_wrong_value_fails_only_that_file(dataset):
    assert failing(replay(dataset, "V=1.30; " + GOOD)) == {"file out.txt"}


def test_wrong_output_fails_stdout(dataset):
    assert failing(replay(dataset, GOOD.replace("echo End", "echo Finished"))) == {"stdout"}


def test_wrong_exit_code_fails_exit(dataset):
    assert failing(replay(dataset, GOOD + "exit 3\n")) == {"exit"}


def test_extra_file_fails_files(dataset):
    assert failing(replay(dataset, GOOD + "touch extra.txt\n")) == {"files"}


def test_changed_input_fails_files(dataset):
    assert failing(replay(dataset, GOOD + "echo x >> system/controlDict\n")) == {"files"}


def test_missing_output_fails_file_and_files(dataset):
    assert failing(replay(dataset, GOOD + "rm out.txt\n")) == {"files", "file out.txt"}


def test_log_files_are_ignored(dataset):
    assert failing(replay(dataset, GOOD + "echo noise > log.prog\n")) == set()


def test_timeout_fails_every_check(dataset, monkeypatch):
    monkeypatch.setattr(runs, "MIN_SECONDS", 1)   # keeps the test short
    assert failing(replay(dataset, "sleep 5\n" + GOOD, timeout=1.0)) == set(CHECKS)


def test_missing_program_fails(dataset):
    root, record = dataset
    record["command"]["program"] = str(root / "absent")
    (root / "records" / "r.json").write_text(json.dumps(record))
    test = Case("records/r.json", "src", "prog", CHECKS, (), {}, 1.0)
    assert "exit" in failing(runs.replay(test, str(root), str(root / "app"), None, None, str(root)))


def test_time_limit_and_processes():
    assert runs.time_limit(Case("r", "s", "p", (), (), {}, 0.1)) == runs.MIN_SECONDS
    assert runs.time_limit(Case("r", "s", "p", (), (), {}, 2.0)) == 2.0 * runs.SLOWDOWN
    assert R.processes("mpirun", ["-np", "4", "simpleFoam", "-parallel"]) == 4
    assert R.processes("simpleFoam", ["-np", "4"]) == 1
