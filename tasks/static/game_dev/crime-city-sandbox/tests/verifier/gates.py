"""The three gates: static scan, import, boot (plan, section 1). A failed gate zeroes the reward.

G_static (before any of the game's code runs): no C#, no native libraries or other
extensions (PF-1); the project settings of PF-2; the 28 actions of IN-1 with keyboard or
mouse and gamepad bindings; no name from the originality denylist in the project's own
text or file names (OR-1; the vendor library is ours and not scanned).

G_import: the kit's preparation (copy, telemetry, one worker thread, headless import)
finished in time, registered the telemetry library, and the project's own import cache
stays under its cap (PF-3).

G_boot: a solo process reaches a playable world within 60 s of starting: its state report
answers and a player is registered (PF-4); a server process answers with role "server".
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from qakit.prepare import Prepared
from qakit.session import GameSpec, Session, SessionError, SessionOptions

ACTIONS = (
    "move_forward",
    "move_back",
    "move_left",
    "move_right",
    "look_left",
    "look_right",
    "look_up",
    "look_down",
    "sprint",
    "jump",
    "crouch",
    "interact",
    "attack",
    "aim",
    "lock_target",
    "reload",
    "weapon_next",
    "weapon_prev",
    "cover",
    "accelerate",
    "brake",
    "steer_left",
    "steer_right",
    "handbrake",
    "horn",
    "phone",
    "map",
    "pause",
)
FORBIDDEN_SUFFIXES = (
    ".cs",
    ".csproj",
    ".sln",
    ".fsproj",
    ".vbproj",
    ".gdextension",
    ".gdnlib",
    ".gdns",
    ".so",
    ".dylib",
    ".dll",
    ".a",
    ".wasm",
    ".jar",
    ".framework",
    ".xcframework",
)
TEXT_SUFFIXES = (
    ".gd",
    ".tscn",
    ".tres",
    ".godot",
    ".cfg",
    ".json",
    ".md",
    ".txt",
    ".gdshader",
    ".shader",
    ".gdshaderinc",
    ".csv",
    ".translation",
    ".po",
)
VENDOR = "assets/vendor"


@dataclass
class GateResult:
    """One gate's verdict.

    Attributes:
        name: "static", "import" or "boot".
        passed: Whether the gate holds.
        problems: What failed, in plain words.
        measured: Values measured (times, sizes, counts).
    """

    name: str
    passed: bool
    problems: list[str] = field(default_factory=list)
    measured: dict = field(default_factory=dict)


def project_settings(text: str) -> dict[str, str]:
    """Flatten project.godot into {"section/key": raw value} (multi-line values joined).

    Args:
        text: project.godot contents.

    Returns:
        The settings; raw values keep their quotes and Godot syntax.
    """
    out: dict[str, str] = {}
    section = ""
    key = None
    buf: list[str] = []
    depth = 0
    for line in text.splitlines():
        if key is not None:
            buf.append(line)
            depth += (
                line.count("{") + line.count("[") - line.count("}") - line.count("]")
            )
            if depth <= 0:
                out[f"{section}/{key}" if section else key] = "\n".join(buf)
                key = None
            continue
        s = line.strip()
        if not s or s.startswith(";"):
            continue
        m = re.match(r"^\[([^\]]+)\]$", s)
        if m:
            section = m.group(1)
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            depth = v.count("{") + v.count("[") - v.count("}") - v.count("]")
            if depth > 0:
                key, buf = k.strip(), [v]
            else:
                out[f"{section}/{k.strip()}" if section else k.strip()] = v.strip()
    return out


def settings_problems(settings: dict[str, str]) -> list[str]:
    """PF-2: Jolt, 60 ticks, jitter fix 0, physics on the main thread, Compatibility."""
    probs = []
    if settings.get("physics/3d/physics_engine", "").strip('"') != "Jolt Physics":
        probs.append("physics engine is not Jolt Physics")
    ticks = settings.get("physics/common/physics_ticks_per_second", "60")
    if ticks.strip() not in ("60", "60.0"):
        probs.append(f"physics ticks per second is {ticks}, not 60")
    jitter = settings.get("physics/common/physics_jitter_fix")
    try:
        if jitter is None or float(jitter) != 0.0:
            probs.append("physics jitter fix is not 0")
    except ValueError:
        probs.append("physics jitter fix is not 0")
    if settings.get("physics/3d/run_on_separate_thread", "false").strip() not in (
        "false",
        "False",
    ):
        probs.append("physics runs on a separate thread")
    if (
        settings.get("rendering/renderer/rendering_method", "").strip('"')
        != "gl_compatibility"
    ):
        probs.append("the renderer is not Compatibility")
    return probs


def inputmap_problems(settings: dict[str, str]) -> list[str]:
    """IN-1: every action exists with a keyboard or mouse event and a gamepad event."""
    probs = []
    for a in ACTIONS:
        raw = settings.get(f"input/{a}")
        if raw is None:
            probs.append(f"action {a} is missing")
            continue
        kb = "InputEventKey" in raw or "InputEventMouseButton" in raw
        pad = "InputEventJoypadButton" in raw or "InputEventJoypadMotion" in raw
        if not kb:
            probs.append(f"action {a} has no keyboard or mouse binding")
        if not pad:
            probs.append(f"action {a} has no gamepad binding")
    return probs


def own_files(project: Path) -> list[Path]:
    """The project's files outside .godot and the vendor library, sorted."""
    out = []
    for p in sorted(project.rglob("*")):
        rel = p.relative_to(project).as_posix()
        if rel.startswith((".godot", VENDOR)):
            continue
        out.append(p)
    return out


