"""QA harness core: prepare a game copy with the probe inserted, launch Godot headless in
lockstep, and exchange signed frames with the probe.

Framing: 4-byte big-endian length N, then a 32-byte HMAC-SHA256 of the payload, then the
JSON payload (N - 32 bytes). Every message in both directions is signed with a per-run key.
"""

import hashlib
import hmac
import json
import os
import random
import re
import shutil
import socket
import struct
import subprocess
import time
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GODOT = os.path.join(ROOT, "vendor/godot-4.7.2/Godot.app/Contents/MacOS/Godot")
PROBE_SRC = os.path.join(ROOT, "probe/qa_probe.gd")


def memory_free_pct():
    out = subprocess.run(
        ["memory_pressure"], check=False, capture_output=True, text=True
    ).stdout
    m = re.search(r"System-wide memory free percentage:\s*(\d+)%", out)
    return int(m.group(1)) if m else -1


def memgate(floor=30, wait_s=0, poll_s=20):
    """Return the free percentage once it is at or above floor; raise if it never gets there."""
    t0 = time.time()
    while True:
        pct = memory_free_pct()
        if pct >= floor:
            return pct
        if time.time() - t0 >= wait_s:
            raise RuntimeError(f"memory free {pct}% below floor {floor}%")
        time.sleep(poll_s)


def _copytree(src, dst):
    def ignore(d, names):
        return [n for n in names if n in (".godot", "__pycache__")]

    shutil.copytree(src, dst, ignore=ignore)


NATIVE_LIB = os.path.join(ROOT, "probe/native/libqacore.dylib")


def add_native_core(game_dir, folder, name):
    """Copy the native core next to the probe and declare it as a GDExtension."""
    shutil.copy(NATIVE_LIB, os.path.join(game_dir, folder, "libqacore.dylib"))
    with open(os.path.join(game_dir, folder, name + ".gdextension"), "w") as f:
        f.write(
            '[configuration]\n\nentry_symbol = "qa_core_init"\ncompatibility_minimum = "4.7"\nreloadable = false\n\n'
            f'[libraries]\n\nmacos.debug = "res://{folder}/libqacore.dylib"\nmacos.release = "res://{folder}/libqacore.dylib"\n'
            f'linux.debug.x86_64 = "res://{folder}/libqacore.so"\nlinux.release.x86_64 = "res://{folder}/libqacore.so"\n'
        )


def insert_probe(game_dir, rng):
    """Copy the probe under a random folder and name and put it first in [autoload]."""
    folder = "_" + "".join(
        rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(10)
    )
    name = "N" + "".join(
        rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(11)
    )
    os.makedirs(os.path.join(game_dir, folder))
    shutil.copy(PROBE_SRC, os.path.join(game_dir, folder, name + ".gd"))
    with open(os.path.join(game_dir, folder, name + ".tscn"), "w") as f:
        f.write(
            "[gd_scene load_steps=2 format=3]\n\n"
            f'[ext_resource type="Script" path="res://{folder}/{name}.gd" id="1"]\n\n'
            f'[node name="{name}" type="Node"]\nscript = ExtResource("1")\n'
        )
    pg = os.path.join(game_dir, "project.godot")
    text = Path(pg).read_text()
    entry = f'{name}="*res://{folder}/{name}.tscn"\n'
    if "[autoload]" in text:
        text = (
            text.replace("[autoload]\n\n", "[autoload]\n\n" + entry, 1)
            if "[autoload]\n\n" in text
            else text.replace("[autoload]\n", "[autoload]\n" + entry, 1)
        )
    else:
        text += "\n[autoload]\n\n" + entry
    Path(pg).write_text(text)
    return folder, name


