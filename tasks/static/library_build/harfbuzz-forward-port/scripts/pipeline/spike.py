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
import tarfile
import time
from collections.abc import Iterator
from pathlib import Path

if sys.version_info < (3, 11):  # noqa: UP036 - the check is for whoever runs this with an older interpreter
    raise SystemExit(
        f"spike.py needs Python 3.11 or later, not {sys.version.split()[0]}: run it with the repository's venv"
    )

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
        "-v",
        f"{TASK / 'environment'}:/env:ro",
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


def build_pipeline_image(platform: str | None) -> None:
    """Build the pipeline image (for another platform when given); the caller holds the heavy lock."""
    ctx = build_context()
    tag = IMAGE if not platform else f"{IMAGE}-{platform.split('/')[1]}"
    cmd = ["docker", "build", "-t", tag, "--label", LABEL]
    if platform:
        cmd += ["--platform", platform]
    started = time.time()
    subprocess.run([*cmd, str(ctx)], check=True)
    log_event(event="image", tag=tag, seconds=round(time.time() - started, 1))


def cmd_image(args: argparse.Namespace) -> None:
    with heavy(f"image {args.platform or 'native'}"):
        build_pipeline_image(args.platform)


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
    if unit and unit.startswith("W"):
        patches = f"/pipe/mutants/{unit}"  # our own mutations, applied forward
    elif unit and (PIPE / "reverts" / unit).is_dir():
        patches = f"/pipe/reverts/{unit}"  # a hand-resolved revert, applied forward
    else:
        patches = f"/work/patches-lib/{unit}" if unit else ""
    tolerant = "1" if unit and unit.startswith("ALL") else ""
    out = f"/work/out/hb/{bid}"
    started = time.time()
    code = docker_run(
        [
            "env",
            f"MESON_EXTRA={meson_extra}",
            f"HB_TOLERANT={tolerant}",
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
    driver: str = "hbdrv",
) -> int:
    """Run one driver of one build over a case file, in one bounded container."""
    started = time.time()
    code = docker_run(
        [
            "sh",
            "-c",
            f"{env} sh /pipe/run_cases.sh /work/out/hb/{bid} {driver} {cases} {out}",
        ],
        cpus=cpus,
        platform=platform,
        check=False,
    )
    log_event(
        event="run",
        id=bid,
        driver=driver,
        out=out,
        code=code,
        wall_s=round(time.time() - started, 1),
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


def run_ops(ops: list[dict]) -> None:
    """Run build, run and shell operations in order; the caller holds the heavy lock."""
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
                op.get("driver", "hbdrv"),
            )
        elif op["op"] == "image":
            build_pipeline_image(op.get("platform"))
        elif op["op"] == "solve":
            # The reference solution exactly as the platform runs it: solution/solve.sh on a tree at /app/harfbuzz.
            started = time.time()
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--memory=4g",
                "--memory-swap=4g",
                "--cpus=2",
            ]
            cmd += ["--label", LABEL, "-v", f"{WORK / op['tree']}:/app/harfbuzz"]
            cmd += [
                "-v",
                f"{TASK / 'solution'}:/solution:ro",
                IMAGE,
                "bash",
                "/solution/solve.sh",
            ]
            code = subprocess.run(cmd, check=False).returncode
            log_event(
                event="solve",
                tree=op["tree"],
                code=code,
                wall_s=round(time.time() - started, 1),
            )
        elif op["op"] == "run_image":
            # A bounded, network-less run of one of our task images; stdout and stderr go to WORK/<out>.
            started = time.time()
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--memory=4g",
                "--memory-swap=4g",
            ]
            cmd += [f"--cpus={op.get('cpus', 2)}", "--label", LABEL]
            if op.get("platform"):
                cmd += ["--platform", op["platform"]]
            if op.get("user"):
                cmd += ["--user", op["user"]]
            with (WORK / op["out"]).open("w") as fh:
                code = subprocess.run(
                    [*cmd, op["image"], *op["args"]],
                    stdout=fh,
                    stderr=subprocess.STDOUT,
                    check=False,
                ).returncode
            log_event(
                event="run_image",
                image=op["image"],
                code=code,
                wall_s=round(time.time() - started, 1),
            )
        elif op["op"] == "docker_build":
            # A task image (the agent image from environment/), labelled as ours.
            started = time.time()
            cmd = ["docker", "build", "-t", op["tag"], "--label", LABEL]
            if op.get("platform"):
                cmd += ["--platform", op["platform"]]
            code = subprocess.run(
                [*cmd, str(TASK / op["context"])], check=False
            ).returncode
            log_event(
                event="image",
                tag=op["tag"],
                code=code,
                seconds=round(time.time() - started, 1),
            )
        elif op["op"] == "host":
            # Our own host-side scripts only (classify.py and the like), with the host's isolated Python.
            started = time.time()
            code = subprocess.run(op["args"], cwd=TASK, check=False).returncode
            log_event(
                event="host",
                args=op["args"][:3],
                code=code,
                wall_s=round(time.time() - started, 1),
            )
            if code:
                raise SystemExit(f"host step failed ({code}): {op['args'][:3]}")
        elif op["op"] == "trial":
            # One simulated trial (simulate_trial.py): the tree as the turn's result, the hooks, the transfer.
            simulate_trial = load_simulate_trial()
            params = {k: v for k, v in op.items() if k != "op"}
            for key in ("tree", "turn"):
                if params.get(key):
                    params[key] = Path(params[key])
            params["payloads"] = [
                (Path(src), dest) for src, dest in params.pop("payloads", [])
            ]
            simulate_trial.run_trial(**params)
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


