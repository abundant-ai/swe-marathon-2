"""Local tests for the weave collect hook and delivery_manifest.check().

Runs on the macOS host with no Docker, network, git or root:

    /Users/skylarkoo7/Documents/github/Abundant/swe-marathon-2/.venv/bin/python -I test_collect.py

Harbor's tar_transfer.py is loaded from its exact file in the Oddish CLI's
site-packages (harbor 0.20.0 @ a5501eca; HARBOR_SITE_PACKAGES overrides the
location).  It is not imported through sys.path, because this venv carries a
different harbor.  That other copy, when present, gets an informational
column, and the hooked trees must pass it too.  Every copy takes Modal's two
legs (harbor/environments/modal.py):

* download, _sdk_download_dir: remote_pack_command (tar -czf ... -C src .) run
  with GNU tar, then extract_dir_from_file (tarfile, filter="data") on the host;
* upload, _sdk_upload_dir: pack_dir_to_file (tarfile) on the host, then
  remote_unpack_command (tar -xzf) for the verifier.

Each tree is also downloaded with pack_dir_to_file in place of GNU tar.  Its
sorted order makes the order-dependent rejections show every time.

The kill and egress steps cannot run here.  The kill loop is driven over a
fake /proc with an injected kill function (fake pids above any real pid), and
the egress step is never called.  Each tree's ground truth is the record the
test keeps while writing it, not the hook's output.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import itertools
import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
# The hook ships in the agent image's build context; the manifest checker in the verifier's.
TASK = HERE.parents[1]
HOOK = TASK / "environment/weave-collect/collect"
HARBOR_SITE = Path(
    os.environ.get(
        "HARBOR_SITE_PACKAGES",
        Path.home() / ".local/share/oddish-cli-noarchil/lib/python3.13/site-packages",
    )
)
GNU, PY = "gnu-tar", "pack_dir"  # download packers
CHAIN = 1000  # d's in the deep chain
# What Harbor's transfer can raise: tarfile filter errors, OSError (ENOTDIR,
# ELOOP, ENAMETOOLONG...), RuntimeError (a tar exit status; RecursionError).
TRANSFER_ERRORS = (tarfile.TarError, OSError, RuntimeError)
FAKE_PID = 5_000_000  # above Linux's PID_MAX_LIMIT (4194304) and macOS's 99998
O_DIR = os.O_RDONLY | os.O_DIRECTORY
O_DIR_NOFOLLOW = O_DIR | os.O_NOFOLLOW


def _load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader(name, loader)
    )
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def _harbor_label(package_dir: Path) -> str:
    for info in sorted(package_dir.parent.glob("harbor-*.dist-info")):
        label = "harbor " + info.name.removeprefix("harbor-").removesuffix(".dist-info")
        with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
            commit = json.loads((info / "direct_url.json").read_text())["vcs_info"][
                "commit_id"
            ]
            label += " @ " + commit[:8]
        return label
    return f"harbor at {package_dir}"


def _pinned_tar_transfer():
    path = HARBOR_SITE / "harbor" / "environments" / "tar_transfer.py"
    if not path.is_file():
        raise SystemExit(f"Harbor's tar_transfer.py not found at {path}")
    return _load("harbor_tar_transfer_pinned", path), _harbor_label(path.parents[1])


def _other_tar_transfer():
    """The harbor this interpreter would import, if it is another copy."""
    spec = importlib.util.find_spec("harbor")
    if spec is None or not spec.submodule_search_locations:
        return None, None
    package = Path(next(iter(spec.submodule_search_locations)))
    path = package / "environments" / "tar_transfer.py"
    if package.resolve() == (HARBOR_SITE / "harbor").resolve() or not path.is_file():
        return None, None
    return _load("harbor_tar_transfer_other", path), _harbor_label(package)


def _gnu_tar() -> str | None:
    for cand in (
        shutil.which("gtar"),
        "/opt/homebrew/bin/gtar",
        "/usr/local/bin/gtar",
        shutil.which("tar"),
    ):
        if cand and Path(cand).is_file():
            out = subprocess.run(
                [cand, "--version"], capture_output=True, text=True, check=False
            )
            if out.stdout.startswith("tar (GNU tar)"):
                return cand
    return None


collect = _load("weave_collect", HOOK)
dm = _load("delivery_manifest", TASK / "tests/delivery_manifest.py")
TT, TT_LABEL = _pinned_tar_transfer()
TT_OTHER, TT_OTHER_LABEL = _other_tar_transfer()
GNU_TAR = _gnu_tar()
PACKERS = (GNU, PY) if GNU_TAR else (PY,)


def say(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def short(exc: BaseException, base: Path) -> str:
    text = f"{type(exc).__name__}: {exc}".replace(str(base), "<tmp>").replace(
        str(HERE), "<here>"
    )
    return text if len(text) <= 120 else text[:117] + "..."


# ------------------------------------------------- descriptor-relative I/O


@contextlib.contextmanager
def at(root: Path, rel: bytes, *, create: bool = False):
    """(dir_fd, name) for rel under root, reached by descriptor at any depth."""
    *parents, name = rel.split(b"/")
    fd = os.open(root, O_DIR)
    try:
        for part in parents:
            if create:
                with contextlib.suppress(FileExistsError):
                    os.mkdir(part, dir_fd=fd)
            nxt = os.open(part, O_DIR_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        yield fd, name
    finally:
        os.close(fd)


def write_rel(root: Path, rel: bytes, data: bytes) -> None:
    with at(root, rel, create=True) as (fd, name):
        out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=fd)
        try:
            os.write(out, data)
        finally:
            os.close(out)


def read_rel(root: Path, rel: bytes) -> bytes | None:
    """Content of rel if it is a regular file reached without links."""
    try:
        with at(root, rel) as (fd, name):
            src = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                if not stat.S_ISREG(os.fstat(src).st_mode):
                    return None
                chunks = []
                while chunk := os.read(src, 1 << 16):
                    chunks.append(chunk)
                return b"".join(chunks)
            finally:
                os.close(src)
    except OSError:
        return None


def link_rel(root: Path, rel: bytes) -> bytes | None:
    try:
        with at(root, rel) as (fd, name):
            return os.readlink(name, dir_fd=fd)
    except OSError:
        return None


def exists_rel(root: Path, rel: bytes) -> bool:
    try:
        with at(root, rel) as (fd, name):
            os.lstat(name, dir_fd=fd)
    except OSError:
        return False
    return True


# -------------------------------------------------------------- the trees


class Tree:
    """A delivery tree and the test's own record of what was written."""

    def __init__(self, root: Path, path_cap: int = collect.PATH_CAP):
        self.root = root
        self.path_cap = path_cap
        self.files: dict[bytes, bytes] = {}  # every regular file written
        self.gone: set[bytes] = set()  # files the hook must remove
        self.unlisted: set[bytes] = set()  # copied, not in the manifest (target/)
        self.links: dict[bytes, bytes] = {}  # links the hook must keep
        self.removals: dict[bytes, str] = {}  # path -> reason the hook must record
        self.skipped: list[str] = []
        root.mkdir(parents=True)

    def file(
        self, rel: bytes, data: bytes | None = None, *, gone=False, unlisted=False
    ):
        data = b"content of " + rel + b"\n" if data is None else data
        write_rel(self.root, rel, data)
        self.files[rel] = data
        if gone:
            self.gone.add(rel)
        if unlisted:
            self.unlisted.add(rel)

    def link(self, rel: bytes, target: bytes, reason: str | None = None):
        with at(self.root, rel, create=True) as (fd, name):
            os.symlink(target, name, dir_fd=fd)
        if reason:
            self.removals[rel] = reason
        else:
            self.links[rel] = target

    def fifo(self, rel: bytes):
        with at(self.root, rel, create=True) as (fd, name):
            os.mkfifo(name, dir_fd=fd)
        self.removals[rel] = "special_file"

    def sock(self, rel: bytes):
        with at(self.root, rel, create=True) as (fd, name):
            here = os.open(".", os.O_RDONLY)
            try:
                os.fchdir(fd)  # AF_UNIX paths are short; bind relative to the directory
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(name.decode())
            finally:
                os.fchdir(here)
                os.close(here)
        self.removals[rel] = "special_file"

    def chain(self, top: bytes, count: int, marks: dict[int, bytes]):
        """top/d/d/... with `count` d's; marks: number of d's -> file put there."""
        for depth, fname in sorted(marks.items()):
            in_level = 1 + depth  # top sits at level 1
            self.file(
                b"/".join([top, *([b"d"] * depth), fname]),
                gone=in_level > collect.DEPTH_CAP,
            )
        self.removals[b"/".join([top, *([b"d"] * collect.DEPTH_CAP)])] = "depth_cap"

    def long_path(self, top: bytes, path_max: int):
        """A path longer than path_max under top, in 250-byte names; the hook
        must cut it at the first directory longer than path_cap."""
        name = b"L" * 250
        self.file(top + b"/keep.txt")
        parts = [top]
        while len(b"/".join(parts)) <= path_max:
            parts.append(name)
        self.file(b"/".join([*parts, b"end.txt"]), gone=True)
        cut = next(
            i
            for i in range(1, len(parts) + 1)
            if len(b"/".join(parts[:i])) > self.path_cap
        )
        self.removals[b"/".join(parts[:cut])] = "path_too_long"

    def try_file(self, rel: bytes, why: str) -> bool:
        try:
            self.file(rel)
        except OSError as exc:
            self.skipped.append(f"{why}: {exc.strerror} (errno {exc.errno})")
            return False
        return True

    def listed(self) -> dict[bytes, bytes]:
        """Files the manifest must list."""
        return {
            r: d
            for r, d in self.files.items()
            if r not in self.gone and r not in self.unlisted
        }

    def kept(self) -> dict[bytes, bytes]:
        """Files that must arrive (the manifest's plus target/)."""
        return {r: d for r, d in self.files.items() if r not in self.gone}


