"""One trial of this task as the platform runs it, end to end in local containers (development tooling, never shipped).

usage: python -I scripts/pipeline/simulate_trial.py NAME [--tree DIR | --solution] [--turn SCRIPT]
           [--payload SRC=DEST ...] [--hold S] [--gap S] [--no-egress] [--hooks fsmaint|none]
           [--collect fsmaint|legacy|none] [--release R] [--build] [--no-verify] [--keep] [--no-lock]

In order, as Harbor runs a trial with a separate verifier (ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md):
1. The agent image starts with no network. The addresses of the net check's hosts are looked up first, in a
   throwaway container, and given to it in /etc/hosts, since on the platform they resolve during set-up.
   The set-up hooks of task.toml run as root, with the inputs staged between them (the agent's own set-up).
2. The turn: one exec session as `dev`, as the agent's own. The test tree replaces /app/harfbuzz's files, its
   .git kept (--tree; --solution runs solution/solve.sh instead, as the oracle does; neither keeps the shipped
   tree). The turn script runs from /app/harfbuzz, and the session waits --hold seconds before it ends.
3. Egress returns (`docker network connect bridge`), unless --no-egress (the platform fix: no egress before
   collection). Then --gap seconds pass, as Harbor moves the agent's logs.
4. The collect hook runs as root: the sweep from task.toml (fsmaint), round 1's inline kill (legacy), or none.
5. /app/harfbuzz and /var/lib/fsmaint/out are packed with GNU tar in the container (`tar -czf ... -C <dir> .` as
   root, as Harbor packs an artifact; exit 1 with only "file changed as we read it" is accepted, as Harbor does),
   then unpacked in another container with Python's tarfile.extractall(..., filter="data"), as Harbor's worker
   does at the pinned harbor: the first member the filter refuses ends the extraction, and what arrived is
   what goes on. The arrived trees stay in a Docker volume (Linux file system semantics, as on the worker).
6. sweep_check.py runs on what arrived, then the verifier image (no network; tree and out folder mounted
   read-only, an absent one not mounted; /logs/verifier made 0777 as Harbor does, and copied out after the run).

WORK/sim/NAME/ ends up holding result.json (the summary), turn.log, collect.log, agent/ (the agent side's records
from /var/lib/fsmaint, without the copies), transfer.json, sweep_check.json and verifier/ (reward and metrics).
The archives and the volume are removed unless --keep; every container is removed.

Every container runs with --memory=4g under the shared heavy-job lock (spike.heavy; --no-lock when the caller
holds it). run_trial() is what spike.py's "trial" operation and `milestone --through-trial` call.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spike  # our own module, found beside this file

TASK = spike.TASK
SIM = spike.WORK / "sim"
AGENT_IMAGE = "hbfp-agent:trial"
VERIFIER_PLATFORM = "linux/amd64"
HOSTS = ("github.com", "codeload.github.com", "pypi.org")  # fsmaint-netcheck's
WORK_LIMIT_SECONDS = 34560  # task.toml's agent timeout_sec, as the hooks have it
LIB = "/usr/local/lib/fsmaint"
LEGACY_COLLECT = (
    'alive() { for w in -u -U; do timeout 10 pgrep "$w" dev -r R,S,D,T,t >/dev/null 2>&1; [ $? -eq 1 ] || '
    'return 0; done; return 1; }; end=$(( $(date +%s) + 60 )); while alive; do [ "$(date +%s)" -lt "$end" ] '
    "|| exit 1; timeout 10 setpriv --reuid=dev --regid=dev --clear-groups kill -9 -1 >/dev/null 2>&1; "
    "timeout 10 pkill -KILL -u dev >/dev/null 2>&1; timeout 10 pkill -KILL -U dev >/dev/null 2>&1; "
    "sleep 0.1; done"
)
UNPACK = r"""
import json, os, sys, tarfile

def count(top):
    entries = 0
    for _root, dirs, files in os.walk(top):
        entries += len(dirs) + len(files)
    return entries

report = {}
for name, dest in (("tree", "/arrived/tree"), ("out", "/arrived/out"), ("state", "/x/agent")):
    src = f"/x/{name}.tar.gz"
    if not os.path.exists(src):
        report[name] = {"archive": False}
        continue
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(src, "r:gz") as tar:
        members = tar.getmembers()
    error = None
    with tarfile.open(src, "r:gz") as tar:
        try:
            tar.extractall(dest, filter="data")
        except Exception as exc:  # what Harbor's worker logs and goes on from
            error = f"{exc.__class__.__name__}: {exc}"
    report[name] = {
        "archive": True,
        "members": len(members) - 1,
        "error": error,
        "arrived_entries": count(dest),
    }