def load_simulate_trial():
    """simulate_trial.py, which lies beside this file (not on sys.path under -I)."""
    if str(PIPE) not in sys.path:
        sys.path.insert(0, str(PIPE))
    import simulate_trial

    return simulate_trial


def cmd_batch(args: argparse.Namespace) -> None:
    """Run a JSON list of build, run and shell operations under one hold of the heavy lock."""
    ops = json.loads(Path(args.plan).read_text())
    with heavy(f"batch {Path(args.plan).name} ({len(ops)} ops)"):
        run_ops(ops)


VERIFIER_IMAGE = "hbfp-verifier:phaseB"


FONT_NOTICE = """These fonts are unmodified copies of Noto fonts, each licensed under the SIL Open Font License,
Version 1.1 (OFL.txt in this folder). Each font carries its copyright notice in its name table (name ID 0) and its
licence statement in name ID 13:

  Noto Naskh Arabic, Noto Sans Arabic           Copyright 2022 The Noto Project Authors (https://github.com/notofonts/arabic)
  Noto Sans, Noto Serif (variable)              Copyright 2022 The Noto Project Authors (https://github.com/notofonts/latin-greek-cyrillic)
  Noto Sans Balinese                            Copyright 2022 The Noto Project Authors (https://github.com/notofonts/balinese)
  Noto Sans Bengali                             Copyright 2025 The Noto Project Authors (https://github.com/notofonts/bengali)
  Noto Sans Devanagari                          Copyright 2022 The Noto Project Authors (https://github.com/notofonts/devanagari)
  Noto Sans Hebrew                              Copyright 2024 The Noto Project Authors (https://github.com/notofonts/hebrew)
  Noto Sans Javanese                            Copyright 2022 The Noto Project Authors (https://github.com/notofonts/javanese)
  Noto Sans Khmer, Noto Serif Khmer             Copyright 2022 The Noto Project Authors (https://github.com/notofonts/khmer)
  Noto Sans Myanmar                             Copyright 2022 The Noto Project Authors (https://github.com/notofonts/myanmar)
  Noto Sans Syriac                              Copyright 2022 The Noto Project Authors (https://github.com/notofonts/syriac)
  Noto Sans Tai Tham                            Copyright 2022 The Noto Project Authors (https://github.com/notofonts/tai-tham)
  Noto Sans KR                                  (c) 2014-2021 Adobe (http://www.adobe.com/)

Sources: https://github.com/notofonts/notofonts.github.io and https://github.com/notofonts/noto-cjk at the commits
pinned in the fetch script. The fonts in ../synth/ are our own.
"""