def full_tree(root: Path) -> Tree:
    t = Tree(root)
    t.file(b"Cargo.toml", b'[package]\nname = "weave-driver"\nversion = "0.1.0"\n')
    t.file(b"Cargo.lock", b"# lock\n")
    t.file(b"src/main.rs", b"fn main() { weave_driver::run(); }\n")
    t.file(b"src/lib.rs", b"pub fn run() {}\n")
    for i in range(24):
        t.file(f"src/merge/m{i:02d}.rs".encode(), f"// part {i}\n".encode() * (i + 1))
    t.file(b"tests/merge.rs", b"#[test]\nfn merges() {}\n")
    t.file(b"target/debug/build.log", b"compiled\n", unlisted=True)
    t.file(b"zz-last.txt", b"sorts last\n")
    t.fifo(b"aa-pipe.fifo")
    t.sock(b"aa-run.sock")
    t.link(b"abs-link", b"/etc/hosts", "absolute_link")
    t.link(b"src/up-link", b"../../outside", "outside_link")
    t.link(b"inside-link", b"src/main.rs")
    t.link(b"src/cargo-link", b"../Cargo.toml")
    t.link(b"dangling-link", b"no/such/file")
    t.link(b"a-dot", b".")
    t.link(b"b-up", b"a-dot/..", "link_through_link")
    t.link(b"thru-file", b"Cargo.toml/x", "link_through_file")
    t.link(b"loop-a", b"loop-b", "link_loop")
    t.link(b"loop-b", b"loop-a", "link_loop")
    t.chain(
        b"deep", CHAIN, {63: b"keep-64.txt", 64: b"gone-65.txt", CHAIN: b"bottom.txt"}
    )
    t.try_file(b"src/name-\xff\xfe.rs", "non-UTF-8 file name")
    (root.parent / "outside-delivery").mkdir()
    t.link(b".delivery", b"../outside-delivery", "outside_link")
    return t


