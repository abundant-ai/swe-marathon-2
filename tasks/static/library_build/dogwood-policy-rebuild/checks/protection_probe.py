"""Gate 7: from the working machine's own user, try every route to the bytes of the execute-only
1.2.0 build, and fail unless every one is closed.

Run inside the working image as `dev` (python3 -I protection_probe.py; it needs `cc` for the
preload library). Routes, each of which must fail:
- reading or copying the file; opening /proc/<pid>/exe, mem or maps of a running build;
- PTRACE_ATTACH to a running build;
- a self-traced exec (PTRACE_TRACEME, then execve: the kernel then drops the setgid bit, so the
  build runs as `dev` itself) whose memory the tracer reads with PTRACE_PEEKDATA or /proc/<pid>/mem;
- LD_PRELOAD of a library whose constructor copies the process's own memory out, on a normal
  exec and on a self-traced one (the build is linked statically, so no loader ever runs one);
- a core dump of a build killed by SIGSEGV.
Prints one JSON object; exits 1 if any route worked or a check could not run (fail closed).
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time

BUILD = "/usr/local/bin/dogwood"
PTRACE_TRACEME, PTRACE_PEEKDATA, PTRACE_CONT, PTRACE_ATTACH, PTRACE_DETACH = (
    0,
    2,
    7,
    16,
    17,
)
PTRACE_GETREGSET, NT_PRSTATUS = 0x4204, 1
# Where the stack pointer sits in the NT_PRSTATUS register set: user_pt_regs on aarch64,
# user_regs_struct on x86_64. The stack is always mapped, so a read there that fails was refused.
SP_OFFSET = 31 * 8 if platform.machine() in ("aarch64", "arm64") else 19 * 8
DUMPER = r"""
#include <stdio.h>
#include <stdlib.h>
__attribute__((constructor)) static void dump(void) {
    const char *out = getenv("PROBE_MARK");
    if (!out) return;
    FILE *f = fopen(out, "w");
    if (!f) return;
    FILE *maps = fopen("/proc/self/maps", "r");
    char line[512];
    while (maps && fgets(line, sizeof line, maps)) fputs(line, f);
    fclose(f);
}
"""
libc = ctypes.CDLL(None, use_errno=True)
libc.ptrace.restype = ctypes.c_long
libc.ptrace.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
results: dict[str, object] = {}


def closed(name: str, ok: bool, detail: str = "") -> None:
    results[name] = {"closed": bool(ok), "detail": detail}


class IoVec(ctypes.Structure):
    _fields_ = [("base", ctypes.c_void_p), ("len", ctypes.c_size_t)]


def stack_pointer(pid: int) -> int | None:
    """The stopped tracee's stack pointer, read from its registers (which the tracer may read)."""
    buf = ctypes.create_string_buffer(1024)
    iov = IoVec(ctypes.cast(buf, ctypes.c_void_p), 1024)
    if (
        libc.ptrace(
            PTRACE_GETREGSET, pid, ctypes.c_void_p(NT_PRSTATUS), ctypes.byref(iov)
        )
        == -1
    ):
        return None
    return int.from_bytes(buf.raw[SP_OFFSET : SP_OFFSET + 8], "little")


def running_build() -> subprocess.Popen:
    """A build that waits on its standard input (`format -` reads it to the end)."""
    return subprocess.Popen(
        [BUILD, "format", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    work = tempfile.mkdtemp(prefix="probe-")
    try:
        with open(BUILD, "rb") as f:
            f.read(16)
        closed("read the file", False, "read succeeded")
    except OSError as exc:
        closed("read the file", True, exc.__class__.__name__)

    proc = running_build()
    time.sleep(0.3)
    for part in ("exe", "mem", "maps"):
        try:
            with open(f"/proc/{proc.pid}/{part}", "rb") as f:
                data = f.read(64)
            closed(f"/proc/<pid>/{part}", not data, f"{len(data)} bytes")
        except OSError as exc:
            closed(f"/proc/<pid>/{part}", True, exc.__class__.__name__)
    attached = libc.ptrace(PTRACE_ATTACH, proc.pid, None, None)
    err = ctypes.get_errno()
    closed(
        "PTRACE_ATTACH",
        attached == -1,
        os.strerror(err) if attached == -1 else "attached",
    )
    if attached != -1:
        libc.ptrace(PTRACE_DETACH, proc.pid, None, None)
    proc.kill()
    proc.wait()

    lib = os.path.join(work, "dump.so")
    src = os.path.join(work, "dump.c")
    with open(src, "w") as f:
        f.write(DUMPER)
    cc = subprocess.run(
        ["cc", "-shared", "-fPIC", "-o", lib, src],
        check=False,
        capture_output=True,
        text=True,
    )
    if cc.returncode != 0:
        closed("preload library built", False, cc.stderr[-300:])
    else:
        mark = os.path.join(work, "mark-normal")
        subprocess.run(
            [BUILD, "--version"],
            env={"LD_PRELOAD": lib, "PROBE_MARK": mark, "PATH": "/usr/bin:/bin"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        closed("LD_PRELOAD, normal exec", not os.path.exists(mark))

        mark = os.path.join(work, "mark-traced")
        child = os.fork()
        if child == 0:  # pragma: no cover
            libc.ptrace(PTRACE_TRACEME, 0, None, None)
            os.execve(
                BUILD, [BUILD, "--version"], {"LD_PRELOAD": lib, "PROBE_MARK": mark}
            )
        os.waitpid(child, 0)  # stopped at the exec
        sp = stack_pointer(child)
        peek = libc.ptrace(PTRACE_PEEKDATA, child, ctypes.c_void_p(sp or 0), None)
        peek_err = ctypes.get_errno()
        try:
            with open(f"/proc/{child}/mem", "rb") as f:
                f.seek(sp or 0)
                mem = f.read(16)
            mem_detail = f"{len(mem)} bytes at the stack pointer"
        except OSError as exc:
            mem, mem_detail = b"", exc.__class__.__name__
        if sp is None:
            closed("stack pointer of the traced build", False, "registers not readable")
        closed(
            "self-traced exec: PTRACE_PEEKDATA",
            peek == -1 and peek_err != 0,
            os.strerror(peek_err) if peek == -1 else "read a word",
        )
        closed("self-traced exec: /proc/<pid>/mem", not mem, mem_detail)
        libc.ptrace(PTRACE_CONT, child, None, None)
        os.waitpid(child, 0)
        closed("LD_PRELOAD, self-traced exec", not os.path.exists(mark))

    cores = os.path.join(work, "cores")
    os.mkdir(cores)
    proc = subprocess.Popen(
        ["sh", "-c", f"ulimit -c unlimited; cd {cores} && exec {BUILD} format -"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.3)
    os.kill(proc.pid, signal.SIGSEGV)
    proc.wait()
    closed("core dump", not os.listdir(cores), ",".join(os.listdir(cores)))

    ok = all(r["closed"] for r in results.values())
    print(json.dumps({"all_closed": ok, "routes": results}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
