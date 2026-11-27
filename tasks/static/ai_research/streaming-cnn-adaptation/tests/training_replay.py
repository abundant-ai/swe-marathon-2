"""Rebuild the source CNN from the submitted training program and labeled public captures."""

import contextlib
import os
import shutil
import signal
import stat
import subprocess
import sys

from execution import CandidateFailure, workspace


@contextlib.contextmanager
def rebuilt_checkpoint(script, source, public):
    with workspace(public) as (work, command, env):
        for src, name in (
            (script, "train.py"),
            (source, "source.npz"),
            (public / "core_model.py", "core_model.py"),
        ):
            dest = work / name
            shutil.copyfile(src, dest)
            dest.chmod(0o444)
        # Use the same interpreter, working-directory imports and arguments as the public command.
        # prlimit bounds the training output even if the submitted program never returns.
        cmd = [
            *command,
            "prlimit",
            "--fsize=67108864",
            "--nofile=128",
            "--",
            sys.executable,
            "-B",
            "train.py",
        ]
        with subprocess.Popen(
            cmd,
            cwd=work,
            env=env,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as proc:
            try:
                status = proc.wait(timeout=900)
            except subprocess.TimeoutExpired as exc:
                raise CandidateFailure(
                    "The 900-second source training replay timed out"
                ) from exc
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if status:
                raise CandidateFailure(
                    f"Source training replay exited with status {status}"
                )
        result = work / "trained.npz"
        try:
            meta = result.lstat()
        except FileNotFoundError as exc:
            raise CandidateFailure(
                "Source training replay produced no trained.npz"
            ) from exc
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= 512 * 1024:
            raise CandidateFailure(
                "Source training replay produced an invalid checkpoint file"
            )
        yield result