def plain_tree(root: Path, path_cap: int = collect.PATH_CAP) -> Tree:
    t = Tree(root, path_cap)
    for i in range(20):
        t.file(f"f{i:02d}.txt".encode())
    t.file(b"sub/s1.txt")
    t.file(b"zz/last.txt")
    return t


def h_fifo(t):
    t.fifo(b"h.fifo")


def h_socket(t):
    t.sock(b"h.sock")


def h_absolute(t):
    t.link(b"h-abs", b"/etc/hosts", "absolute_link")


def h_outward(t):
    t.link(b"sub/h-up", b"../../outside", "outside_link")


def h_via_link(t):
    t.link(b"a-dot", b".")
    t.link(b"b-up", b"a-dot/..", "link_through_link")


def h_via_file(t):
    t.link(b"h-thru", b"f00.txt/x", "link_through_file")


def h_loop(t):
    t.link(b"loop-a", b"loop-b", "link_loop")
    t.link(b"loop-b", b"loop-a", "link_loop")
    t.link(b"loop-c", b"loop-a/x", "link_through_link")


def h_chain(t):
    t.chain(b"deep", CHAIN, {63: b"keep-64.txt", CHAIN: b"bottom.txt"})


def h_long(t):
    t.long_path(b"long", os.pathconf(t.root, "PC_PATH_MAX"))


def h_delivery(t):
    t.link(b".delivery", b"../outside", "outside_link")


HAZARDS = (
    ("FIFO", h_fifo),
    ("Unix socket", h_socket),
    ("absolute symlink", h_absolute),
    ("../../ outward symlink", h_outward),
    ("a-dot -> . and b-up -> a-dot/..", h_via_link),
    ("link through a file", h_via_file),
    ("link loop, and a link into it", h_loop),
    ("1,000-level directory chain", h_chain),
    ("path longer than PATH_MAX", h_long),
    (".delivery -> ../outside", h_delivery),
)


# ------------------------------------------------------------ Harbor legs


