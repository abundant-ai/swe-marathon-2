"""Run one-shot requests against an unprivileged, read-only submission."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import tempfile
from typing import Any

REGISTER_OUTPUT = "result.json"
EXISTING_REPORT = b'{"existing_report":true}\n'
MAX_REPORT_BYTES = 1_048_576


@dataclass(frozen=True)
class Response:
    """Capture the command outcome and regular output file, if present."""

    exit_code: int | None
    output: bytes | None
    detail: str
    original_untouched: bool = False
    replaced: bool = False


def artifact_ready(app: Path) -> bool:
    """Check that the collected application uses regular source files.

    Args:
        app: Collected application directory in the verifier environment.

    Returns:
        Whether the executable and optional module tree can be evaluated.
    """
    entry = app / "coating"
    modules = app / "coating_app"
    if entry.is_symlink() or not entry.is_file():
        return False
    if modules.is_symlink() or (modules.exists() and not modules.is_dir()):
        return False
    return all(not p.is_symlink() and (p.is_dir() or p.is_file()) for p in modules.rglob("*"))


def make_immutable(app: Path) -> None:
    """Restore launch permissions and protect the shared submission between checks.

    Args:
        app: Validated artifact directory. The verifier owns its container.
    """
    entry = app / "coating"
    # Some artifact transports restore individual files without execute bits.
    if not entry.stat().st_mode & 0o111:
        entry.chmod(0o755)
    if os.geteuid() != 0:
        return
    modules = list((app / "coating_app").rglob("*"))
    for path in [app, entry, app / "coating_app", *modules]:
        if not path.exists():
            continue
        os.chown(path, 0, 0)
        mode = stat.S_IMODE(path.stat().st_mode)
        path.chmod(0o755 if path.is_dir() or mode & 0o111 else 0o644)


@contextmanager
def request_directory() -> Iterator[tuple[Path, Path, pwd.struct_passwd | None]]:
    """Create a request with one separate writable directory for the program.

    Yields:
        A traversable request root, a writable response path, and the optional
        restricted account to use in a hosted verifier.
    """
    account = pwd.getpwnam("candidate") if os.geteuid() == 0 else None
    with tempfile.TemporaryDirectory(prefix="coating-request-") as directory:
        root = Path(directory)
        root.chmod(0o711)
        response = root / "response"
        response.mkdir(mode=0o700)
        if account is not None:
            os.chown(response, account.pw_uid, account.pw_gid)
        yield root, response, account


def read_result(path: Path) -> tuple[bytes, int] | None:
    """Read a small regular response by descriptor, without following links.

    Args:
        path: Expected registration result in the candidate response directory.

    Returns:
        The result bytes and inode, or None when the file is absent, unsafe, or too large.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        return None
    except OSError as error:
        if error.errno == errno.ELOOP:
            return None
        raise
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT_BYTES:
            return None
        output = stream.read(MAX_REPORT_BYTES + 1)
        return (output, info.st_ino) if len(output) <= MAX_REPORT_BYTES else None


def call(
    app: Path, command: str, inputs: Mapping[str, Mapping[str, Any]], *, timeout_s: float,
) -> Response:
    """Run a public command that publishes one complete JSON result file.

    Args:
        app: Validated coating application directory.
        command: Published subcommand to exercise.
        inputs: Flag names and trusted JSON inputs exposed to this one process.
        timeout_s: Maximum elapsed time for the command.

    Returns:
        Outcome and output bytes. Unexpected trusted I/O failures propagate
        so that infrastructure errors cannot yield a scored result.
    """
    with request_directory() as (root, response, account):
        arguments = [str(app / "coating"), command]
        for name, record in inputs.items():
            path = root / f"{name}.json"
            path.write_text(json.dumps(record, allow_nan=False), encoding="utf-8")
            path.chmod(0o644)
            arguments.extend((f"--{name}", str(path)))
        result_file = response / REGISTER_OUTPUT
        result_file.write_bytes(EXISTING_REPORT)
        result_file.chmod(0o666)
        arguments.extend(("--output", str(result_file)))
        user = account.pw_uid if account else None
        group = account.pw_gid if account else None
        environment = {
            "PATH": f"{Path(sys.executable).parent}:/usr/local/bin:/usr/bin:/bin",
            "HOME": str(response),
            "TMPDIR": str(response),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
        with result_file.open("rb") as original:
            original_inode = os.fstat(original.fileno()).st_ino
            try:
                process = subprocess.Popen(
                    arguments, cwd=app, user=user, group=group,
                    extra_groups=[] if account else None, env=environment,
                    start_new_session=True, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except OSError as error:
                # Linux reports a bad or missing shebang interpreter at exec time.
                if error.errno not in (errno.ENOENT, errno.ENOEXEC, errno.EACCES):
                    raise
                return Response(None, None, "Executable or declared interpreter could not start.")
            with process:
                try:
                    code = process.wait(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    return Response(None, None, "Coating command timed out.")
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=3)
            original.seek(0)
            untouched = original.read(len(EXISTING_REPORT) + 1) == EXISTING_REPORT
            returned = read_result(result_file)
            if returned is None:
                return Response(code, None, "Coating command did not leave a regular report.")
            output, result_inode = returned
            return Response(
                code, output, f"Coating command exited with status {code}.",
                original_untouched=untouched, replaced=result_inode != original_inode,
            )


def register(
    app: Path, job: Mapping[str, Any], scans: Mapping[str, Any], *, timeout_s: float = 75.0,
) -> Response:
    """Call the registration CLI with one disclosed job and scan batch."""
    return call(app, "register", {"job": job, "scans": scans}, timeout_s=timeout_s)
