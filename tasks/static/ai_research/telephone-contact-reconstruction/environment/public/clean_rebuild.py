"""Run a public source test with a fresh /app/work and /tmp inside an unprivileged PRoot view."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path


def run_clean(
    work,
    input_names,
    *,
    runtime=None,
    extra_binds=(),
    guest_python=None,
    library_path=None,
):
    """Stage only original public observations and the current source; publish a fresh receipt on success."""
    receipt = work / "test_receipt.json"
    receipt.unlink(missing_ok=True)
    source = work / "submission.py"
    if source.stat().st_size > 2 * 1024**2:
        raise ValueError("Source exceeds 2 MiB")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    proot = runtime or shutil.which("proot")
    if not proot:
        raise RuntimeError("The clean public test requires the provided PRoot runtime")
    with tempfile.TemporaryDirectory(prefix="scene-public-test-") as folder:
        root = Path(folder) / "root"
        guest = root / "app/work"
        guest.mkdir(parents=True)
        (root / "tmp").mkdir()
        (root / "output").mkdir()
        (root / "checks").mkdir()
        shutil.copyfile(work / "smoke.py", root / "checks/check.py")
        for name in (*input_names, "submission.py"):
            if Path(name).name != name:
                raise ValueError("Expected a public observation filename")
            src = work / name
            target = guest / name
            shutil.copyfile(src, target)
            target.chmod(0o444)
        binds = [
            (p, p)
            for p in (
                "/usr",
                "/bin",
                "/lib",
                "/lib64",
                "/proc/cpuinfo",
                "/proc/meminfo",
                "/dev/null",
                "/dev/urandom",
                "/dev/zero",
                "/etc/ld.so.cache",
                "/etc/localtime",
            )
            if Path(p).exists()
        ]
        binds.extend(extra_binds)
        cmd = [proot, "-r", str(root), "-w", "/app/work"]
        for outside, inside in binds:
            outer = Path(outside)
            anchor = root / str(inside).lstrip("/")
            anchor.parent.mkdir(parents=True, exist_ok=True)
            if outer.is_dir():
                anchor.mkdir(exist_ok=True)
            else:
                anchor.touch(exist_ok=True)
            cmd.extend(("-b", f"{outer}:{inside}!"))
        python = guest_python or sys.executable
        cmd.extend((python, "-B", "/checks/check.py", "--clean-child"))
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PROOT_NO_SECCOMP": "1",
        }
        if library_path:
            env["PYTHONPATH"] = library_path
        # PRoot's own runtime dependencies may be outside system paths in local research installs.
        if runtime and os.environ.get("LD_LIBRARY_PATH"):
            env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
        process = subprocess.Popen(cmd, env=env, start_new_session=True)
        try:
            code = process.wait(timeout=640)
            if code:
                raise RuntimeError(f"Clean source test exited with code {code}")
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
        result = json.loads((root / "output/receipt.json").read_text())
        if (
            result["source_sha256"] != before
            or hashlib.sha256(source.read_bytes()).hexdigest() != before
        ):
            raise RuntimeError("Source changed during the clean test")
        receipt.write_text(json.dumps(result))
        print("SMOKE_PASS", json.dumps(result["details"]))