class Harbor:
    """Modal's two tar legs, run here with one copy of Harbor's tar_transfer."""

    _seq = itertools.count()

    def __init__(self, work: Path, tar_transfer, label: str):
        self.tt, self.label, self.slug = tar_transfer, label, work.name
        self.work = work
        self.shim = work / "shim"
        self.shim.mkdir(parents=True)
        if GNU_TAR:
            (self.shim / "tar").symlink_to(GNU_TAR)

    def _sh(self, command: str) -> None:
        res = subprocess.run(
            ["/bin/sh", "-c", command],
            env={"PATH": f"{self.shim}:/usr/bin:/bin", "LC_ALL": "C"},
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"exit {res.returncode}: {res.stderr.strip()}")

    def download(self, src: Path, host_dir: Path, packer: str) -> None:
        """modal.py _sdk_download_dir: pack in the sandbox, extract on the host."""
        archive = self.work / f"download-{next(self._seq)}.tar.gz"
        if packer == GNU:
            self._sh(self.tt.remote_pack_command(str(src), str(archive)))
        else:
            self.tt.pack_dir_to_file(src, archive)
        self.tt.extract_dir_from_file(archive, host_dir)

    def upload(self, host_dir: Path, verifier_dir: Path) -> None:
        """modal.py _sdk_upload_dir: pack on the host, unpack for the verifier."""
        archive = self.work / f"upload-{next(self._seq)}.tar.gz"
        self.tt.pack_dir_to_file(host_dir, archive)
        self._sh(self.tt.remote_unpack_command(str(archive), str(verifier_dir)))

    def attempt(
        self, tree: Tree, case: Path, packer: str
    ) -> tuple[str, int, int, Path]:
        """Copy through both legs; (outcome, files arrived, files expected, dir)."""
        host, verifier = case / "host" / "driver", case / "verifier" / "driver"
        outcome = None
        try:
            self.download(tree.root, host, packer)
        except TRANSFER_ERRORS as exc:
            outcome, where = "download raised " + short(exc, case), host
        else:
            where = verifier
            try:
                self.upload(host, verifier)
            except TRANSFER_ERRORS as exc:
                outcome = "upload raised " + short(exc, case)
        kept = tree.kept()
        arrived = sum(read_rel(where, rel) == data for rel, data in kept.items())
        if outcome is None:
            outcome = "whole" if arrived == len(kept) else "truncated"
        return outcome, arrived, len(kept), where


def hook(tree: Tree, end_bound: float | None = None) -> tuple[dict, dict]:
    """The hook's neutralise and manifest steps, as main() chains them."""
    report = collect.neutralise(tree.root, path_cap=tree.path_cap)
    base = {
        "removed": list(report["removed"]),
        "removed_counts": dict(report["removed_counts"]),
        "errors": list(report["errors"]),
    }
    manifest = collect.manifest_step(
        tree.root, base, end_bound=end_bound, ctime_before=report["ctime_before"]
    )
    return report, manifest