def stage_verifier(selection_path: Path, recorded: Path | None = None) -> int:
    """Stage a private selection into tests/ (its git-ignored private/, inputs/ and wheels/); return the case count.

    tests/ is the verifier's build context, as on the platform. The cases go to tests/private/cases.jsonl
    (root-only in the image), the fonts they use to tests/inputs/, the meson wheel to tests/wheels/. The expected
    outputs come from `recorded` (outputs.tsv of a RECORD=1 run of the verifier image on 15.2.0) when given, else from
    the pipeline's builds as recorded in the selection.
    """
    selection = [
        json.loads(line) for line in selection_path.read_text().splitlines() if line
    ]
    tests = TASK / "tests"
    for sub in ("wheels", "private", "inputs/fonts/noto", "inputs/fonts/synth"):
        (tests / sub).mkdir(parents=True, exist_ok=True)
    meson = next((DL / "python").glob("meson-*.whl"))
    shutil.copy2(meson, tests / "wheels" / meson.name)
    named = {c["font"] for c in selection}
    for c in selection:
        named |= set(re.findall(r"(?:^|=)((?:noto|synth)/[^;,]+)", c["opts"]))
    # Every Noto font here is under the SIL Open Font License 1.1 (name ID 13 of each); its text and a notice travel
    # with the fonts. noto-cjk's Sans/LICENSE is the OFL 1.1 text; notofonts.github.io's LICENSE is that site's own
    # Apache-2.0 licence, not the fonts', so it is not shipped.
    shutil.copy2(
        DL / "fonts" / "LICENSE-noto-cjk-Sans",
        tests / "inputs" / "fonts" / "noto" / "OFL.txt",
    )
    (tests / "inputs" / "fonts" / "noto" / "NOTICE.txt").write_text(FONT_NOTICE)
    for font in sorted(named):
        kind, name = font.split("/", 1)
        src = (DL / "fonts" / name) if kind == "noto" else (WORK / "fonts" / name)
        shutil.copy2(src, tests / "inputs" / "fonts" / kind / name)
    keys = (
        "id",
        "unit",
        "family",
        "kind",
        "window",
        "drv",
        "font",
        "idx",
        "opts",
        "text",
    )
    (tests / "private" / "cases.jsonl").write_text(
        "".join(
            json.dumps({k: c.get(k, "shape") for k in keys}, sort_keys=True) + "\n"
            for c in selection
        )
    )
    if recorded:
        rows = dict(
            line.split("\t", 1) for line in recorded.read_text().splitlines() if line
        )
        expected = {"15.2.0": {c["id"]: rows[c["id"]] for c in selection}}
    else:
        expected = {
            rel: {c["id"]: c["gold"][rel] for c in selection}
            for rel in ("15.0.0", "15.1.0", "15.2.0")
        }
    (tests / "private" / "expected.json").write_text(json.dumps(expected))
    return len(selection)


def verifier_tag(platform: str | None) -> str:
    return (
        VERIFIER_IMAGE if not platform else f"{VERIFIER_IMAGE}-{platform.split('/')[1]}"
    )


def build_verifier_image(platform: str | None = None) -> None:
    """Build the verifier image from tests/ (for another platform when given); the caller holds the heavy lock."""
    tag = verifier_tag(platform)
    cmd = ["docker", "build", "-t", tag, "--label", LABEL]
    if platform:
        cmd += ["--platform", platform]
    started = time.time()
    subprocess.run([*cmd, str(TASK / "tests")], check=True)
    log_event(event="image", tag=tag, seconds=round(time.time() - started, 1))


