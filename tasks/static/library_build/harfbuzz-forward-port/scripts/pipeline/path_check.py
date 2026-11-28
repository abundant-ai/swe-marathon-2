"""Can any user other than root write a directory, or a file, that root resolves commands through? (fix round 2)

usage (inside an image, as root): python3 -I path_check.py OUT.json   (OUT "-": the whole report on stdout)

Harbor runs commands as root in both containers without setting PATH: `tar -czf` to collect /logs/verifier after
test.sh and the artifacts after the turn, and `su` around the collect hook. Our own root programs resolve names too
(test.sh's python3, verify.py's and the sweep's tools). A file that `builder`, `nobody` or `dev` could plant in any of
those directories would run as root (QA, Dogwood pass 07 F1). The directories checked are: the image's PATH, su's
default paths from /etc/login.defs, verify.py's PATH and the sweep's, and the standard system ones; with every
parent folder up to /. For each user that exists here, plus a fresh numeric uid (verify.py runs builds under one), a
forked child takes that user's ids and asks the kernel whether it may write the directory, or any entry in it
(which also covers ACLs). Prints a summary and writes the full report; exit 1 if anything is writable.
"""

from __future__ import annotations

import json
import os
import pwd
import stat
import sys
from pathlib import Path

FIXED = (
    "/opt/py/bin",
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
)
USERS = ("dev", "builder", "nobody")
FRESH_UID = 40017  # an unused uid and gid, as verify.py's per-run builder ids are


def path_dirs() -> list[str]:
    dirs = list(os.environ.get("PATH", "").split(":"))
    try:
        for line in Path("/etc/login.defs").read_text(errors="replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("ENV_PATH", "ENV_SUPATH"):
                dirs += parts[1].split("=", 1)[-1].split(":")
    except OSError:
        pass
    dirs += FIXED
    seen, out = set(), []
    for d in dirs:
        if not d or not d.startswith("/"):
            continue
        p = Path(d)
        for q in [p, *p.parents]:
            s = str(q)
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def identities() -> list[tuple[str, int, int, list[int]]]:
    ids = []
    for name in USERS:
        try:
            pw = pwd.getpwnam(name)
        except KeyError:
            continue
        groups = os.getgrouplist(name, pw.pw_gid)
        ids.append((name, pw.pw_uid, pw.pw_gid, groups))
    ids.append((f"uid {FRESH_UID}", FRESH_UID, FRESH_UID, [FRESH_UID]))
    return ids


def writable_as(ident: tuple[str, int, int, list[int]], dirs: list[str]) -> list[str]:
    """What this identity may write, asked of the kernel in a child that takes its ids."""
    _name, uid, gid, groups = ident
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(r)
        found = []
        try:
            os.setgroups(groups)
            os.setresgid(gid, gid, gid)
            os.setresuid(uid, uid, uid)
            for d in dirs:
                try:
                    st = os.lstat(d)
                except OSError:
                    continue
                if stat.S_ISLNK(st.st_mode):
                    target = os.path.realpath(d)
                    if os.access(target, os.W_OK):
                        found.append(f"{d} -> {target}")
                    continue
                if os.access(d, os.W_OK):
                    found.append(d)
                if d in path_dirs_cache and stat.S_ISDIR(st.st_mode):
                    try:
                        names = os.listdir(d)
                    except OSError:
                        names = []
                    for n in names:
                        f = os.path.join(d, n)
                        try:
                            if not stat.S_ISLNK(os.lstat(f).st_mode) and os.access(
                                f, os.W_OK
                            ):
                                found.append(f)
                        except OSError:
                            pass
            os.write(w, json.dumps(found).encode())
        finally:
            os._exit(0)
    os.close(w)
    data = b""
    while chunk := os.read(r, 65536):
        data += chunk
    os.close(r)
    os.waitpid(pid, 0)
    return json.loads(data.decode() or "[]")


path_dirs_cache: set[str] = set()


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("run as root")
    out = Path(sys.argv[1])
    dirs = path_dirs()
    path_dirs_cache.update(
        d for d in dirs if d in os.environ.get("PATH", "").split(":") or d in FIXED
    )
    report = {"path": os.environ.get("PATH"), "checked": dirs, "writable": {}}
    for ident in identities():
        found = writable_as(ident, dirs)
        if found:
            report["writable"][ident[0]] = found
    report["pass"] = not report["writable"]
    if (
        str(out) == "-"
    ):  # the whole report on stdout (run through `python3 -I -c`, with no file to write)
        print(json.dumps(report, indent=1))
        sys.exit(0 if report["pass"] else 1)
    out.write_text(json.dumps(report, indent=1))
    print(
        json.dumps(
            {"pass": report["pass"], "dirs": len(dirs), "writable": report["writable"]}
        )
    )
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