def setUpModule():
    say(
        f"python {sys.version.split()[0]} on {sys.platform}; PATH_MAX here {os.pathconf('/', 'PC_PATH_MAX')}"
    )
    say(f"tar_transfer (pinned, asserted): {TT.__file__} ({TT_LABEL})")
    if TT_OTHER:
        say(
            f"tar_transfer (other, info + hooked trees): {TT_OTHER.__file__} ({TT_OTHER_LABEL})"
        )
    say(
        f"GNU tar for remote_pack_command / remote_unpack_command: {GNU_TAR or 'not found'}"
    )


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix=".t-", dir=HERE))
        self.harbor = Harbor(self.tmp / "pinned", TT, TT_LABEL)
        self.other = (
            Harbor(self.tmp / "other", TT_OTHER, TT_OTHER_LABEL) if TT_OTHER else None
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ------------------------------------------------------------------ tests


class TransferTests(Base):
    def test_1_full_tree_after_hook_arrives_whole(self):
        for packer in PACKERS:
            with self.subTest(packer=packer):
                case = self.tmp / packer
                tree = full_tree(case / "driver")
                report, manifest = hook(tree, end_bound=time.time() + 3600)
                self.assertEqual(report["errors"], [])
                got = {e["path"]: e["reason"] for e in report["removed"]}
                self.assertEqual(got, {k.decode(): v for k, v in tree.removals.items()})
                deep = next(e for e in report["removed"] if e["reason"] == "depth_cap")
                self.assertEqual(deep["entries"], (CHAIN - collect.DEPTH_CAP + 1) + 2)
                kinds = {e["path"]: e["kind"] for e in report["removed"]}
                self.assertEqual(
                    (kinds["aa-pipe.fifo"], kinds["aa-run.sock"]), ("fifo", "socket")
                )

                listed = {e["path"]: e for e in manifest["files"]}
                self.assertEqual(
                    set(listed),
                    {r.decode("utf-8", "backslashreplace") for r in tree.listed()},
                )
                for rel, data in tree.listed().items():
                    entry = listed[rel.decode("utf-8", "backslashreplace")]
                    self.assertEqual(
                        (entry["size"], entry["sha256"]),
                        (len(data), hashlib.sha256(data).hexdigest()),
                    )

                delivery = tree.root / ".delivery"
                st_dir, st_file = delivery.lstat(), (delivery / "manifest.json").lstat()
                self.assertTrue(
                    stat.S_ISDIR(st_dir.st_mode) and stat.S_ISREG(st_file.st_mode)
                )
                self.assertEqual(
                    (stat.S_IMODE(st_dir.st_mode), stat.S_IMODE(st_file.st_mode)),
                    (0o755, 0o644),
                )
                self.assertEqual(list((case / "outside-delivery").iterdir()), [])

                for harbor in filter(None, (self.harbor, self.other)):
                    host = case / harbor.slug / "host" / "driver"
                    verifier = case / harbor.slug / "verifier" / "driver"
                    harbor.download(tree.root, host, packer)  # must not raise
                    harbor.upload(host, verifier)
                    for rel, data in tree.kept().items():
                        self.assertEqual(read_rel(verifier, rel), data, rel)
                    for rel in (tree.gone | set(tree.removals)) - {b".delivery"}:
                        self.assertFalse(exists_rel(verifier, rel), rel)
                    self.assertTrue(
                        stat.S_ISDIR((verifier / ".delivery").lstat().st_mode)
                    )
                    for rel, target in tree.links.items():
                        self.assertEqual(link_rel(verifier, rel), target, rel)
                    arrived = json.loads(
                        (verifier / ".delivery" / "manifest.json").read_bytes()
                    )
                    self.assertEqual(arrived["files"], manifest["files"])
                    result = dm.check(verifier)
                    self.assertTrue(result["present"])
                    self.assertEqual(
                        (result["missing"], result["changed"], result["late"]),
                        ([], [], []),
                    )
                    say(
                        f"  [{packer}, {harbor.label}] hook removed {len(report['removed'])} entries "
                        f"({', '.join(f'{k} {v}' for k, v in sorted(report['removed_counts'].items()))}); "
                        f"all {len(listed)} listed files arrived with the same sha256, plus "
                        f"{len(tree.unlisted)} in target/ and {len(tree.links)} kept links; "
                        f"check(): present=True, missing=[], changed=[], late=[]"
                    )
                for skipped in tree.skipped:
                    say(f"  [{packer}] not in this tree: {skipped}")

    def test_2_same_tree_without_hook_is_cut(self):
        for packer in PACKERS:
            with self.subTest(packer=packer):
                case = self.tmp / packer
                tree = full_tree(case / "driver")
                outcome, arrived, expected, _ = self.harbor.attempt(
                    tree, case / "pinned", packer
                )
                say(
                    f"  [{packer}, {self.harbor.label}] no hook: {outcome}; {arrived}/{expected} files arrived"
                )
                self.assertTrue("raised" in outcome or arrived < expected, outcome)
                if self.other:
                    outcome, arrived, expected, _ = self.other.attempt(
                        tree, case / "other", packer
                    )
                    say(
                        f"  [{packer}, {self.other.label}] no hook: {outcome}; {arrived}/{expected} files arrived"
                    )

    def test_3_each_hazard_alone(self):
        prefix = len(str(self.tmp / "h99" / PY / "fixed-o" / "verifier" / "driver")) + 1
        cap = min(collect.PATH_CAP, os.pathconf(self.tmp, "PC_PATH_MAX") - prefix - 64)
        say(
            f"  path_cap for these trees: {cap} (production {collect.PATH_CAP}; this host's PATH_MAX is smaller)"
        )
        for i, (label, build) in enumerate(HAZARDS):
            cut_somewhere = False
            for packer in PACKERS:
                base = self.tmp / f"h{i}" / packer
                bare = plain_tree(base / "bare" / "driver", cap)
                build(bare)
                outcome, arrived, expected, _ = self.harbor.attempt(
                    bare, base / "bare", packer
                )
                cut_somewhere |= "raised" in outcome or arrived < expected
                lines = [
                    f"    no hook, {self.harbor.label}: {outcome}; {arrived}/{expected} arrived"
                ]
                if self.other:
                    o_outcome, o_arrived, _, _ = self.other.attempt(
                        bare, base / "bare-o", packer
                    )
                    lines.append(
                        f"    no hook, {self.other.label}: {o_outcome}; {o_arrived}/{expected} arrived"
                    )
                fixed = plain_tree(base / "fixed" / "driver", cap)
                build(fixed)
                report, _ = hook(fixed)
                afters = []
                for harbor, sub in ((self.harbor, "fixed"), (self.other, "fixed-o")):
                    if harbor is None:
                        continue
                    after, got, want, where = harbor.attempt(fixed, base / sub, packer)
                    result = dm.check(where)
                    afters.append(f"{after} {got}/{want}")
                    with self.subTest(hazard=label, packer=packer, harbor=harbor.label):
                        self.assertEqual(report["errors"], [])
                        self.assertEqual(
                            {e["path"]: e["reason"] for e in report["removed"]},
                            {k.decode(): v for k, v in fixed.removals.items()},
                        )
                        self.assertEqual(after, "whole")
                        self.assertTrue(result["present"])
                        self.assertEqual(
                            (result["missing"], result["changed"]), ([], [])
                        )
                lines.append(
                    f"    with the hook: {', '.join(afters)}; removed {', '.join(sorted(report['removed_counts']))}"
                )
                say(f"  {label} [{packer}]\n" + "\n".join(lines))
            with self.subTest(hazard=label):
                if label == "Unix socket":
                    continue  # tar skips sockets on both packers; nothing is cut
                self.assertTrue(
                    cut_somewhere, f"{label}: no packer was cut without the hook"
                )

    def test_4_device_members_are_refused_by_the_data_filter(self):
        # Device nodes need root to create, so the members go into an archive
        # that Harbor's extract_dir then extracts.  The member after never arrives.
        for kind in (tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE):
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                dev = tarfile.TarInfo("./dev0")
                dev.type, dev.devmajor, dev.devminor = kind, 1, 3
                tar.addfile(dev)
                after = tarfile.TarInfo("./z.txt")
                after.size = 5
                tar.addfile(after, io.BytesIO(b"after"))
            buf.seek(0)
            out = self.tmp / f"type-{kind.decode()}"
            with (
                self.subTest(member_type=kind),
                self.assertRaises(tarfile.SpecialFileError),
            ):
                TT.extract_dir(buf, out)
            self.assertFalse((out / "z.txt").exists())
        say(
            "  char device, block device and FIFO members: SpecialFileError, the member after them not extracted"
        )


class MainTests(Base):
    """main() over a temp tree.  kill_step and egress_step are stubbed: a real
    kill_step on Linux would signal this user's own processes, and the egress
    step needs the network."""

    def _run_main(self, root: Path, egress) -> tuple[int, str]:
        canned = {
            "processes_found": 0,
            "processes": [],
            "kill_rounds": [],
            "remaining_processes": [],
        }
        started = time.time()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(collect, "ROOT", bytes(root)))
            stack.enter_context(
                mock.patch.object(collect, "kill_step", lambda **_: canned)
            )
            stack.enter_context(mock.patch.object(collect, "egress_step", egress))
            stack.enter_context(
                mock.patch.object(collect, "container_start", lambda: started - 60)
            )
            out = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code = collect.main()
        return code, out.getvalue()

    def test_main_writes_the_manifest_when_a_step_fails(self):
        tree = plain_tree(self.tmp / "case" / "driver")
        tree.fifo(b"p.fifo")

        def broken_egress():
            raise OSError("stubbed out: no network in these tests")

        code, out = self._run_main(tree.root, broken_egress)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("weave-collect: files=22 removed=1"), out)
        manifest = json.loads((tree.root / ".delivery" / "manifest.json").read_bytes())
        self.assertEqual(manifest["format"], collect.FORMAT)
        self.assertAlmostEqual(
            manifest["end_bound"] - manifest["container_start"], 34560, places=2
        )
        self.assertIsNone(manifest["egress"])
        self.assertEqual(
            [e for e in manifest["errors"] if e.startswith("egress: ")],
            ["egress: OSError: stubbed out: no network in these tests"],
        )
        self.assertEqual(
            [(e["path"], e["reason"]) for e in manifest["removed"]],
            [("p.fifo", "special_file")],
        )
        self.assertEqual((manifest["file_count"], manifest["late_files"]), (22, []))
        self.assertEqual(
            set(manifest["timings"]),
            {"kill", "egress", "container_start", "neutralise"},
        )
        result = dm.check(tree.root)
        self.assertEqual(
            (result["present"], result["missing"], result["changed"]), (True, [], [])
        )

    def test_main_returns_0_without_a_root(self):
        code, out = self._run_main(
            self.tmp / "absent", lambda: {"open": False, "hosts": {}}
        )
        self.assertEqual(code, 0)
        self.assertIn("errors=", out)
        self.assertFalse((self.tmp / "absent").exists())


