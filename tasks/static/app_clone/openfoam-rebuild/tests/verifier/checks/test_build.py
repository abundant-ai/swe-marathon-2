"""compile.sh builds the programs from the submitted source."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from ..contracts import CheckResult, VerificationContext


def test_build(context: VerificationContext) -> CheckResult:
    """Runs compile.sh in the submission folder as the unprivileged user, without network,
    after removing any bin/ it contains; then makes the folder read-only for that user."""
    app = context.app
    script = app / "compile.sh"
    if not script.is_file():
        return CheckResult("build", "failed", "compile.sh not found")
    if (app / "bin").is_symlink():
        (app / "bin").unlink()
    shutil.rmtree(app / "bin", ignore_errors=True)
    _chown_tree(app, context.uid, context.gid)
    home = tempfile.mkdtemp(dir=context.work)
    tmp = tempfile.mkdtemp(dir=context.work)
    for d in (home, tmp):
        os.chown(d, context.uid, context.gid)
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": home,
        "TMPDIR": tmp,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    log = context.output / "build.log"
    with open(log, "wb") as f:
        try:
            p = subprocess.run(
                ["bash", str(script)],
                check=False,
                cwd=app,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=context.build_timeout,
                user=context.uid,
                group=context.gid,
                extra_groups=[],
            )
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = None
    _chown_tree(app, 0, 0)
    # root's, readable by everyone, executable by everyone where the owner could execute it,
    # never set-user-id or set-group-id
    for d, dirs, files in os.walk(app):
        for x in [d, *(os.path.join(d, n) for n in dirs + files)]:
            if not os.path.islink(x):
                mode = os.stat(x).st_mode
                os.chmod(
                    x,
                    mode & 0o1755
                    | 0o444
                    | (0o111 if os.path.isdir(x) or mode & 0o100 else 0),
                )
    bin_dir = app / "bin"
    programs = (
        sorted(
            p.name
            for p in bin_dir.iterdir()
            if p.is_file() and os.stat(p).st_mode & 0o001
        )
        if bin_dir.is_dir() and not bin_dir.is_symlink()
        else []
    )
    if rc is None:
        return CheckResult(
            "build",
            "failed",
            f"compile.sh did not finish in {context.build_timeout:.0f} s",
        )
    if rc != 0:
        return CheckResult(
            "build", "failed", f"compile.sh exited with {rc}; see build.log"
        )
    if not programs:
        return CheckResult("build", "failed", "compile.sh built no executables in bin/")
    return CheckResult(
        "build",
        "passed",
        f"{len(programs)} programs built",
        {"programs_built": float(len(programs))},
    )


def _chown_tree(root, uid, gid):
    for d, dirs, files in os.walk(root):
        os.chown(d, uid, gid, follow_symlinks=False)
        for n in dirs + files:
            os.chown(os.path.join(d, n), uid, gid, follow_symlinks=False)