def run_verifier(
    tree: Path | None,
    name: str,
    release: str,
    platform: str | None = None,
    record: bool = False,
    cpus: int = 4,
    background: bool = False,
    out: Path | None = None,
    mounts: list[str] | None = None,
    image: str | None = None,
    logs: Path | None = None,
    extra: list[str] | None = None,
) -> dict:
    """Run the verifier image against one tree the way the platform does. The container starts idle, with no
    network and the tree (and the sweep's out folder, when given) mounted read-only (or as the `--mount` arguments
    given); /logs/verifier is made 0777, as Harbor makes it; test.sh runs as root in an exec of its own; then, as
    Harbor collects the folder, `tar -czf` of /logs/verifier runs as root in another exec (`bash -c`, with the
    image's PATH), the archive is copied out and unpacked with tarfile's "data" filter into `logs`
    (WORK/verify/NAME by default). No host folder is mounted on /logs/verifier, so its modes are the container's
    own (R2-07 N2). `extra` adds `docker run` options (the fork bomb's second run takes `--pids-limit=96`).

    With `background`, start the run and return at once; `finish_verifier` waits for it. The caller holds the heavy
    lock.
    """
    logs = logs or WORK / "verify" / name
    logs.mkdir(parents=True, exist_ok=True)
    for stale in RESULT_NAMES:  # what an earlier run of this name left
        if (logs / stale).is_file() or (logs / stale).is_symlink():
            (logs / stale).unlink()
    container = f"hbfp-verify-{re.sub(r'[^a-z0-9_.-]+', '-', name.lower())}-{os.getpid()}-{time.time_ns() % 10**9}"
    where = list(mounts or [])
    if tree is not None:
        where += ["-v", f"{tree.resolve()}:/app/harfbuzz:ro"]
    if out is not None:
        where += ["-v", f"{out.resolve()}:/var/lib/fsmaint/out:ro"]
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container,
            "--network",
            "none",
            "--memory=4g",
            "--memory-swap=4g",
            f"--cpus={cpus}",
            "--label",
            LABEL,
            *(["--platform", platform] if platform else []),
            *where,
            *(extra or []),
            "--entrypoint",
            "sleep",
            image or verifier_tag(platform),
            "infinity",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "--user",
            "root",
            container,
            "bash",
            "-c",
            "mkdir -p /logs/verifier && chmod 777 /logs/verifier",
        ],
        check=False,
        capture_output=True,
    )
    cmd = [
        "docker",
        "exec",
        "--user",
        "root",
        "-e",
        f"RELEASE={release}",
        *(["-e", "RECORD=1"] if record else []),
        container,
        "bash",
        "/tests/test.sh",
    ]
    started = time.time()
    if background:
        return {
            "name": name,
            "logs": logs,
            "started": started,
            "container": container,
            "proc": subprocess.Popen(cmd),
        }
    code = subprocess.run(cmd, check=False).returncode
    return collect_verifier(container, name, logs, started, code)


RESULT_NAMES = (
    "reward.txt",
    "reward.json",
    "metrics.json",
    "outputs.tsv",
    "case_pass.json",
)
VERIFIER_ARCHIVE = "/tmp/runtime_download_verifier.tar.gz"