class DeliveryTests(Base):
    def test_whatever_stands_at_delivery_is_replaced(self):
        def as_link(root, outside):
            (root / ".delivery").symlink_to(outside)

        def as_file(root, outside):
            (root / ".delivery").write_bytes(b'{"files": []}')

        def as_fifo(root, outside):
            os.mkfifo(root / ".delivery")

        def as_tree(root, outside):
            (root / ".delivery" / "old").mkdir(parents=True)
            (root / ".delivery" / "manifest.json").symlink_to(outside / "victim.json")
            (root / ".delivery" / "old" / "x").write_bytes(b"x")

        for label, plant in (
            ("symlink", as_link),
            ("file", as_file),
            ("fifo", as_fifo),
            ("tree", as_tree),
        ):
            with self.subTest(planted=label):
                case = self.tmp / label
                root, outside = case / "driver", case / "outside"
                root.mkdir(parents=True)
                outside.mkdir()
                (outside / "victim.json").write_bytes(b"keep me")
                (root / "a.txt").write_bytes(b"a")
                plant(root, outside)
                manifest = collect.manifest_step(root, {"note": label})
                self.assertEqual(
                    sorted(p.name for p in outside.iterdir()), ["victim.json"]
                )
                self.assertEqual((outside / "victim.json").read_bytes(), b"keep me")
                st_dir = (root / ".delivery").lstat()
                st_file = (root / ".delivery" / "manifest.json").lstat()
                self.assertTrue(
                    stat.S_ISDIR(st_dir.st_mode) and stat.S_ISREG(st_file.st_mode)
                )
                self.assertEqual(
                    (stat.S_IMODE(st_dir.st_mode), stat.S_IMODE(st_file.st_mode)),
                    (0o755, 0o644),
                )
                self.assertEqual(
                    [p.name for p in (root / ".delivery").iterdir()], ["manifest.json"]
                )
                self.assertEqual(
                    [e["reason"] for e in manifest["removed"]], ["replaced"]
                )
                self.assertEqual([e["path"] for e in manifest["files"]], ["a.txt"])

    def test_late_files_are_those_changed_after_end_bound(self):
        root = self.tmp / "driver"
        root.mkdir()
        (root / "early.txt").write_bytes(b"early")
        time.sleep(0.1)
        bound = time.time()
        time.sleep(0.1)
        (root / "late.txt").write_bytes(b"late")
        manifest = collect.manifest_step(root, end_bound=bound)
        self.assertEqual(manifest["late_files"], ["late.txt"])
        self.assertEqual(dm.check(root)["late"], ["late.txt"])


