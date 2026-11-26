"""Host-side driver for the HarfBuzz forward-port pipeline: bounded Docker jobs under the shared heavy lock.

Development tooling, never shipped. Downloaded code only ever runs inside the pipeline image's containers.
Run with Python 3.11 or later (the repository's venv), as `python -I scripts/pipeline/spike.py <command> ...`.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
PIPE = TASK / "scripts" / "pipeline"
DRIVER = TASK / "tests" / "driver"
CACHE = Path.home() / "Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port"
DL = CACHE / "dl"
WORK = CACHE / "work"
HISTORY = DL / "git" / "harfbuzz"
LOCK = Path(
    "/private/tmp/claude-501/-Users-skylarkoo7-Documents-github-Abundant-harbor-lh/"
    "094b99cf-143c-4e5c-86e7-fdaba6b55775/scratchpad/heavy-docker.lock"
)
IMAGE = "hbfp-pipeline:phaseB"
LABEL = "org.abundant.task=harfbuzz-forward-port"
RELEASES = ("14.3.0", "15.0.0", "15.1.0", "15.2.0")
EVENTS = CACHE / "events.jsonl"


def log_event(**fields: object) -> None:
    """Append one timestamped record to the pipeline's event log."""
    fields["utc"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with EVENTS.open("a") as fh:
        fh.write(json.dumps(fields) + "\n")


def memory_free_pct() -> int:
    """Return the system-wide free memory percentage that macOS's memory_pressure reports."""
    out = subprocess.run(
        ["memory_pressure"], capture_output=True, text=True, check=True
    ).stdout
    match = re.search(r"free percentage:\s*(\d+)%", out)
    return int(match.group(1)) if match else 0


@contextlib.contextmanager
def heavy(
    job: str, poll_s: int = int(os.environ.get("HBFP_POLL_S", "120"))
) -> Iterator[None]:
    """Hold the shared heavy-job lock, taken only while at least 30% of memory is free."""
    while True:
        free = memory_free_pct()
        if free >= 30:
            try:
                LOCK.mkdir()
                break
            except FileExistsError:
                holder = (
                    (LOCK / "owner").read_text().strip()
                    if (LOCK / "owner").exists()
                    else "unknown"
                )
                print(f"lock held ({holder}); retrying in {poll_s}s", file=sys.stderr)
        else:
            print(f"memory free {free}% < 30%; retrying in {poll_s}s", file=sys.stderr)
        time.sleep(poll_s)
    owner = LOCK / "owner"
    started = time.time()
    try:
        owner.write_text(
            f"harfbuzz-forward-port {job} pid={os.getpid()} since={dt.datetime.now(dt.UTC).isoformat()}\n"
        )
        log_event(event="lock", job=job, mem_free_pct=free)
        yield
    finally:
        if owner.exists():
            owner.unlink()
        LOCK.rmdir()
        log_event(
            event="unlock",
            job=job,
            seconds=round(time.time() - started, 1),
            mem_free_pct=memory_free_pct(),
        )


def docker_run(
    args: list[str], *, cpus: int = 6, platform: str | None = None, check: bool = True
) -> int:
    """Run one bounded, labelled, self-removing container of the pipeline image."""
    cmd = [
        "docker",
        "run",
        "--rm",
        "--memory=4g",
        "--memory-swap=4g",
        f"--cpus={cpus}",
        "--label",
        LABEL,
    ]
    if platform:
        cmd += ["--platform", platform]
    cmd += [
        "-v",
        f"{DL}:/dl:ro",
        "-v",
        f"{WORK}:/work",
        "-v",
        f"{DRIVER}:/drv:ro",
        "-v",
        f"{PIPE}:/pipe:ro",
    ]
    cmd += [IMAGE if not platform else f"{IMAGE}-{platform.split('/')[1]}", *args]
    result = subprocess.run(cmd, check=False)
    if check and result.returncode:
        raise SystemExit(f"container failed ({result.returncode}): {' '.join(args)}")
    return result.returncode


def build_context() -> Path:
    """Assemble the pipeline image's build context: Dockerfile, hb_build, wheels (hard links) and their sums."""
    ctx = CACHE / "ctx" / "pipeline"
    (ctx / "wheels").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PIPE / "Dockerfile", ctx / "Dockerfile")
    shutil.copy2(PIPE / "hb_build.sh", ctx / "hb_build.sh")
    sums = []
    for row in (CACHE / "MANIFEST.tsv").read_text().splitlines()[1:]:
        group, rel, _url, _size, sha, _ = row.split("\t")
        if group == "python":
            name = Path(rel).name
            dst = ctx / "wheels" / name
            if not dst.exists():
                os.link(DL / rel, dst)
            sums.append(f"{sha}  wheels/{name}")
    (ctx / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    return ctx


def cmd_image(args: argparse.Namespace) -> None:
    ctx = build_context()
    tag = IMAGE if not args.platform else f"{IMAGE}-{args.platform.split('/')[1]}"
    cmd = ["docker", "build", "-t", tag, "--label", LABEL]
    if args.platform:
        cmd += ["--platform", args.platform]
    with heavy(f"image {tag}"):
        started = time.time()
        subprocess.run([*cmd, str(ctx)], check=True)
        log_event(event="image", tag=tag, seconds=round(time.time() - started, 1))


def stack36() -> list[str]:
    """The 2026-08-12 saturation commits of 14.4.0 (unit 36), oldest first."""
    out = subprocess.run(
        [
            "git",
            "-C",
            str(HISTORY),
            "log",
            "--no-merges",
            "--reverse",
            "--format=%h %ad %s",
            "--date=short",
            "14.3.1..14.4.0",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    pat = re.compile(
        r"saturat|clamp|widen|trust bounded|full-range|full values|scale full",
        re.IGNORECASE,
    )
    return [
        line.split()[0]
        for line in out.splitlines()
        if " 2026-08-12 " in line and pat.search(line)
    ]


def units() -> list[dict[str, str]]:
    rows = (PIPE / "units.tsv").read_text().splitlines()
    head = rows[0].split("\t")
    return [
        dict(zip(head, row.split("\t"), strict=True)) for row in rows[1:] if row.strip()
    ]


def cmd_patches(_: argparse.Namespace) -> None:
    """Export each unit's commits as numbered patches (oldest first), restricted to what the product build
    compiles: src/ without unit tests, generators and the Rust and WebAssembly back ends, plus the meson files."""
    report = []
    for unit in units():
        commits = (
            stack36() if unit["commits"] == "@stack36" else unit["commits"].split()
        )
        dest = WORK / "patches-lib" / unit["unit"]
        dest.mkdir(parents=True, exist_ok=True)
        written = 0
        for i, sha in enumerate(commits):
            cmd = [
                "git",
                "-C",
                str(HISTORY),
                "format-patch",
                "-1",
                "--stdout",
                sha,
                "--",
                "src",
                "meson.build",
                "meson_options.txt",
                ":(exclude)src/test-*",
                ":(exclude)src/gen-*",
                ":(exclude)src/rust",
                ":(exclude)src/wasm",
            ]
            for attempt in range(
                4
            ):  # blobs arrive over the network on demand; retry transient failures
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
                if result.returncode == 0:
                    break
                time.sleep(5 * (attempt + 1))
            result.check_returncode()
            patch = result.stdout
            if "\ndiff --git " in patch:
                (dest / f"{i:03d}-{sha}.patch").write_text(patch)
                written += 1
        report.append(
            {"unit": unit["unit"], "commits": len(commits), "patches": written}
        )
    (WORK / "patches-lib" / "index.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


def cmd_revert_check(_: argparse.Namespace) -> None:
    """S6: reverse-apply every unit's patches on its release, without building."""
    with heavy("revert-check"):
        docker_run(
            [
                "sh",
                "/pipe/revert_check.sh",
                "/work/patches-lib",
                "/work/s6-revert-check.tsv",
            ],
            cpus=2,
        )
    print((WORK / "s6-revert-check.tsv").read_text())


def do_build(
    bid: str,
    release: str,
    unit: str | None = None,
    jobs: int = 4,
    cpus: int = 6,
    ragel: str = "on",
    platform: str | None = None,
    meson_extra: str = "",
) -> dict:
    """Build one tree (a release, optionally with a unit's commits reverted) in one bounded container."""
    src = f"/dl/harfbuzz/harfbuzz-{release}.tar.xz"
    patches = f"/work/patches-lib/{unit}" if unit else ""
    out = f"/work/out/hb/{bid}"
    started = time.time()
    code = docker_run(
        [
            "env",
            f"MESON_EXTRA={meson_extra}",
            "sh",
            "/pipe/hb_build.sh",
            src,
            out,
            patches,
            str(jobs),
            ragel,
        ],
        cpus=cpus,
        platform=platform,
        check=False,
    )
    info = {"event": "build", "id": bid, "code": code, "cpus": cpus}
    info["wall_s"] = round(time.time() - started, 1)
    build_json = WORK / "out" / "hb" / bid / "build.json"
    if build_json.exists():
        info |= json.loads(build_json.read_text())
    log_event(**info)
    print(json.dumps(info), flush=True)
    return info


def do_run(
    bid: str,
    cases: str,
    out: str,
    platform: str | None = None,
    env: str = "",
    cpus: int = 2,
) -> int:
    """Run the driver of one build over a case file, in one bounded container."""
    started = time.time()
    code = docker_run(
        ["sh", "-c", f"{env} timeout 1800 /work/out/hb/{bid}/hbdrv < {cases} > {out}"],
        cpus=cpus,
        platform=platform,
        check=False,
    )
    log_event(
        event="run", id=bid, out=out, code=code, wall_s=round(time.time() - started, 1)
    )
    return code


def cmd_build(args: argparse.Namespace) -> None:
    with heavy(f"build {args.id}"):
        do_build(
            args.id,
            args.release,
            args.unit,
            args.jobs,
            args.cpus,
            args.ragel,
            args.platform,
        )


def cmd_run(args: argparse.Namespace) -> None:
    with heavy(f"run {args.id}"):
        do_run(args.id, args.cases, args.out, args.platform)


def cmd_batch(args: argparse.Namespace) -> None:
    """Run a JSON list of build, run and shell operations under one hold of the heavy lock."""
    ops = json.loads(Path(args.plan).read_text())
    with heavy(f"batch {Path(args.plan).name} ({len(ops)} ops)"):
        for op in ops:
            if op["op"] == "build":
                do_build(
                    op["id"],
                    op["release"],
                    op.get("unit"),
                    op.get("jobs", 4),
                    op.get("cpus", 6),
                    op.get("ragel", "on"),
                    op.get("platform"),
                    op.get("meson_extra", ""),
                )
            elif op["op"] == "run":
                do_run(
                    op["id"],
                    op["cases"],
                    op["out"],
                    op.get("platform"),
                    op.get("env", ""),
                    op.get("cpus", 2),
                )
            elif op["op"] == "sh":
                started = time.time()
                code = docker_run(
                    op["args"],
                    cpus=op.get("cpus", 2),
                    platform=op.get("platform"),
                    check=False,
                )
                log_event(
                    event="sh",
                    args=op["args"][:3],
                    code=code,
                    wall_s=round(time.time() - started, 1),
                )
            else:
                raise SystemExit(f"unknown op {op['op']}")


VERIFIER_IMAGE = "hbfp-verifier:phaseB"


def stage_verifier(selection_path: Path) -> int:
    """Stage a private selection into tests/ (its git-ignored private/, inputs/ and wheels/); return the case count.

    tests/ is the verifier's build context, as on the platform. The selection's cases and recorded outputs go to
    tests/private/ (root-only in the image), the fonts they use to tests/inputs/, and the meson wheel to tests/wheels/.
    """
    selection = [
        json.loads(line) for line in selection_path.read_text().splitlines() if line
    ]
    tests = TASK / "tests"
    for sub in ("wheels", "private", "inputs/fonts/noto", "inputs/fonts/synth"):
        (tests / sub).mkdir(parents=True, exist_ok=True)
    meson = next((DL / "python").glob("meson-*.whl"))
    shutil.copy2(meson, tests / "wheels" / meson.name)
    for font in sorted({c["font"] for c in selection}):
        kind, name = font.split("/", 1)
        src = (DL / "fonts" / name) if kind == "noto" else (WORK / "fonts" / name)
        shutil.copy2(src, tests / "inputs" / "fonts" / kind / name)
    keys = ("id", "unit", "family", "kind", "window", "font", "idx", "opts", "text")
    (tests / "private" / "cases.jsonl").write_text(
        "".join(
            json.dumps({k: c[k] for k in keys}, sort_keys=True) + "\n"
            for c in selection
        )
    )
    expected = {
        rel: {c["id"]: c["gold"][rel] for c in selection}
        for rel in ("15.0.0", "15.1.0", "15.2.0")
    }
    (tests / "private" / "expected.json").write_text(json.dumps(expected))
    return len(selection)


def build_verifier_image() -> None:
    """Build the verifier image from tests/; the caller holds the heavy lock."""
    started = time.time()
    subprocess.run(
        [
            "docker",
            "build",
            "-t",
            VERIFIER_IMAGE,
            "--label",
            LABEL,
            str(TASK / "tests"),
        ],
        check=True,
    )
    log_event(
        event="image", tag=VERIFIER_IMAGE, seconds=round(time.time() - started, 1)
    )


def run_verifier(tree: Path, name: str, release: str) -> dict:
    """Run the verifier image against one tree, the way the platform would (tree read-only, logs mounted).

    The caller holds the heavy lock.
    """
    logs = WORK / "verify" / name
    logs.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker",
        "run",
        "--rm",
        "--memory=4g",
        "--memory-swap=4g",
        "--cpus=4",
        "--label",
        LABEL,
        "-e",
        f"RELEASE={release}",
        "-v",
        f"{tree.resolve()}:/app/harfbuzz:ro",
        "-v",
        f"{logs}:/logs/verifier",
        VERIFIER_IMAGE,
        "bash",
        "/tests/test.sh",
    ]
    started = time.time()
    code = subprocess.run(cmd, check=False).returncode
    reward_file = logs / "reward.txt"
    reward = reward_file.read_text().strip() if reward_file.exists() else None
    result = {
        "name": name,
        "code": code,
        "reward": reward,
        "wall_s": round(time.time() - started, 1),
    }
    log_event(event="verify", **result)
    print(json.dumps(result))
    return result


def cmd_stage_verifier(args: argparse.Namespace) -> None:
    stage_verifier(Path(args.selection))
    with heavy("verifier image"):
        build_verifier_image()


def cmd_verify(args: argparse.Namespace) -> None:
    with heavy(f"verify {args.name}"):
        run_verifier(Path(args.tree), args.name, args.release)


def cmd_milestone(args: argparse.Namespace) -> None:
    """Stage a selection, then under one hold of the lock build the verifier image and verify each tree."""
    n = stage_verifier(Path(args.selection))
    print(f"staged {n} cases")
    with heavy(f"milestone: verifier image and {len(args.tree)} verifier runs"):
        build_verifier_image()
        for spec in args.tree:
            name, _, tree = spec.partition("=")
            run_verifier(Path(tree), name, args.release)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("image")
    p.add_argument("--platform")
    p.set_defaults(func=cmd_image)
    sub.add_parser("patches").set_defaults(func=cmd_patches)
    sub.add_parser("revert-check").set_defaults(func=cmd_revert_check)
    p = sub.add_parser("build")
    p.add_argument("id")
    p.add_argument("release", choices=RELEASES)
    p.add_argument("--unit")
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--cpus", type=int, default=6)
    p.add_argument("--ragel", default="on", choices=("on", "off"))
    p.add_argument("--platform")
    p.set_defaults(func=cmd_build)
    p = sub.add_parser("run")
    p.add_argument("id")
    p.add_argument("cases")
    p.add_argument("out")
    p.add_argument("--platform")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("batch")
    p.add_argument("plan")
    p.set_defaults(func=cmd_batch)
    p = sub.add_parser("stage-verifier")
    p.add_argument("selection")
    p.set_defaults(func=cmd_stage_verifier)
    p = sub.add_parser("verify")
    p.add_argument("name")
    p.add_argument("tree")
    p.add_argument("--release", default="15.2.0")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("milestone")
    p.add_argument("selection")
    p.add_argument("tree", nargs="+", help="NAME=TREE, verified in order")
    p.add_argument("--release", default="15.2.0")
    p.set_defaults(func=cmd_milestone)
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
