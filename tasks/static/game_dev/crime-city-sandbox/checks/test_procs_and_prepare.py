"""Process control (limits, output caps, whole-tree kills) and project preparation, with
small Python children instead of Godot."""

from __future__ import annotations

import os
import random
import signal
import sys
import time
from pathlib import Path

from qakit import prepare, procs

PY = sys.executable


def run_child(
    tmp_path: Path, code: str, limits: procs.Limits, wait_s: float = 20.0
) -> procs.ExitInfo:
    """Run a Python child under limits until it ends (or wait_s passes) and return how it ended."""
    p = procs.Proc(
        [PY, "-c", code],
        {"PATH": "/usr/bin:/bin"},
        tmp_path,
        limits,
        tmp_path / "out.log",
        home=tmp_path,
    )
    return p.close(wait_s)


def test_output_is_capped_head_and_tail(tmp_path: Path) -> None:
    """Only the first and last parts of a flood of output are kept, with a note between."""
    code = "import sys\nfor i in range(400):\n    sys.stdout.write(('%05d' % i) * 2000 + '\\n')\n"
    ex = run_child(tmp_path, code, procs.Limits(log_head_mb=0.1, log_tail_mb=0.05))
    log = (tmp_path / "out.log").read_bytes()
    assert ex.code == 0 and ex.output_bytes > 3_000_000
    assert ex.output_dropped > 0 and b"bytes of output not kept" in log
    assert len(log) < 200_000 and log.rstrip().endswith(b"00399" * 2000)


def test_wall_limit_kills(tmp_path: Path) -> None:
    """A child past its wall limit is killed and the violation recorded."""
    ex = run_child(tmp_path, "import time\ntime.sleep(60)\n", procs.Limits(wall_s=1.0))
    assert ex.violation == "wall" and ex.signal == signal.SIGKILL and ex.wall_s < 10


def test_cpu_limit_stops_a_busy_loop(tmp_path: Path) -> None:
    """RLIMIT_CPU stops a spinning child; the end is reported as the cpu limit."""
    ex = run_child(
        tmp_path, "while True:\n    pass\n", procs.Limits(cpu_s=1), wait_s=30
    )
    assert ex.violation == "cpu" and ex.signal in (signal.SIGXCPU, signal.SIGKILL)


def test_memory_limit_kills(tmp_path: Path) -> None:
    """A child that keeps allocating is killed by the watchdog at its memory cap."""
    code = "import time\nb = []\nwhile True:\n    b.append(bytearray(16 << 20))\n    time.sleep(0.02)\n"
    ex = run_child(tmp_path, code, procs.Limits(memory_mb=150), wait_s=30)
    assert ex.violation == "memory" and ex.peak_memory_mb > 150


def test_disk_limit_kills(tmp_path: Path) -> None:
    """A child that fills its home folder past the cap is killed."""
    code = "import os, time\nf = open('big.bin', 'wb')\nwhile True:\n    f.write(os.urandom(1 << 20)); f.flush(); time.sleep(0.05)\n"
    ex = run_child(tmp_path, code, procs.Limits(disk_mb=20), wait_s=30)
    assert ex.violation == "disk"


def test_kill_reaches_children_and_grandchildren(tmp_path: Path) -> None:
    """Killing the game kills what it started, including a process that left its group."""
    code = (
        "import os, subprocess, time\n"
        "subprocess.Popen(['/bin/sleep', '4243'])\n"
        "subprocess.Popen(['/bin/sleep', '4243'], start_new_session=True)\n"
        "subprocess.Popen(['/bin/sh', '-c', 'sleep 4243 & sleep 4243'])\n"
        "time.sleep(60)\n"
    )
    p = procs.Proc(
        [PY, "-c", code], {"PATH": "/usr/bin:/bin"}, tmp_path, procs.Limits(), None
    )
    time.sleep(3.0)  # the watchdog samples the tree every 2 s
    tree = procs.descendants(p.pid, procs.process_table())
    assert len(tree) >= 4
    ex = p.kill()
    assert ex.stray_pids == []
    assert all(not procs._exists(pid) or _zombie(pid) for pid in tree)


def _zombie(pid: int) -> bool:
    """Whether pid is a zombie (gone except for its exit status)."""
    out = os.popen(f"ps -o stat= -p {pid}").read().strip()
    return out.startswith("Z") or out == ""


def test_rlimits_always_disable_core_files() -> None:
    """RLIMIT_CORE is 0 whatever else is limited."""
    assert ("RLIMIT_CORE", 0, 0) in procs.rlimits_for(procs.Limits())


def test_add_autoload_first() -> None:
    """The telemetry entry goes first in [autoload], or into a new section."""
    text = 'config_version=5\n\n[autoload]\n\nA="*res://a.gd"\n\n[input]\n'
    out = prepare.add_autoload_first(text, "Tz", "res://_x/Tz.tscn")
    assert out.index('Tz="res://_x/Tz.tscn"') < out.index("A=")
    out2 = prepare.add_autoload_first("config_version=5\n", "Tz", "res://_x/Tz.tscn")
    assert out2.endswith('[autoload]\n\nTz="res://_x/Tz.tscn"\n')


def test_random_names_are_distinct_identifiers() -> None:
    """Folder, class and autoload names are valid and differ from each other."""
    folder, cls, auto = prepare.random_names(random.Random(3))
    assert (
        folder.startswith("_")
        and cls.isidentifier()
        and auto.isidentifier()
        and cls != auto
    )


def test_telemetry_insertion_and_tamper_check(tmp_path: Path) -> None:
    """Inserted files verify; a changed library or a moved autoload entry is reported."""
    game = tmp_path / "game"
    game.mkdir()
    (game / "project.godot").write_text(
        'config_version=5\n\n[autoload]\n\nX="*res://x.gd"\n'
    )
    lib = tmp_path / "lib.bin"
    lib.write_bytes(b"\x7fELF fake")
    tel = prepare.insert_telemetry(game, lib, random.Random(1))
    assert prepare.verify_telemetry(game, tel) == []
    scene = (game / tel.folder / f"{tel.autoload}.tscn").read_text()
    assert f'type="{tel.class_name}"' in scene
    ext = (game / tel.folder / f"{tel.class_name}.gdextension").read_text()
    assert 'entry_symbol = "qa_telemetry_init"' in ext
    (game / tel.folder / f"{tel.class_name}{prepare.LIB_SUFFIX}").write_bytes(b"other")
    pg = game / "project.godot"
    pg.write_text(pg.read_text().replace(f"{tel.autoload}=", "Moved="))
    problems = prepare.verify_telemetry(game, tel)
    assert any("changed" in p for p in problems) and any(
        "first autoload" in p for p in problems
    )


def test_overrides_set_one_worker_thread() -> None:
    """override.cfg runs the game with one worker thread and no file logging."""
    text = prepare.overrides_text(prepare.OVERRIDES)
    assert "[threading]" in text and "worker_pool/max_threads=1" in text
    assert "file_logging/enable_file_logging=false" in text


def test_copy_project_skips_the_cache(tmp_path: Path) -> None:
    """The copy leaves out .godot and override.cfg."""
    src = tmp_path / "src"
    (src / ".godot").mkdir(parents=True)
    (src / ".godot" / "x").write_text("cache")
    (src / "project.godot").write_text("config_version=5\n")
    (src / "override.cfg").write_text("[x]\n")
    prepare.copy_project(src, tmp_path / "dst")
    assert sorted(p.name for p in (tmp_path / "dst").iterdir()) == ["project.godot"]