class CheckTests(Base):
    def test_missing_changed_and_bad_manifests(self):
        root = self.tmp / "driver"
        (root / "sub").mkdir(parents=True)
        for name in ("same", "edited", "resized", "deleted", "relinked", "sub/redir"):
            (root / name).write_bytes(b"0123456789")
        collect.manifest_step(root)
        (root / "edited").write_bytes(b"9876543210")
        (root / "resized").write_bytes(b"0123")
        (root / "deleted").unlink()
        (root / "relinked").unlink()
        (root / "relinked").symlink_to("same")
        (root / "sub" / "redir").unlink()
        (root / "sub" / "redir").mkdir()
        result = dm.check(root)
        self.assertTrue(result["present"])
        self.assertEqual(
            sorted(result["missing"]), ["deleted", "relinked", "sub/redir"]
        )
        self.assertEqual(sorted(result["changed"]), ["edited", "resized"])

        manifest_path = root / ".delivery" / "manifest.json"
        manifest_path.write_bytes(b'{"files": [')
        result = dm.check(root)
        self.assertFalse(result["present"])
        self.assertIn("does not parse", result["notes"][0])

        manifest_path.write_bytes(b"[" * 100000 + b"]" * 100000)
        self.assertFalse(dm.check(root)["present"])

        manifest_path.write_text(
            json.dumps(
                {
                    "format": collect.FORMAT,
                    "files": [
                        {
                            "path": "same",
                            "size": 10,
                            "sha256": hashlib.sha256(b"0123456789").hexdigest(),
                        },
                        {
                            "path": "name-\\xff.rs",
                            "path_hex": b"name-\xff.rs".hex(),
                            "size": 1,
                            "sha256": None,
                        },
                        {"path": "../escape", "size": 1},
                        {"path": "/abs", "size": 1},
                    ],
                    "late_files": ["same"],
                }
            )
        )
        result = dm.check(root)
        self.assertTrue(result["present"])
        self.assertEqual(
            (result["missing"], result["changed"], result["late"]),
            (["name-\\xff.rs"], [], ["same"]),
        )
        self.assertTrue(
            any("2 manifest entries" in n for n in result["notes"]), result["notes"]
        )

        shutil.rmtree(root / ".delivery")
        (root / ".delivery").symlink_to(self.tmp)
        self.assertFalse(dm.check(root)["present"])
        (root / ".delivery").unlink()
        result = dm.check(root)
        self.assertFalse(result["present"])
        self.assertEqual(result["notes"], ["no manifest at .delivery/manifest.json"])

    def test_non_utf8_names_round_trip(self):
        raw = b"src/name-\xff\xfe.rs"
        fields = collect._path_fields(raw)
        self.assertEqual(
            fields, {"path": "src/name-\\xff\\xfe.rs", "path_hex": raw.hex()}
        )
        self.assertEqual(dm._entry_path(fields), raw)
        self.assertEqual(dm._entry_path(json.loads(json.dumps(fields))), raw)
        self.assertEqual(
            collect._path_fields("src/é.rs".encode()), {"path": "src/é.rs"}
        )
        for bad in ("../x", "/abs", "a//b", "a/./b", "", "a/.."):
            self.assertIsNone(dm._entry_path({"path": bad}), bad)
        self.assertIsNone(dm._entry_path({"path_hex": "zz"}))

    def test_non_utf8_file_on_disk(self):
        tree = plain_tree(self.tmp / "case" / "driver")
        if not tree.try_file(b"sub/name-\xff\xfe.rs", "non-UTF-8 file name"):
            self.skipTest(f"this filesystem refuses the name: {tree.skipped[0]}")
        hook(tree)
        outcome, arrived, expected, where = self.harbor.attempt(
            tree, self.tmp / "case", PACKERS[0]
        )
        self.assertEqual((outcome, arrived), ("whole", expected))
        self.assertEqual(dm.check(where)["missing"], [])