def denylist_pattern(entries: list[str]) -> re.Pattern | None:
    """A case-insensitive whole-word pattern for the denylist (None when empty)."""
    words = [
        re.escape(e.strip()) for e in entries if e.strip() and not e.startswith("#")
    ]
    if not words:
        return None
    joined = "|".join(sorted(words, key=len, reverse=True))
    return re.compile(
        r"(?<![A-Za-z0-9])(?:" + joined + r")(?![A-Za-z0-9])", re.IGNORECASE
    )


def static_gate(project: Path, denylist: list[str]) -> GateResult:
    """G_static over the submitted project, before anything of it runs.

    Args:
        project: The project folder as collected.
        denylist: Originality denylist entries (names; "#" starts a comment line).

    Returns:
        The gate's verdict.
    """
    probs: list[str] = []
    pg = project / "project.godot"
    if not pg.is_file():
        return GateResult("static", False, ["no project.godot"])
    files = own_files(project)
    native = [
        f.relative_to(project).as_posix()
        for f in files
        if f.name.lower().endswith(FORBIDDEN_SUFFIXES)
    ]
    if native:
        probs.append(f"C# or native files: {', '.join(native[:5])}")
    settings = project_settings(pg.read_text(errors="replace"))
    probs += settings_problems(settings)
    probs += inputmap_problems(settings)
    pat = denylist_pattern(denylist)
    hits = []
    if pat is not None:
        for f in files:
            rel = f.relative_to(project).as_posix()
            if (
                pat.search(rel.replace("_", " ").replace("-", " "))
                or pat.search(rel)
                or (
                    f.is_file()
                    and f.suffix.lower() in TEXT_SUFFIXES
                    and f.stat().st_size < (8 << 20)
                    and pat.search(f.read_text(errors="replace"))
                )
            ):
                hits.append(rel)
            if len(hits) >= 5:
                break
    if hits:
        probs.append(f"names from the originality denylist in: {', '.join(hits)}")
    return GateResult("static", not probs, probs, {"files": len(files)})


def import_gate(
    prepared: Prepared, cache_cap_mb: float, import_cap_s: float
) -> GateResult:
    """G_import from a preparation's outcome.

    Args:
        prepared: The kit's preparation of the project copy.
        cache_cap_mb: The largest own import cache allowed (1024 in the release).
        import_cap_s: The import's time cap (600 in the release; also enforced while running).

    Returns:
        The gate's verdict.
    """
    probs = list(prepared.problems)
    if prepared.cache_mb > cache_cap_mb:
        probs.append(
            f"import cache {prepared.cache_mb:.0f} MB is over {cache_cap_mb:.0f} MB"
        )
    if prepared.import_s > import_cap_s:
        probs.append(
            f"import took {prepared.import_s:.0f} s, over {import_cap_s:.0f} s"
        )
    measured = {"import_s": prepared.import_s, "cache_mb": prepared.cache_mb}
    return GateResult("import", not probs, probs, measured)


def boot_once(
    spec: GameSpec, opts: SessionOptions, budget_s: float, want_role: str
) -> tuple[list[str], dict]:
    """Start one process and step it until it is playable or the budget runs out.

    Returns:
        (problems, measured); the process is closed either way.
    """
    probs: list[str] = []
    measured: dict = {}
    try:
        s = Session(spec, opts)
    except SessionError as exc:
        return [f"{want_role} did not start: {exc}"], measured
    try:
        measured["hello"] = s.hello
        while True:
            fr = s.step(6, observe={"census": True, "state": True, "every": 6})
            st = fr.get("state")
            ok = isinstance(st, dict) and st.get("ok") is True
            role = (
                (st or {}).get("network", {}).get("role")
                if isinstance(st, dict)
                else None
            )
            if want_role == "solo":
                has_player = any(e.get("k") == "player" for e in fr.get("census") or [])
                ready = ok and has_player
            else:
                ready = ok and role == "server"
            elapsed = time.monotonic() - s.t_start
            if ready:
                measured["boot_s"] = round(elapsed, 3)
                measured["ticks"] = fr["t"]
                break
            if elapsed > budget_s:
                probs.append(f"{want_role} not playable within {budget_s:.0f} s")
                break
    except SessionError as exc:
        probs.append(f"{want_role} failed while booting: {exc.kind}: {exc}")
    finally:
        measured["exit"] = (
            s.exit_info.__dict__ if s.exit_info else s.close(5.0).__dict__
        )
    return probs, measured


def boot_gate(
    prepared: Prepared,
    godot: str,
    work: Path,
    options,
    budget_s: float = 60.0,
    server: bool = True,
    plans: Path | None = None,
) -> GateResult:
    """G_boot: solo (and server) processes become playable within budget_s.

    Args:
        prepared: The prepared copy.
        godot: Godot binary.
        work: Folder for the boot runs.
        options: options(name, folder) -> SessionOptions.
        budget_s: Seconds from process start (PF-4: 60).
        server: Also boot the server role.
        plans: The plan folder passed as --plan-dir, or None.

    Returns:
        The gate's verdict.
    """
    probs: list[str] = []
    measured: dict = {}
    roles = [("solo", ("--role=solo", "--variation=1"))]
    if server:
        roles.append(("server", ("--role=server", "--port=47011", "--variation=1")))
    for role, args in roles:
        if plans is not None:
            args = (*args, f"--plan-dir={plans}")
        folder = work / f"boot-{role}"
        spec = GameSpec(prepared.game_dir, args, godot)
        p, m = boot_once(spec, options(role, folder), budget_s, role)
        probs += p
        measured[role] = m
    return GateResult("boot", not probs, probs, measured)