def prepare_game(
    src_project, dst, seed=None, overrides=None, import_timeout=1800, log=None
):
    """Fresh copy of the project with the probe inserted, then a headless import."""
    rng = random.Random(seed)
    if os.path.exists(dst):
        raise RuntimeError(f"{dst} exists")
    _copytree(src_project, dst)
    folder, name = insert_probe(dst, rng)
    if overrides:
        with open(os.path.join(dst, "override.cfg"), "w") as f:
            for section, kv in overrides.items():
                f.write(f"[{section}]\n\n")
                f.writelines(f"{k}={v}\n" for k, v in kv.items())
                f.write("\n")
    t0 = time.time()
    with open(log or os.devnull, "w") as lf:
        subprocess.run(
            [GODOT, "--headless", "--path", dst, "--import"],
            check=False,
            stdout=lf,
            stderr=subprocess.STDOUT,
            timeout=import_timeout,
        )
    return {
        "dir": dst,
        "probe_folder": folder,
        "probe_name": name,
        "import_s": time.time() - t0,
    }


class ProbeError(Exception):
    pass


class Session:
    """One Godot process in lockstep with its probe."""

    def __init__(
        self,
        game_dir,
        user_args=(),
        log_path=None,
        fixed_fps=60,
        extra_args=(),
        timeout=60,
        env_extra=None,
    ):
        self.key = os.urandom(32)
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        port = self.srv.getsockname()[1]
        env = dict(os.environ)
        env["QA_PROBE_PORT"] = str(port)
        env["QA_PROBE_KEY"] = self.key.hex()
        env.update(env_extra or {})
        cmd = [GODOT, "--headless"]
        if fixed_fps:
            cmd += ["--fixed-fps", str(fixed_fps)]
        cmd += list(extra_args) + ["--path", game_dir, "--"] + list(user_args)
        self.log = open(log_path or os.devnull, "w")  # noqa: SIM115 - The stream stays open for the owning process.
        self.t_start = time.time()
        self.proc = subprocess.Popen(
            cmd, env=env, stdout=self.log, stderr=subprocess.STDOUT
        )
        self.srv.settimeout(timeout)
        try:
            self.sock, _ = self.srv.accept()
        except TimeoutError:
            self.kill()
            raise ProbeError("probe did not connect")
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(timeout)
        self.hello = self._recv().get("hello")
        self.t_connected = time.time()
        self.frame = self._recv()  # first observation (start of the first physics tick)
        self.rtt = []
        self.n_msgs = 0

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ProbeError("probe closed the connection")
            buf += chunk
        return buf

    def _recv(self):
        n = struct.unpack(">I", self._recv_exact(4))[0]
        data = self._recv_exact(n)
        mac, payload = data[:32], data[32:]
        if not hmac.compare_digest(
            mac, hmac.new(self.key, payload, hashlib.sha256).digest()
        ):
            raise ProbeError("bad signature from probe")
        return json.loads(payload)

    def _send(self, obj):
        payload = json.dumps(obj, separators=(",", ":")).encode()
        mac = hmac.new(self.key, payload, hashlib.sha256).digest()
        self.sock.sendall(struct.pack(">I", len(payload) + 32) + mac + payload)

    def step(self, run=1, inputs=(), dev=(), observe=None, queries=()):
        """Run `run` ticks with the given input timeline, return the next frame."""
        t_prev = self.frame["t"]
        cmd = {
            "run": int(run),
            "inputs": list(inputs),
            "dev": list(dev),
            "observe": observe if observe is not None else {"census": True},
            "queries": list(queries),
        }
        t0 = time.perf_counter()
        self._send(cmd)
        fr = self._recv()
        self.rtt.append(time.perf_counter() - t0)
        self.n_msgs += 1
        if fr["t"] != t_prev + int(run):
            raise ProbeError(
                f"lockstep broken: expected tick {t_prev + int(run)}, got {fr['t']}"
            )
        self.frame = fr
        return fr

    def close(self, wait=20):
        try:
            self._send({"quit": True})
        except Exception:  # noqa: BLE001, S110 - Best-effort cleanup or optional evidence.
            pass
        try:
            self.proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            self.kill()
        for s in (getattr(self, "sock", None), self.srv):
            try:
                s.close()
            except Exception:  # noqa: BLE001, S110 - Best-effort cleanup or optional evidence.
                pass
        self.log.close()
        return self.proc.returncode

    def kill(self):
        try:
            self.proc.kill()
            self.proc.wait(timeout=10)
        except Exception:  # noqa: BLE001, S110 - Best-effort cleanup or optional evidence.
            pass
