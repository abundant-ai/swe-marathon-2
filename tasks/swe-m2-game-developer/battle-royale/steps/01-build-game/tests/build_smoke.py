"""Build and start a submitted Unreal project in an isolated Linux container."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
from tempfile import TemporaryDirectory
import time


GENERATED_ROOT_DIRS = frozenset(("Binaries", "Intermediate", "Saved", "DerivedDataCache"))
MAP_STARTED = re.compile(
    rb"LogLoad:\s*Took [^\r\n]+ to LoadMap\([^\r\n)]+\)"
    rb"|LogWorld:\s*Bringing World [^\r\n]+ up for play\b"
)


class SmokeError(RuntimeError):
    """A build or launch smoke stage could not establish its expected result."""


def engine_version(engine_root: Path) -> str:
    """Read the installed version from the engine being used for the build.

    Args:
        engine_root: Directory containing Unreal's Engine subdirectory.

    Returns:
        The recorded major, minor, and patch version as a dotted string.

    Raises:
        SmokeError: The engine version file is missing or invalid.
    """
    try:
        version = json.loads((engine_root / "Engine/Build/Build.version").read_text())
        parts = tuple(version[key] for key in ("MajorVersion", "MinorVersion", "PatchVersion"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SmokeError(f"Cannot read the engine Build.version: {exc}") from exc
    if any(type(part) is not int or part < 0 for part in parts):
        raise SmokeError("Engine Build.version requires three nonnegative integer version fields")
    return ".".join(map(str, parts))


def build_command(engine_root: Path, project: Path, package: Path) -> list[str]:
    """Assemble the Unreal Automation Tool command for a Linux package.

    Args:
        engine_root: Installed engine containing the RunUAT executable.
        project: Absolute path to the scratch copy of the submitted project.
        package: Fresh absolute archive destination.

    Returns:
        Argument vector passed directly to the process, preserving spaces in paths.
    """
    return [
        str(engine_root / "Engine/Build/BatchFiles/RunUAT.sh"),
        "BuildCookRun",
        f"-project={project}",
        "-platform=Linux",
        "-clientconfig=Development",
        "-noP4",
        "-build",
        "-cook",
        "-AdditionalCookerOptions=-skipzenstore",
        "-stage",
        "-pak",
        "-archive",
        f"-archivedirectory={package}",
        "-utf8output",
        "-unattended",
    ]


def copy_project(source: Path, destination: Path) -> None:
    """Stage a project without its root-level generated outputs and caches.

    Args:
        source: Absolute path to the submitted project's source directory.
        destination: Fresh directory where RunUAT can modify the scratch copy.

    Preserves the source tree, including nested plugin directories.
    """
    def ignore_generated(directory: str, names: list[str]) -> set[str]:
        """Select generated directories to skip in the project root only."""
        if Path(directory) != source:
            return set()
        return {name for name in GENERATED_ROOT_DIRS.intersection(names) if (source / name).is_dir()}

    shutil.copytree(source, destination, symlinks=True, ignore=ignore_generated)


def stop_process_group(process: subprocess.Popen[bytes]) -> None:
    """Stop a smoke child and its descendants before deleting scratch state.

    Args:
        process: A process started in its own session by the smoke runner.
    """
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def build_project(
    command: list[str], workdir: Path, log_path: Path, environment: dict[str, str], timeout: int
) -> None:
    """Build the scratch project, retaining Unreal's combined tool output.

    Args:
        command: RunUAT argument vector returned by build_command.
        workdir: Scratch project directory where the build runs.
        log_path: New file for the combined stdout and stderr.
        environment: Explicit environment for the unprivileged child.
        timeout: Maximum allowed build time in seconds.

    Raises:
        SmokeError: RunUAT exits unsuccessfully or exceeds the build timeout.
    """
    with log_path.open("wb") as log, subprocess.Popen(
        command, cwd=workdir, env=environment, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    ) as process:
        try:
            code = process.wait(timeout=timeout)
            if code:
                raise SmokeError(f"RunUAT failed with exit code {code}. See {log_path.name}.")
        except subprocess.TimeoutExpired as exc:
            raise SmokeError(f"RunUAT exceeded {timeout} seconds. See {log_path.name}.") from exc
        finally:
            stop_process_group(process)


def packaged_launcher(package: Path, project_name: str) -> Path:
    """Locate the game's generated Linux launcher and verify there is a binary.

    Args:
        package: Fresh directory written by the successful RunUAT archive step.
        project_name: File stem of the supplied .uproject.

    Returns:
        Path to the generated shell launcher.

    Raises:
        SmokeError: The archive lacks an unambiguous launcher or an executable ELF.
    """
    launchers = [
        path for path in package.rglob("*.sh")
        if path.name == f"{project_name}.sh" and not path.is_symlink() and path.is_file()
    ]
    if len(launchers) != 1:
        raise SmokeError(f"Expected one generated {project_name}.sh launcher, found {len(launchers)}")
    for binary in launchers[0].parent.glob("**/Binaries/Linux/*"):
        if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
            continue
        with binary.open("rb") as stream:
            if stream.read(4) == b"\x7fELF" and ".so" not in binary.suffixes:
                return launchers[0]
    raise SmokeError("The archived launcher has no packaged executable ELF under Binaries/Linux")


def launch_project(
    launcher: Path, log_path: Path, environment: dict[str, str], timeout: int
) -> str:
    """Start the packaged game headlessly and wait for a map startup log entry.

    Args:
        launcher: Generated Linux game launcher under the fresh archive.
        log_path: New file for the combined game logs.
        environment: Explicit environment for the unprivileged child.
        timeout: Maximum allowed startup time in seconds.

    Returns:
        The map-start marker observed before shutting down the process group.

    Raises:
        SmokeError: The launcher exits early or fails to log map startup in time.
    """
    command = [
        "/bin/bash", str(launcher), "-nullrhi", "-nosound", "-unattended",
        "-stdout", "-FullStdOutLogOutput",
    ]
    with log_path.open("wb") as output, log_path.open("rb") as reader, subprocess.Popen(
        command, cwd=launcher.parent, env=environment, stdin=subprocess.DEVNULL,
        stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
    ) as process:
        deadline = time.monotonic() + timeout
        tail = b""
        try:
            while time.monotonic() < deadline:
                chunk = reader.read(65536)
                text = tail + chunk
                marker = MAP_STARTED.search(text)
                code = process.poll()
                if code is not None:
                    raise SmokeError(f"The headless game exited with code {code}. See {log_path.name}.")
                if marker:
                    return marker.group().decode(errors="replace")
                tail = text[-4096:]
                if not chunk:
                    time.sleep(0.1)
            raise SmokeError(f"No map startup in {timeout} seconds. See {log_path.name}.")
        finally:
            stop_process_group(process)


def main() -> int:
    """Run the unprivileged smoke CLI and record evidence in a fresh directory.

    Returns:
        Zero after Linux packaging and map startup, otherwise a nonzero exit.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, default=Path("/opt/unreal"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--build-timeout", type=int, default=1800, help="Build timeout in seconds")
    parser.add_argument("--launch-timeout", type=int, default=60, help="Startup timeout in seconds")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run the smoke as an unprivileged user in the isolated verifier container")
    if min(args.build_timeout, args.launch_timeout) <= 0:
        parser.error("Build and launch timeouts must be positive")
    project = args.project.resolve()
    output = args.output_dir.resolve()
    if project.suffix != ".uproject" or not project.is_file():
        parser.error("--project must point to a .uproject file")
    if output.is_relative_to(project.parent):
        parser.error("--output-dir must be outside the project directory")
    try:
        output.mkdir(mode=0o700, parents=True)
    except OSError as exc:
        parser.error(f"Cannot create a fresh output directory: {exc}")

    engine_root = args.engine_root.resolve()
    report: dict[str, str] = {"status": "failed", "stage": "engine", "engine_root": str(engine_root)}
    try:
        report["engine_version"] = engine_version(engine_root)
        package = output / "package"
        # Unreal can detach its cache service from the build process group.
        # Keep its files outside the build tree, which the verifier removes.
        with (
            TemporaryDirectory(prefix=".smoke-", dir=output) as temporary,
            TemporaryDirectory(prefix="basin-smoke-cache-", dir="/tmp", ignore_cleanup_errors=True) as cache,
        ):
            scratch = Path(temporary)
            runtime = Path(cache)
            for folder in ("home", "tmp"):
                (runtime / folder).mkdir()
            environment = {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": str(runtime / "home"),
                "TMPDIR": str(runtime / "tmp"),
                "DOTNET_CLI_HOME": str(runtime / "home"),
                "UnrealBuildTool_BuildConfiguration__bAllowUBAExecutor": "false",
            }
            report["stage"] = "copy"
            copied = scratch / "project"
            copy_project(project.parent, copied)
            report["stage"] = "build"
            build_project(
                build_command(engine_root, copied / project.name, package),
                copied, output / "build.log", environment, args.build_timeout,
            )
            report["stage"] = "archive"
            launcher = packaged_launcher(package, project.stem)
            report["launcher"] = str(launcher.relative_to(output))
            report["stage"] = "launch"
            report["map_startup"] = launch_project(
                launcher, output / "launch.log", environment, args.launch_timeout,
            )
        report["status"] = "passed"
    except (OSError, SmokeError) as exc:
        report["error"] = str(exc)
    (output / "smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