class ProcTests(Base):
    """kill_step over a fake /proc; no real process is ever signalled."""

    def _proc(
        self,
        proc: Path,
        pid: int,
        uid: int,
        comm: bytes,
        cmdline: bytes,
        states: list[bytes],
    ):
        d = proc / str(pid)
        (d / "task").mkdir(parents=True)
        ids = b"\t".join([str(uid).encode()] * 4)
        (d / "status").write_bytes(
            b"Name:\t"
            + comm
            + b"\nState:\t"
            + states[0]
            + b"\nTgid:\t%d\nUid:\t" % pid
            + ids
            + b"\nGid:\t"
            + ids
            + b"\n"
        )
        (d / "comm").write_bytes(comm + b"\n")
        (d / "cmdline").write_bytes(cmdline)
        for n, state in enumerate(states):
            (d / "task" / str(pid + n)).mkdir()
            (d / "task" / str(pid + n) / "status").write_bytes(
                b"Name:\tt\nState:\t" + state + b"\n"
            )

    def test_kill_loop(self):
        proc = self.tmp / "proc"
        zombie_main, zombie, root_proc, stuck = (
            FAKE_PID + 10,
            FAKE_PID + 20,
            FAKE_PID + 30,
            FAKE_PID + 40,
        )
        z, s, d = b"Z (zombie)", b"S (sleeping)", b"D (disk sleep)"
        self._proc(proc, 1, 0, b"init", b"/sbin/init\0", [s])
        self._proc(
            proc,
            zombie_main,
            1001,
            b"bad\xffname",
            b"python3\0-c\0import os # \xfe\0",
            [z, s],
        )
        self._proc(proc, zombie, 1001, b"defunct", b"", [z])
        self._proc(proc, root_proc, 0, b"sshd", b"sshd\0", [s])
        self._proc(proc, stuck, 1002, b"stuck", b"cat\0/mnt/x\0", [d])
        (proc / "self").mkdir()
        killed: list[int] = []

        def fake_kill(pid, sig):
            self.assertGreaterEqual(pid, FAKE_PID)  # a fake pid, never a real one
            self.assertEqual(sig, signal.SIGKILL)
            killed.append(pid)
            if pid == zombie_main:  # SIGKILL lands: every task now Z
                for status in (proc / str(pid) / "task").glob("*/status"):
                    status.write_bytes(b"Name:\tt\nState:\tZ (zombie)\n")

        now = [0.0]
        out = collect.kill_step(
            proc,
            kill=fake_kill,
            clock=lambda: now[0],
            sleep=lambda sec: now.__setitem__(0, now[0] + sec),
            limit=0.5,
            protect={1},
        )
        found = {p["pid"]: p for p in out["processes"]}
        self.assertEqual(sorted(found), [zombie_main, zombie, stuck])
        self.assertEqual(found[zombie_main]["comm"], "bad\\xffname")
        self.assertEqual(
            found[zombie_main]["cmdline"], ["python3", "-c", "import os # \\xfe"]
        )
        self.assertEqual(
            (found[zombie_main]["alive"], found[zombie]["alive"]), (True, False)
        )
        self.assertEqual(killed.count(zombie_main), 1)
        self.assertNotIn(zombie, killed)
        self.assertNotIn(root_proc, killed)
        self.assertGreaterEqual(killed.count(stuck), 5)
        self.assertEqual(out["kill_rounds"][0]["pids"], [zombie_main, stuck])
        self.assertEqual(out["remaining_processes"], [stuck])
        say(
            f"  fake /proc: {out['processes_found']} non-root found, {len(out['kill_rounds'])} rounds, "
            f"remaining {out['remaining_processes']}; comm {found[zombie_main]['comm']!r}, "
            f"cmdline {found[zombie_main]['cmdline']!r}"
        )

        (proc / str(stuck) / "task" / str(stuck) / "status").write_bytes(
            b"State:\tZ (zombie)\n"
        )
        now[0] = 0.0
        quiet = collect.kill_step(
            proc,
            kill=fake_kill,
            clock=lambda: now[0],
            sleep=lambda sec: None,
            protect={1},
        )
        self.assertEqual((quiet["kill_rounds"], quiet["remaining_processes"]), ([], []))

    def test_container_start(self):
        proc = self.tmp / "proc"
        (proc / "1").mkdir(parents=True)
        (proc / "stat").write_bytes(b"cpu  1 2 3 4\nbtime 1700000000\nprocesses 9\n")
        rest = b"S 0 1 1 0 -1 4194560 0 0 0 0 0 0 0 0 20 0 1 0 12345 999"
        (proc / "1" / "stat").write_bytes(b"1 (my (init) ) x) " + rest + b"\n")
        want = 1700000000 + 12345 / os.sysconf("SC_CLK_TCK")
        self.assertAlmostEqual(collect.container_start(proc), want)


class HookFileTests(unittest.TestCase):
    def test_shebang_mode_and_import(self):
        path = HOOK
        self.assertEqual(path.read_bytes().split(b"\n", 1)[0], b"#!/usr/bin/python3 -I")
        self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
        self.assertEqual(collect.ROOT, b"/app/driver")
        self.assertEqual((collect.DEPTH_CAP, collect.END_OFFSET), (64, 34560))


if __name__ == "__main__":
    unittest.main(verbosity=2)