json.dump(report, open("/x/transfer-unpack.json", "w"), indent=1)
"""
RESOLVE = (
    "import json, socket\n"
    "found = {}\n"
    f"for host in {HOSTS!r}:\n"
    "    try:\n"
    "        found[host] = sorted({i[4][0] for i in socket.getaddrinfo(host, 443, socket.AF_INET, "
    "socket.SOCK_STREAM)})[:2]\n"
    "    except OSError:\n"
    "        found[host] = []\n"
    "print(json.dumps(found))\n"
)


def docker(
    *args: str, timeout: float | None = None, check: bool = False, **kw
) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], timeout=timeout, check=check, **kw)


def bounded(image: str, *args: str, platform: str | None = None) -> list[str]:
    """A `docker run` of one of our images: removed when it ends, labelled, 4 GiB of memory."""
    return [
        "run", "--rm", "--memory=4g", "--memory-swap=4g", "--label", spike.LABEL,
        *(["--platform", platform] if platform else []), *args, image,
    ]  # fmt: skip


def safe_name(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,62}", name):
        raise SystemExit(
            f"trial name {name!r}: use lowercase letters, digits, '.', '_' and '-'"
        )
    return name


def resolve_hosts(image: str) -> dict[str, list[str]]:
    """The addresses of the net check's hosts, looked up in a throwaway container with network."""
    result = docker(
        *bounded(image, "--network", "bridge", "--entrypoint", "/usr/bin/python3"),
        "-I",
        "-c",
        RESOLVE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        found = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        found = {}
    return {host: list(found.get(host) or []) for host in HOSTS}


def build_images(
    agent_image: str,
    verifier_image: str,
    platform: str | None,
    agent: bool = True,
    verifier: bool = True,
) -> None:
    """The agent image from environment/ (this machine's platform) and the verifier image from tests/ (for
    `platform`); the key staged first (fsmaint_key.py). The caller holds the heavy lock."""
    import fsmaint_key

    fsmaint_key.stage_key()
    for tag, context, plat, wanted in (
        (agent_image, TASK / "environment", None, agent),
        (verifier_image, TASK / "tests", platform, verifier),
    ):
        if not wanted:
            continue
        started = time.time()
        cmd = ["docker", "build", "-t", tag, "--label", spike.LABEL]
        if plat:
            cmd += ["--platform", plat]
        subprocess.run([*cmd, str(context)], check=True)
        spike.log_event(event="image", tag=tag, seconds=round(time.time() - started, 1))


def run_trial(
    name: str,
    tree: Path | None = None,
    solution: bool = False,
    turn: Path | None = None,
    payloads: list[tuple[Path, str]] | None = None,
    hold: float = 4.0,
    gap: float = 6.0,
    egress: bool = True,
    hooks: str = "fsmaint",
    collect: str = "fsmaint",
    release: str = "15.2.0",
    agent_image: str = AGENT_IMAGE,
    verifier_image: str | None = None,
    platform: str | None = VERIFIER_PLATFORM,
    verify: bool = True,
    keep: bool = False,
    limit_in: float | None = None,
    verifier_args: list[str] | None = None,
) -> dict:
    """One simulated trial (the module's docstring); its summary, also in WORK/sim/NAME/result.json. The caller
    holds the heavy lock."""
    name = safe_name(name)
    verifier_image = verifier_image or spike.verifier_tag(platform)
    here = SIM / name
    if here.exists():
        raise SystemExit(f"{here} exists: pick another name, or move it away first")
    here.mkdir(parents=True)
    agent, volume = f"hbfp-sim-{name}", f"hbfp-sim-{name}-arrived"
    result: dict = {"name": name, "started": time.time(), "steps": {}}
    steps = result["steps"]

    def step(label: str, started: float, **fields) -> None:
        steps[label] = {"seconds": round(time.time() - started, 2), **fields}

    def exec_in(user: str, command: list[str], log: Path, seconds: float) -> int | None:
        with log.open("ab") as out:
            out.write(f"\n$ ({user}) {' '.join(command)[:300]}\n".encode())
            out.flush()
            try:
                return docker("exec", "--user", user, agent, *command, stdout=out, stderr=subprocess.STDOUT,
                              timeout=seconds).returncode  # fmt: skip
            except subprocess.TimeoutExpired:
                return None

    try:
        t = time.time()
        hosts = resolve_hosts(agent_image)
        add_hosts = [
            f"--add-host={host}:{addr}"
            for host, addrs in hosts.items()
            for addr in addrs[:1]
        ]
        step("resolve", t, hosts=hosts)
        # 1. The agent image, no network; the set-up hooks as root, the inputs staged between them.
        t = time.time()
        docker(
            "run", "-d", "--name", agent, "--network", "none", "--memory=4g", "--memory-swap=4g", "--cpus=4",
            "--label", spike.LABEL, *add_hosts, "--user", "root", "--entrypoint", "sleep", agent_image, "infinity",
            check=True, capture_output=True,
        )  # fmt: skip
        log = here / "setup.log"
        codes = {}
        if hooks == "fsmaint":
            codes["setup_begin"] = exec_in("root", [f"{LIB}/fsmaint-reserve"], log, 120)
        if limit_in is not None and hooks == "fsmaint":
            # a capped run, shortened: the start of the work recorded so that its time limit falls
            # `limit_in` seconds from now (the net check and the sweep read it; nothing else changes)
            exec_in(
                "root",
                [
                    "sh",
                    "-c",
                    (
                        "/usr/bin/python3 -I -c 'import time; print(repr(time.time() - "
                        f"{WORK_LIMIT_SECONDS} + {float(limit_in)}))' > /var/lib/fsmaint/work-started"
                    ),
                ],
                log,
                60,
            )
        if tree is not None:
            docker(
                "cp",
                str(tree.resolve()),
                f"{agent}:/opt/sim-tree",
                check=True,
                capture_output=True,
            )
            exec_in("root", ["chown", "-R", "dev:dev", "/opt/sim-tree"], log, 300)
        if solution:
            docker(
                "cp",
                str(TASK / "solution"),
                f"{agent}:/solution",
                check=True,
                capture_output=True,
            )
            exec_in("root", ["chmod", "-R", "a+rX", "/solution"], log, 60)
        for src, dest in payloads or []:
            docker(
                "cp",
                str(src.resolve()),
                f"{agent}:{dest}",
                check=True,
                capture_output=True,
            )
            exec_in("root", ["chown", "-R", "dev:dev", dest], log, 300)
        if turn is not None:
            docker(
                "cp",
                str(turn.resolve()),
                f"{agent}:/opt/sim-turn.sh",
                check=True,
                capture_output=True,
            )
            exec_in("root", ["chmod", "0755", "/opt/sim-turn.sh"], log, 60)
        if hooks == "fsmaint":
            codes["setup_complete"] = exec_in(
                "root", [f"{LIB}/fsmaint-reserve", "--netcheck"], log, 120
            )
        step("setup", t, codes=codes)
        # 2. The turn, one exec session as `dev`.
        t = time.time()
        script = "\n".join(
            [
                "set -u",
                "cd /app/harfbuzz",
                "if [ -d /opt/sim-tree ]; then",
                "  find /app/harfbuzz -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +",
                "  cp -a /opt/sim-tree/. /app/harfbuzz/",
                "fi",
                "if [ -f /solution/solve.sh ]; then bash /solution/solve.sh; fi",
                "if [ -f /opt/sim-turn.sh ]; then bash /opt/sim-turn.sh; fi",
                f"sleep {hold}",
            ]
        )
        code = exec_in("dev", ["bash", "-c", script], here / "turn.log", hold + 900)
        turn_ended = time.time()
        step("turn", t, code=code, ended_at=turn_ended)
        # 3. Egress returns; the gap before collection.
        t = time.time()
        if egress:
            joined = docker("network", "connect", "bridge", agent, capture_output=True)
            if joined.returncode:  # a container on `none` must leave it first
                docker("network", "disconnect", "none", agent, capture_output=True)
                docker(
                    "network",
                    "connect",
                    "bridge",
                    agent,
                    check=True,
                    capture_output=True,
                )
        time.sleep(gap)
        step("egress", t, restored=egress, restored_at=t if egress else None)
        # 4. The collect hook, as root.
        t = time.time()
        log = here / "collect.log"
        if collect == "fsmaint":
            code = exec_in("root", [f"{LIB}/fsmaint-sweep"], log, 600)
        elif collect == "legacy":
            code = exec_in("root", ["bash", "-c", LEGACY_COLLECT], log, 120)
        else:
            code = None
        # what of `dev` is still alive (a thread not exited) once the hook has run
        alive = docker(
            "exec", "--user", "root", agent, "sh", "-c",
            "d=$(id -u dev); for t in /proc/[0-9]*/task/[0-9]*; do "
            "u=$(awk '/^Uid:/ {print $2}' $t/status 2>/dev/null); s=$(awk '/^State:/ {print $2}' $t/status 2>/dev/null); "
            '[ "$u" = "$d" ] && [ "$s" != Z ] && [ "$s" != X ] && echo "$t $s $(cat ${t%/task/*}/comm 2>/dev/null)"; '
            "done; true",
            capture_output=True, text=True, timeout=120,
        ).stdout.split("\n")  # fmt: skip
        alive = [line for line in alive if line.strip()]
        step(
            "collect",
            t,
            hook=collect,
            code=code,
            dev_threads_after=len(alive),
            dev_threads=alive[:20],
        )
        # 5. Packed in the container as Harbor packs an artifact, copied out, unpacked as its worker does.
        t = time.time()
        packed = {}
        for label, path in (("tree", "/app/harfbuzz"), ("out", "/var/lib/fsmaint/out")):
            archive = f"/tmp/runtime_download_{label}.tar.gz"
            res = docker(
                "exec", "--user", "root", agent, "bash", "-c",
                f'[ -d {path} ] || exit 99; tar -czf {archive} -C {path} .',
                capture_output=True, text=True, timeout=600,
            )  # fmt: skip
            changed_only = res.returncode == 1 and all(
                line.strip().endswith("file changed as we read it")
                for line in res.stderr.splitlines()
                if line.strip()
            )
            ok = res.returncode == 0 or changed_only
            packed[label] = {
                "code": res.returncode,
                "stderr": res.stderr[-500:],
                "accepted": ok,
            }
            if ok:
                docker(
                    "cp",
                    f"{agent}:{archive}",
                    str(here / f"{label}.tar.gz"),
                    check=True,
                    capture_output=True,
                )
        docker(
            "exec", "--user", "root", agent, "sh", "-c",
            "tar -czf /tmp/state.tar.gz -C /var/lib/fsmaint --exclude=./copy --exclude=./room --exclude=./inodes .",
            capture_output=True, timeout=300,
        )  # fmt: skip
        docker(
            "cp",
            f"{agent}:/tmp/state.tar.gz",
            str(here / "state.tar.gz"),
            capture_output=True,
        )
        docker("rm", "-f", agent, capture_output=True)
        docker(
            "volume",
            "create",
            "--label",
            spike.LABEL,
            volume,
            check=True,
            capture_output=True,
        )
        unpack = docker(
            *bounded(agent_image, "--network", "none", "--user", "root", "-v", f"{volume}:/arrived",
                     "-v", f"{here}:/x", "--entrypoint", "/usr/bin/python3"),
            "-I", "-c", UNPACK, capture_output=True, text=True, timeout=900,
        )  # fmt: skip
        try:
            unpacked = json.loads((here / "transfer-unpack.json").read_text())
        except (OSError, ValueError):
            unpacked = {"error": unpack.stderr[-1000:]}
        transfer = {"packed": packed, "unpacked": unpacked}
        (here / "transfer.json").write_text(json.dumps(transfer, indent=1))
        step("transfer", t)
        # 6. What arrived: the sweep's reader, then the verifier.
        mounts = []
        for label, target in (
            ("tree", "/app/harfbuzz"),
            ("out", "/var/lib/fsmaint/out"),
        ):
            if unpacked.get(label, {}).get("archive"):
                mounts += [
                    "--mount",
                    f"type=volume,src={volume},dst={target},volume-subpath={label},readonly",
                ]
        t = time.time()
        res = docker(
            *bounded(verifier_image, "--network", "none", *mounts, "-v",
                     f"{TASK / 'tests' / 'sweep_check.py'}:/opt/sweep/sweep_check.py:ro", platform=platform),
            "python3", "-I", "-B", "/opt/sweep/sweep_check.py", "/app/harfbuzz", "/var/lib/fsmaint/out",
            "/tests/private/fsmaint.key", capture_output=True, text=True, timeout=900,
        )  # fmt: skip
        try:
            checked = json.loads(res.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            checked = {"error": res.stderr[-1000:]}
        (here / "sweep_check.json").write_text(json.dumps(checked, indent=1))
        step(
            "sweep_check", t, fault=checked.get("fault"), refused=checked.get("refused")
        )
        if verify:
            t = time.time()
            verified = spike.run_verifier(
                None,
                name,
                release,
                platform,
                mounts=mounts,
                image=verifier_image,
                logs=here / "verifier",
                extra=verifier_args,
            )
            step(
                "verifier", t, code=verified.get("code"), reward=verified.get("reward")
            )
            result["reward"] = verified.get("reward")
            result["reward_json"] = verified.get("reward_json")
        result["sweep_check"] = {
            key: checked.get(key) for key in ("fault", "refused", "notes")
        }
        result["transfer"] = {
            label: {
                key: (unpacked.get(label) or {}).get(key)
                for key in ("members", "arrived_entries", "error")
            }
            for label in ("tree", "out")
        }
    finally:
        docker("rm", "-f", agent, capture_output=True)
        if not keep:
            docker("volume", "rm", "-f", volume, capture_output=True)
            for label in ("tree", "out", "state"):
                archive = here / f"{label}.tar.gz"
                if archive.is_file():
                    archive.unlink()
        result["seconds"] = round(time.time() - result["started"], 1)
        (here / "result.json").write_text(json.dumps(result, indent=1))
        spike.log_event(event="trial", name=name, reward=result.get("reward"), seconds=result["seconds"],
                        fault=(result.get("sweep_check") or {}).get("fault"))  # fmt: skip
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in ("name", "reward", "sweep_check", "transfer", "seconds")
            }
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("name")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--tree",
        type=Path,
        help="a tree put in place of /app/harfbuzz's files during the turn",
    )
    group.add_argument(
        "--solution",
        action="store_true",
        help="the turn runs solution/solve.sh (the oracle)",
    )
    parser.add_argument(
        "--turn",
        type=Path,
        help="a shell script run as dev from /app/harfbuzz during the turn",
    )
    parser.add_argument(
        "--payload",
        action="append",
        default=[],
        help="SRC=DEST copied in before the turn",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=4.0,
        help="seconds the session waits before it ends",
    )
    parser.add_argument(
        "--gap", type=float, default=6.0, help="seconds from egress to the collect hook"
    )
    parser.add_argument(
        "--no-egress",
        action="store_true",
        help="egress never returns before collection",
    )
    parser.add_argument("--hooks", choices=("fsmaint", "none"), default="fsmaint")
    parser.add_argument(
        "--collect", choices=("fsmaint", "legacy", "none"), default="fsmaint"
    )
    parser.add_argument("--release", default="15.2.0")
    parser.add_argument("--agent-image", default=AGENT_IMAGE)
    parser.add_argument("--verifier-image")
    parser.add_argument(
        "--platform", default=VERIFIER_PLATFORM, help="the verifier image's platform"
    )
    parser.add_argument("--build", action="store_true", help="build both images first")
    parser.add_argument(
        "--no-verify", action="store_true", help="stop after sweep_check.py"
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the archives and the arrived volume"
    )
    parser.add_argument(
        "--no-lock", action="store_true", help="the caller holds the heavy lock"
    )
    parser.add_argument(
        "--limit-in",
        type=float,
        help="a capped run, shortened: the work's time limit falls this many seconds after set-up",
    )
    args = parser.parse_args()
    payloads = []
    for item in args.payload:
        src, _, dest = item.partition("=")
        if not dest.startswith("/"):
            raise SystemExit(
                f"--payload {item}: DEST must be an absolute path in the container"
            )
        payloads.append((Path(src), dest))
    verifier_image = args.verifier_image or spike.verifier_tag(args.platform)

    def go() -> None:
        if args.build:
            build_images(args.agent_image, verifier_image, args.platform)
        run_trial(
            args.name, tree=args.tree, solution=args.solution, turn=args.turn, payloads=payloads, hold=args.hold,
            gap=args.gap, egress=not args.no_egress, hooks=args.hooks, collect=args.collect, release=args.release,
            agent_image=args.agent_image, verifier_image=verifier_image, platform=args.platform,
            verify=not args.no_verify, keep=args.keep, limit_in=args.limit_in,
        )  # fmt: skip

    spike.WORK.mkdir(parents=True, exist_ok=True)
    if args.no_lock:
        go()
    else:
        with spike.heavy(f"trial {args.name}"):
            go()


if __name__ == "__main__":
    main()
