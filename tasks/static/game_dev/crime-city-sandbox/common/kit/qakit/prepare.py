"""Prepare a copy of a game project for QA runs: telemetry, settings, import.

The copy gets:
- the telemetry node's library, a .gdextension file and a one-node scene in a folder with
  a random name, the scene listed first in [autoload] under another random name (the
  node's class is the library's file name, also random);
- an override.cfg that runs the game with one worker thread
  (threading/worker_pool/max_threads=1) and without file logging (output goes to the
  kit, which keeps its head and tail);
- a headless import (godot --headless --path DIR --import).

After the import the copy is checked: the import ended normally, the engine registered
the telemetry library (.godot/extension_list.cfg) and the telemetry files are unchanged.
verify_telemetry repeats the file check before each run.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import string
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .procs import ExitInfo, Limits, Proc
from .session import game_env

OVERRIDES = {
    "threading": {"worker_pool/max_threads": "1"},
    "debug": {
        "file_logging/enable_file_logging": "false",
        "file_logging/enable_file_logging.pc": "false",
    },
}
LIB_SUFFIX = ".dylib" if sys.platform == "darwin" else ".so"
ALNUM = string.ascii_lowercase + string.digits


@dataclass(frozen=True)
class Telemetry:
    """Where the telemetry node was put in a prepared copy.

    Attributes:
        folder: Project folder holding the telemetry files (random, starts with "_").
        class_name: The node's class name and the library's file stem (random).
        autoload: The autoload entry's name (random, different from class_name).
        hashes: SHA-256 of each telemetry file, by path relative to the project.
    """

    folder: str
    class_name: str
    autoload: str
    hashes: dict[str, str]


@dataclass
class Prepared:
    """A prepared copy and what its preparation found.

    Attributes:
        game_dir: The copy.
        telemetry: Where the telemetry node is.
        import_ok: The import ended normally (exit code 0, no kill, no limit).
        import_exit: How the import process ended.
        extension_registered: The engine lists the telemetry library as an extension.
        problems: Everything that went wrong, in plain words (empty when ready).
        cache_mb: Size of the project's .godot folder after the import.
        import_s: Wall seconds of the import.
    """

    game_dir: Path
    telemetry: Telemetry
    import_ok: bool
    import_exit: ExitInfo | None
    extension_registered: bool
    problems: list[str] = field(default_factory=list)
    cache_mb: float = 0.0
    import_s: float = 0.0

    @property
    def ready(self) -> bool:
        """Whether the copy can be run."""
        return not self.problems

    def to_json(self) -> dict:
        """A JSON-ready summary (paths as strings)."""
        d = asdict(self)
        d["game_dir"] = str(self.game_dir)
        return d


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_project(src: Path, dst: Path) -> None:
    """Copy a project without its .godot cache, override.cfg or Python caches.

    Symbolic links are copied as links, never followed.

    Args:
        src: The project folder (with project.godot).
        dst: A path that must not exist yet.

    Raises:
        FileExistsError: dst exists.
        FileNotFoundError: src has no project.godot.
    """
    if not (src / "project.godot").is_file():
        raise FileNotFoundError(f"{src} has no project.godot")
    if dst.exists():
        raise FileExistsError(dst)
    skip = {".godot", "override.cfg", "__pycache__"}
    shutil.copytree(
        src,
        dst,
        symlinks=True,
        ignore=lambda _d, names: [n for n in names if n in skip],
    )


def add_autoload_first(project_text: str, name: str, path: str) -> str:
    """Return project.godot text with one autoload entry placed first.

    The entry is not a singleton (no "*"), so it is not a global name in scripts.

    Args:
        project_text: The current project.godot contents.
        name: Autoload name.
        path: res:// path of the scene.

    Returns:
        The new text. An [autoload] section is created at the end when there is none.
    """
    entry = f'{name}="{path}"\n'
    lines = project_text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "[autoload]":
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            return "".join(lines[:j]) + entry + "".join(lines[j:])
    tail = "" if project_text.endswith("\n") or not project_text else "\n"
    return project_text + tail + "\n[autoload]\n\n" + entry


def overrides_text(overrides: dict[str, dict[str, str]]) -> str:
    """Render override.cfg sections ({section: {key: raw value}})."""
    out = []
    for section, kv in overrides.items():
        out.append(f"[{section}]\n\n")
        out.extend(f"{k}={v}\n" for k, v in kv.items())
        out.append("\n")
    return "".join(out)


def random_names(rng: random.Random) -> tuple[str, str, str]:
    """Random folder, class and autoload names (distinct, valid identifiers).

    Returns:
        ("_" + 10 characters, "N" + 11, "A" + 11) from lowercase letters and digits.
    """
    folder = "_" + "".join(rng.choice(ALNUM) for _ in range(10))
    cls = "N" + "".join(rng.choice(ALNUM) for _ in range(11))
    auto = "A" + "".join(rng.choice(ALNUM) for _ in range(11))
    return folder, cls, auto


def insert_telemetry(game_dir: Path, library: Path, rng: random.Random) -> Telemetry:
    """Add the telemetry node to a project copy (files, then the autoload entry).

    Args:
        game_dir: The copy (modified in place).
        library: The built telemetry library for this platform.
        rng: Source of the random names.

    Returns:
        Where the node was put, with the files' hashes.
    """
    folder, cls, auto = random_names(rng)
    (game_dir / folder).mkdir()
    lib_rel = f"{folder}/{cls}{LIB_SUFFIX}"
    shutil.copyfile(library, game_dir / lib_rel)
    (game_dir / lib_rel).chmod(0o755)
    ext_rel = f"{folder}/{cls}.gdextension"
    (game_dir / ext_rel).write_text(
        "[configuration]\n\n"
        'entry_symbol = "qa_telemetry_init"\n'
        'compatibility_minimum = "4.7"\n'
        "reloadable = false\n\n"
        "[libraries]\n\n"
        f'macos.debug = "res://{folder}/{cls}.dylib"\n'
        f'macos.release = "res://{folder}/{cls}.dylib"\n'
        f'linux.debug.x86_64 = "res://{folder}/{cls}.so"\n'
        f'linux.release.x86_64 = "res://{folder}/{cls}.so"\n'
    )
    scene_rel = f"{folder}/{auto}.tscn"
    (game_dir / scene_rel).write_text(
        f'[gd_scene format=3]\n\n[node name="{auto}" type="{cls}"]\n'
    )
    pg = game_dir / "project.godot"
    pg.write_text(add_autoload_first(pg.read_text(), auto, f"res://{scene_rel}"))
    hashes = {rel: sha256_file(game_dir / rel) for rel in (lib_rel, ext_rel, scene_rel)}
    return Telemetry(folder, cls, auto, hashes)


def verify_telemetry(game_dir: Path, tel: Telemetry) -> list[str]:
    """Check that the telemetry files and the autoload entry are still in place.

    Args:
        game_dir: A prepared copy.
        tel: What prepare recorded.

    Returns:
        Problems found, in plain words (empty when all is in place).
    """
    problems = []
    for rel, digest in tel.hashes.items():
        path = game_dir / rel
        if not path.is_file():
            problems.append(f"telemetry file missing: {rel}")
        elif sha256_file(path) != digest:
            problems.append(f"telemetry file changed: {rel}")
    text = (game_dir / "project.godot").read_text(errors="replace")
    m = re.search(r"^\[autoload\]\s*\n(?:\s*\n)*([^\n]*)", text, re.MULTILINE)
    want = f'{tel.autoload}="res://{tel.folder}/{tel.autoload}.tscn"'
    if not m or m.group(1).strip() != want:
        problems.append("telemetry is not the first autoload")
    return problems


def extension_registered(game_dir: Path, tel: Telemetry) -> bool:
    """Whether the engine registered exactly the telemetry library as an extension."""
    path = game_dir / ".godot" / "extension_list.cfg"
    if not path.is_file():
        return False
    lines = [
        ln.strip() for ln in path.read_text(errors="replace").splitlines() if ln.strip()
    ]
    return lines == [f"res://{tel.folder}/{tel.class_name}.gdextension"]


def cache_mb(game_dir: Path) -> float:
    """Size of a project's .godot folder in MiB (0 when it does not exist)."""
    from .procs import folder_mb

    return folder_mb(game_dir / ".godot")