def collect_verifier(
    container: str, name: str, logs: Path, started: float, code: int
) -> dict:
    """Collect /logs/verifier from the ended run as Harbor does (tar as root, with the image's PATH), unpack it into
    `logs` with the "data" filter, remove the container, and record the result."""
    pack = subprocess.run(
        [
            "docker",
            "exec",
            "--user",
            "root",
            container,
            "bash",
            "-c",
            f"tar -czf {VERIFIER_ARCHIVE} -C /logs/verifier .",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    archive = logs / ".verifier-logs.tar.gz"
    copied = subprocess.run(
        ["docker", "cp", f"{container}:{VERIFIER_ARCHIVE}", str(archive)],
        check=False,
        capture_output=True,
    )
    subprocess.run(["docker", "rm", "-f", container], check=False, capture_output=True)
    collected = {"tar": pack.returncode, "tar_stderr": pack.stderr[-300:]}
    if copied.returncode == 0 and archive.is_file():
        try:
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(logs, filter="data")
        except (tarfile.TarError, OSError) as exc:
            collected["unpack_error"] = f"{type(exc).__name__}: {exc}"[:300]
        archive.unlink()
    else:
        collected["copied"] = False
    result = verifier_result(name, logs, started, code)
    result["collected"] = collected
    return result


def finish_verifier(run: dict) -> dict:
    """Wait for a verifier run started in the background and record its result."""
    code = run["proc"].wait()
    return collect_verifier(
        run["container"], run["name"], run["logs"], run["started"], code
    )


def read_result(path: Path) -> str | None:
    """A result file's text, read without following a link (the tree under test may plant one); None without one."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        return os.read(fd, 1 << 16).decode(errors="replace").strip()
    finally:
        os.close(fd)


def verifier_result(name: str, logs: Path, started: float, code: int) -> dict:
    result = {
        "name": name,
        "code": code,
        "reward": read_result(logs / "reward.txt"),
        "wall_s": round(time.time() - started, 1),
    }
    reward_json = read_result(logs / "reward.json")  # Harbor reads this one first
    if reward_json is not None:
        result["reward_json"] = reward_json[:200]
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


def record_gold(
    selection: Path, platform: str | None, release: str, tree: Path
) -> None:
    """Record the expected outputs through the verifier image itself (RECORD=1 on the reference tree), compare them
    with the pipeline's outputs, restage them as the expected outputs and rebuild the image."""
    res = run_verifier(tree, "record", release, platform, record=True)
    recorded = WORK / "verify" / "record" / "outputs.tsv"
    if res["code"] != 0 or not recorded.exists():
        raise SystemExit("recording through the verifier image failed")
    rows = dict(
        line.split("\t", 1) for line in recorded.read_text().splitlines() if line
    )
    cases = [json.loads(line) for line in selection.read_text().splitlines() if line]
    differ = [c["cid"] for c in cases if rows.get(c["id"]) != c["gold"][release]]
    (WORK / "verify" / "record" / "differ-from-pipeline.txt").write_text(
        "".join(f"{cid}\n" for cid in differ)
    )
    log_event(event="record", cases=len(cases), differ_from_pipeline=len(differ))
    stage_verifier(selection, recorded)
    build_verifier_image(platform)


def cmd_milestone(args: argparse.Namespace) -> None:
    """Under one hold of the lock: run the plan's operations, stage the selection, build the verifier (recording
    the expected outputs through it when asked), and verify each tree."""
    ops = json.loads(Path(args.plan).read_text()) if args.plan else []
    after = json.loads(Path(args.after).read_text()) if args.after else []
    with heavy(
        f"milestone: {len(ops)} ops, verifier image, {len(args.tree)} runs, {len(after)} ops after"
    ):
        milestone_runs(args, ops)
        run_ops(after)


def milestone_runs(args: argparse.Namespace, ops: list[dict]) -> None:
    """cmd_milestone's work before its `--after` operations; the caller holds the heavy lock."""
    run_ops(ops)
    n = stage_verifier(
        Path(args.selection), Path(args.recorded) if args.recorded else None
    )
    print(f"staged {n} cases", flush=True)
    build_verifier_image(args.platform)
    if args.record:
        record_gold(
            Path(args.selection), args.platform, args.release, Path(args.record)
        )
    if args.record and args.determinism:
        determinism(Path(args.record), args.release, args.platform)
    # A tree named bg:NAME runs in the background, beside the others: for runs that mostly wait out the
    # verifier's deadline (a sleeping build, a hanging library), so they do not hold the lock for half an hour
    # each. They are started first and waited for at the end.
    specs = [s.partition("=") for s in args.tree]
    if args.through_trial:
        through_trials(args, specs)
        return
    started = []
    for name, _, rest in sorted(specs, key=lambda x: not x[0].startswith("bg:")):
        tree, _, release = rest.partition("@")
        if name.startswith("bg:"):
            started.append(
                run_verifier(
                    Path(tree),
                    name[3:],
                    release or args.release,
                    args.platform,
                    background=True,
                )
            )
        else:
            run_verifier(Path(tree), name, release or args.release, args.platform)
    for run in started:
        finish_verifier(run)


BG_AT_ONCE = 2  # background trials at once (through_trials)


def through_trials(args: argparse.Namespace, specs: list[tuple[str, str, str]]) -> None:
    """Each tree through one simulated trial (simulate_trial.run_trial): put in place as the turn's result, the
    hooks run, packed and unpacked as Harbor moves it, then verified. TREE `solution` runs solution/solve.sh as the
    turn, TREE `shipped` keeps the image's tree. The others run first, one at a time; then the bg:NAME trials, which
    mostly wait out the verifier's deadline, run in threads, at most BG_AT_ONCE together, so that no more than that
    many unprivileged builds share Docker's disk at once (fix round 2: the VM had under 2 GB free)."""
    import threading

    simulate_trial = load_simulate_trial()
    if args.build_agent:
        simulate_trial.build_images(
            args.agent_image, verifier_tag(args.platform), args.platform, verifier=False
        )
    slots = threading.BoundedSemaphore(BG_AT_ONCE)

    def one(**params) -> None:
        try:
            simulate_trial.run_trial(**params)
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - one trial's failure is its own record
            print(f"trial {params['name']} failed: {exc!r}", flush=True)
            log_event(event="trial_failed", name=params["name"], error=repr(exc)[:300])

    def in_slot(**params) -> None:
        with slots:
            one(**params)

    threads = []
    for name, _, rest in sorted(specs, key=lambda x: x[0].startswith("bg:")):
        tree, _, release = rest.partition("@")
        params = {
            "name": name.removeprefix("bg:"),
            "tree": None if tree in ("solution", "shipped") else Path(tree),
            "solution": tree == "solution",
            "release": release or args.release,
            "agent_image": args.agent_image,
            "verifier_image": verifier_tag(args.platform),
            "platform": args.platform,
        }
        if name.startswith("bg:"):
            thread = threading.Thread(target=in_slot, kwargs=params)
            thread.start()
            threads.append(thread)
        else:
            one(**params)
    for thread in threads:
        thread.join()


def determinism(tree: Path, release: str, platform: str | None) -> None:
    """3+1: record the reference twice more as before and once on one CPU; every outputs.tsv must be identical."""
    runs = {"record-2": 4, "record-3": 4, "record-1cpu": 1}
    for name, cpus in runs.items():
        run_verifier(tree, name, release, platform, record=True, cpus=cpus)
    first = (WORK / "verify" / "record" / "outputs.tsv").read_bytes()
    same = {
        name: (WORK / "verify" / name / "outputs.tsv").exists()
        and (WORK / "verify" / name / "outputs.tsv").read_bytes() == first
        for name in runs
    }
    log_event(event="determinism", identical=same)
    print(json.dumps({"determinism": same}), flush=True)


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
    p.add_argument("tree", nargs="+", help="NAME=TREE[@RELEASE], verified in order")
    p.add_argument("--release", default="15.2.0")
    p.add_argument("--plan", help="operations to run first, under the same hold")
    p.add_argument("--after", help="operations to run last, under the same hold")
    p.add_argument("--platform", help="build and run the verifier for this platform")
    p.add_argument(
        "--record",
        help="reference tree: record the expected outputs through the verifier image",
    )
    p.add_argument(
        "--recorded",
        help="stage the expected outputs from an earlier recording (its outputs.tsv)",
    )
    p.add_argument(
        "--determinism",
        action="store_true",
        help="with --record: three more recordings, one of them on 1 CPU",
    )
    p.add_argument(
        "--through-trial",
        action="store_true",
        help="run each tree through a simulated trial (simulate_trial.py): TREE may be `solution` or `shipped`",
    )
    p.add_argument(
        "--agent-image",
        default="hbfp-agent:trial",
        help="with --through-trial: the agent image",
    )
    p.add_argument(
        "--build-agent",
        action="store_true",
        help="with --through-trial: build the agent image from environment/ first",
    )
    p.set_defaults(func=cmd_milestone)
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
