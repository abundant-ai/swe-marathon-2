"""One game process and its telemetry link.

Lockstep (Session): the game runs headless under --fixed-fps 60 and the telemetry node
blocks at every observation tick until the kit sends the next command, so the kit owns
the clock and a run is independent of how fast the machine is.

Real time (RealtimeSession): the game runs freely (used for clients of an online session);
a reader thread collects the heartbeat the telemetry node sends every tick, and frames at
the requested rate; commands take effect at the next tick.

Errors are SessionError with a short `kind`:
  "no_link"     the game never connected its telemetry (it did not start, or stalled
                before the engine finished starting)
  "closed"      the link closed: the process exited or crashed
  "limit"       the kit stopped the process for a resource limit (see ExitInfo.violation)
  "stalled"     no frame within the allowed time (a hang, or telemetry kept from running)
  "out_of_step" a frame at an unexpected tick, or with a different tick count
  "gone"        the telemetry node left the scene tree
  "unsigned", "bad_message"   a message that fails the link's checks
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .link import Link, LinkError
from .procs import ExitInfo, Limits, Proc

LOCKSTEP_FPS = 60


class SessionError(Exception):
    """A game session failed; `kind` is one of the kinds in the module docstring."""

    def __init__(self, kind: str, message: str) -> None:
        """Create the error.

        Args:
            kind: Short failure kind (see the module docstring).
            message: Detail for logs and reports.
        """
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class GameSpec:
    """What to run.

    Attributes:
        game_dir: A prepared project (telemetry inserted, imported).
        args: Arguments after "--" (the game's own command line, such as --role=solo).
        godot: Absolute path of the Godot binary.
        mode: "lockstep" or "realtime".
        engine_args: Extra engine arguments placed before --path.
    """

    game_dir: Path
    args: tuple[str, ...]
    godot: str
    mode: str = "lockstep"
    engine_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionOptions:
    """How a session is started and supervised.

    Attributes:
        home: Fresh folder used as the process's home (its user:// data lands under it).
        log_path: File for the game's output, or None.
        limits: Resource limits of the process.
        boot_s: Seconds from process start to the first frame (lockstep) or the
            telemetry hello (real time).
        step_s: Seconds allowed for a lockstep step, plus step_per_tick_s per tick run.
        step_per_tick_s: See step_s.
        env_extra: Extra environment variables for the game.
        cgroup: Linux only: cgroup folder the process joins (see procs.Proc).
        user: Linux only, as root: (uid, gid) to run the game as.
        before_start: Called just before the process starts (for example to wait for
            free memory on a shared machine).
    """

    home: Path
    log_path: Path | None = None
    limits: Limits = field(default_factory=Limits)
    boot_s: float = 60.0
    step_s: float = 30.0
    step_per_tick_s: float = 0.25
    env_extra: dict[str, str] = field(default_factory=dict)
    cgroup: Path | None = None
    user: tuple[int, int] | None = None
    before_start: Callable[[], None] | None = None


def game_env(home: Path, extra: dict[str, str]) -> dict[str, str]:
    """The environment of a game process: a small fixed set plus extra.

    The home folder holds everything the game writes to user:// on both platforms
    (macOS: $HOME/Library/Application Support; Linux: $XDG_DATA_HOME).

    Args:
        home: The process's home folder (created by the caller).
        extra: Variables added last (the telemetry settings, other switches).

    Returns:
        The complete environment.
    """
    tmp = home / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "LANG": "C.UTF-8",
    }
    if sys.platform.startswith("linux"):
        env.update(
            XDG_DATA_HOME=str(home / ".local/share"),
            XDG_CONFIG_HOME=str(home / ".config"),
            XDG_CACHE_HOME=str(home / ".cache"),
        )
    env.update(extra)
    return env


def engine_argv(spec: GameSpec) -> list[str]:
    """The full command line of a game process.

    Args:
        spec: What to run.

    Returns:
        [godot, --headless, (--fixed-fps 60 in lockstep), engine args, --path, dir, --, args].
    """
    argv = [spec.godot, "--headless"]
    if spec.mode == "lockstep":
        argv += ["--fixed-fps", str(LOCKSTEP_FPS)]
    argv += list(spec.engine_args)
    argv += ["--path", str(Path(spec.game_dir).resolve()), "--", *spec.args]
    return argv


class _Base:
    """Start-up shared by both modes: listen, start the process, accept, read hello."""

    def __init__(self, spec: GameSpec, opts: SessionOptions) -> None:
        """Start the game and wait for its telemetry hello.

        Args:
            spec: What to run.
            opts: How to start and supervise it.

        Raises:
            SessionError: "no_link", "closed", "limit", "unsigned" or "bad_message"
                when the game does not get as far as its hello.
        """
        self.spec = spec
        self.opts = opts
        self.key = os.urandom(32)
        self.exit_info: ExitInfo | None = None
        self.link: Link | None = None
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        opts.home.mkdir(parents=True, exist_ok=True)
        extra = dict(opts.env_extra)
        extra.update(
            QA_TELEMETRY_PORT=str(port),
            QA_TELEMETRY_KEY=self.key.hex(),
            QA_TELEMETRY_MODE=spec.mode,
        )
        self.gate_wait_s = 0.0
        if opts.before_start:
            t_gate = time.monotonic()
            opts.before_start()
            self.gate_wait_s = time.monotonic() - t_gate
        self.t_start = time.monotonic()
        self.proc = Proc(
            engine_argv(spec),
            game_env(opts.home, extra),
            spec.game_dir,
            opts.limits,
            opts.log_path,
            home=opts.home,
            cgroup=opts.cgroup,
            user=opts.user,
        )
        try:
            sock = self._accept(listener, opts.boot_s)
        finally:
            listener.close()
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.link = Link(sock, self.key)
        self.hello = self._recv(self._left(opts.boot_s)).get("hello")
        if not isinstance(self.hello, dict):
            self._fail("bad_message", "the first message was not a hello")

    def _left(self, budget_s: float) -> float:
        """Seconds left of an allowance counted from process start (at least 0.05)."""
        return max(0.05, budget_s - (time.monotonic() - self.t_start))

    def _accept(self, listener: socket.socket, boot_s: float) -> socket.socket:
        """Accept the telemetry connection, giving up when the process ends or boot_s passes."""
        listener.settimeout(0.2)
        while True:
            try:
                sock, _addr = listener.accept()
                return sock
            except TimeoutError:
                pass
            if not self.proc.alive():
                self._fail("closed", "the game ended before its telemetry connected")
            if time.monotonic() - self.t_start > boot_s:
                self._fail("no_link", f"no telemetry connection within {boot_s:.0f} s")

    def _recv(self, timeout_s: float) -> dict:
        """Receive one message, turning link errors into session errors."""
        assert self.link is not None
        try:
            return self.link.recv(timeout_s)
        except LinkError as exc:
            kind = exc.kind
            if kind == "silent":
                kind = "stalled"
            if kind == "closed":
                self.proc.wait(2.0)
            self._fail(kind, str(exc))
        raise AssertionError("unreachable")

    def _fail(self, kind: str, message: str) -> None:
        """Kill the process and raise; a resource-limit kill is reported as "limit"."""
        self.exit_info = self.proc.kill() if self.exit_info is None else self.exit_info
        violation = self.exit_info.violation
        if violation and violation != "killed" and kind in ("closed", "stalled"):
            kind, message = "limit", f"stopped for its {violation} limit ({message})"
        if self.link:
            self.link.close()
        raise SessionError(kind, message)

    def kill(self) -> ExitInfo:
        """Kill the game's process tree now; returns how it ended."""
        if self.exit_info is None:
            self.exit_info = self.proc.kill()
        if self.link:
            self.link.close()
        return self.exit_info

    def close(self, grace_s: float = 5.0) -> ExitInfo:
        """Ask the game to quit, wait up to grace_s, then kill whatever is left."""
        if self.exit_info is not None:
            return self.exit_info
        # Before the game quits: what it started would be orphaned by its exit.
        self.proc.snapshot_tree()
        self.proc.sample_memory(kill=False)
        if self.link:
            try:
                self.link.send({"quit": True})
            except LinkError:
                pass
        self.exit_info = self.proc.close(grace_s)
        if self.link:
            self.link.close()
        return self.exit_info


class Session(_Base):
    """A lockstep game session: the kit advances the game tick by tick."""

    def __init__(self, spec: GameSpec, opts: SessionOptions) -> None:
        """Start the game and wait for its first frame (see _Base).

        Raises:
            SessionError: As _Base, plus "stalled" when no first frame arrives in time.
        """
        super().__init__(spec, opts)
        self.frame = self._recv(self._left(opts.boot_s))
        self._check_frame(self.frame, None)
        self.t_first_frame_s = time.monotonic() - self.t_start

    def _check_frame(self, frame: dict, want_t: int | None) -> None:
        """Fail on a "gone" notice or a frame at the wrong tick."""
        if "gone" in frame:
            self._fail("gone", f"telemetry left the scene tree at tick {frame['gone']}")
        if not isinstance(frame.get("t"), int):
            self._fail("bad_message", "frame without a tick")
        if want_t is not None and frame["t"] != want_t:
            self._fail("out_of_step", f"frame at tick {frame['t']}, expected {want_t}")

    def step(
        self,
        run: int = 1,
        inputs: list[list] | tuple = (),
        dev: list[list] | tuple = (),
        observe: dict | None = None,
        queries: list[dict] | tuple = (),
    ) -> dict:
        """Run the game for `run` ticks and return the frame at the tick after them.

        Args:
            run: Ticks to run (at least 1).
            inputs: [offset, action, strength] triples; offset 0 is the first tick of
                the run. Strength 0 releases the action.
            dev: [command, args] pairs run through the game's DevConsole before the
                first tick; their answers arrive in the returned frame's "dev".
            observe: New observation settings (kept until changed), or None.
            queries: Queries answered in the returned frame's "q".

        Returns:
            The frame (a dict with "t", "ticks", "events", "dev" and what was observed).

        Raises:
            SessionError: On any failure; the process has been killed.
        """
        run = max(1, int(run))
        cmd: dict = {"run": run, "inputs": list(inputs), "dev": list(dev)}
        if observe is not None:
            cmd["observe"] = observe
        if queries:
            cmd["queries"] = list(queries)
        want = self.frame["t"] + run
        try:
            assert self.link is not None
            self.link.send(cmd)
        except LinkError as exc:
            self._fail("closed", str(exc))
        fr = self._recv(self.opts.step_s + self.opts.step_per_tick_s * run)
        self._check_frame(fr, want)
        if fr.get("ticks") != run:
            self._fail(
                "out_of_step", f"frame reports {fr.get('ticks')} ticks, ran {run}"
            )
        self.frame = fr
        return fr


@dataclass
class Heartbeats:
    """What the real-time reader saw of the per-tick heartbeat.

    Attributes:
        first_tick: Tick of the first heartbeat, or None.
        last_tick: Tick of the latest heartbeat, or None.
        count: Heartbeats received.
        skipped: Ticks missing from the sequence (each jump larger than one counts its
            missing ticks).
        max_gap_s: Longest time between two received heartbeats (kit clock).
        gaps: (tick, seconds) of gaps longer than the session's allowance.
    """

    first_tick: int | None = None
    last_tick: int | None = None
    count: int = 0
    skipped: int = 0
    max_gap_s: float = 0.0
    gaps: list[tuple[int, float]] = field(default_factory=list)


class RealtimeSession(_Base):
    """A real-time game session: the game runs freely; a thread collects what it sends."""

    def __init__(
        self, spec: GameSpec, opts: SessionOptions, gap_s: float = 1.0
    ) -> None:
        """Start the game, read its hello, and start collecting heartbeats and frames.

        Args:
            spec: What to run (mode must be "realtime").
            opts: How to start and supervise it.
            gap_s: Longest silence between heartbeats that is not recorded as a gap.

        Raises:
            SessionError: As _Base.
        """
        super().__init__(spec, opts)
        self.gap_s = gap_s
        self.frames: list[dict] = []
        self.beats = Heartbeats()
        self.error: SessionError | None = None
        self._last_rx: float | None = None
        self._mu = threading.Lock()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        """Reader thread: sort messages into heartbeats and frames until the link ends."""
        assert self.link is not None
        while True:
            try:
                msg = self.link.recv(None)
            except LinkError as exc:
                with self._mu:
                    if self.error is None and self.exit_info is None:
                        self.error = SessionError(exc.kind, str(exc))
                return
            now = time.monotonic()
            with self._mu:
                if "hb" in msg:
                    self._beat(int(msg["hb"]), now)
                elif "gone" in msg:
                    self.error = SessionError("gone", "telemetry left the scene tree")
                else:
                    msg["rx_s"] = round(now - self.t_start, 6)
                    self.frames.append(msg)

    def _beat(self, tick: int, now: float) -> None:
        """Account one heartbeat (called with the lock held)."""
        b = self.beats
        if b.last_tick is not None and tick != b.last_tick + 1:
            b.skipped += max(0, tick - b.last_tick - 1)
        if self._last_rx is not None:
            gap = now - self._last_rx
            b.max_gap_s = max(b.max_gap_s, gap)
            if gap > self.gap_s:
                b.gaps.append((tick, round(gap, 3)))
        if b.first_tick is None:
            b.first_tick = tick
        b.last_tick = tick
        b.count += 1
        self._last_rx = now

    def silence_s(self) -> float:
        """Seconds since the last heartbeat arrived (since start when none has)."""
        with self._mu:
            last = self._last_rx if self._last_rx is not None else self.t_start
        return time.monotonic() - last

    def send(self, cmd: dict) -> None:
        """Send a command; it takes effect at the game's next tick.

        Raises:
            SessionError: "closed" when the link is gone.
        """
        try:
            assert self.link is not None
            self.link.send(cmd)
        except LinkError as exc:
            raise SessionError("closed", str(exc)) from exc

    def heartbeat(self) -> Heartbeats:
        """A snapshot of the heartbeat record, counting a silence still going on now.

        Returns:
            A copy of the record; an ongoing silence longer than the allowance is
            included in max_gap_s and gaps (with tick -1).
        """
        silence = self.silence_s()
        with self._mu:
            b = self.beats
            snap = Heartbeats(
                b.first_tick, b.last_tick, b.count, b.skipped, b.max_gap_s, list(b.gaps)
            )
        if silence > self.gap_s:
            snap.max_gap_s = max(snap.max_gap_s, silence)
            snap.gaps.append((-1, round(silence, 3)))
        return snap

    def wait(self, seconds: float) -> None:
        """Let the game run for `seconds` of wall time.

        Heartbeat gaps are recorded, not raised: the caller judges them afterwards
        through heartbeat().

        Raises:
            SessionError: The link failed or the telemetry node left the tree (the
                process has been killed).
        """
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            with self._mu:
                err = self.error
            if err is not None:
                self.exit_info = (
                    self.proc.kill() if self.exit_info is None else self.exit_info
                )
                if self.link:
                    self.link.close()
                violation = self.exit_info.violation
                if violation and violation != "killed" and err.kind == "closed":
                    raise SessionError(
                        "limit", f"stopped for its {violation} limit ({err})"
                    )
                raise err
            time.sleep(min(0.05, max(0.0, end - time.monotonic())))