def import_project(
    game_dir: Path,
    godot: str,
    home: Path,
    limits: Limits,
    log_path: Path | None,
    before_start=None,
) -> ExitInfo:
    """Run the engine's headless import on a project copy.

    Args:
        game_dir: The copy.
        godot: Absolute path of the Godot binary.
        home: Home folder for the import process.
        limits: Limits; limits.wall_s is the import's time cap.
        log_path: File for the import's output, or None.
        before_start: Optional callable run just before the process starts.

    Returns:
        How the import process ended.
    """
    home.mkdir(parents=True, exist_ok=True)
    if before_start:
        before_start()
    argv = [godot, "--headless", "--path", str(game_dir), "--import"]
    proc = Proc(argv, game_env(home, {}), game_dir, limits, log_path, home=home)
    proc.wait(None)
    return proc.close(0)


def prepare(
    src: Path,
    dst: Path,
    godot: str,
    library: Path,
    rng: random.Random,
    work: Path,
    import_limits: Limits,
    before_start=None,
) -> Prepared:
    """Copy a project, add the telemetry node and the settings, import it, check it.

    Args:
        src: The project to prepare (left untouched).
        dst: Where the copy goes (must not exist).
        godot: Absolute path of the Godot binary.
        library: The built telemetry library for this platform.
        rng: Source of the random telemetry names.
        work: Folder for the import's home folder and log.
        import_limits: Limits of the import process (wall_s caps its time).
        before_start: Optional callable run just before the import starts.

    Returns:
        The prepared copy; check .ready and .problems before running it.

    Raises:
        FileNotFoundError, FileExistsError: As copy_project.
    """
    src, dst, work = src.resolve(), dst.resolve(), work.resolve()
    copy_project(src, dst)
    tel = insert_telemetry(dst, library, rng)
    (dst / "override.cfg").write_text(overrides_text(OVERRIDES))
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    ex = import_project(
        dst,
        godot,
        work / "import-home",
        import_limits,
        work / "import.log",
        before_start,
    )
    elapsed = time.monotonic() - t0
    problems = []
    import_ok = ex.code == 0 and ex.violation is None
    if ex.violation == "wall":
        problems.append(f"import did not finish within {import_limits.wall_s:.0f} s")
    elif ex.violation:
        problems.append(f"import stopped for its {ex.violation} limit")
    elif ex.code != 0:
        why = f"exit code {ex.code}" if ex.code is not None else f"signal {ex.signal}"
        problems.append(f"import ended with {why}")
    registered = extension_registered(dst, tel)
    if import_ok and not registered:
        problems.append("the engine did not register the telemetry library")
    problems += verify_telemetry(dst, tel)
    prepared = Prepared(
        dst,
        tel,
        import_ok,
        ex,
        registered,
        problems,
        round(cache_mb(dst), 2),
        round(elapsed, 2),
    )
    (work / "prepared.json").write_text(json.dumps(prepared.to_json(), indent=1))
    return prepared
