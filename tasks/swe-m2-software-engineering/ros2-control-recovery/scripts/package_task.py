"""Select the runtime files needed to build a control_recovery task bundle."""

import argparse
from pathlib import Path
import shutil
import tempfile
import tomllib

TASK = Path(__file__).resolve().parents[1]
ORACLE = [
    ("__init__.py", "__main__.py", "core.py"),
    (),
    (),
    ("handover.py",),
    ("servo.py",),
    (),
    (),
    (),
]


def copy(source: Path, target: Path) -> None:
    """Copy one absolute authoring path into its chosen bundle target."""
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def package(parent: Path) -> Path:
    """Publish a clean runtime-only bundle under the task's submitting slug."""
    config = tomllib.loads((TASK / "task.toml").read_text(encoding="utf-8"))
    name = config["task"]["name"].split("/", 1)[1]
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / name
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory(prefix=".bundle-", dir=parent) as temporary:
        staged = Path(temporary) / name
        copy(TASK / "task.toml", staged / "task.toml")
        for name in ("Dockerfile", ".dockerignore", "resources/README.md",
                     "resources/native_manager_demo.py", "resources/native_drive_demo.py"):
            copy(TASK / "environment" / name, staged / "environment" / name)
        runtime = []
        for step, modules in zip(config["steps"], ORACLE, strict=True):
            prefix = Path("steps", step["name"])
            for name in ("instruction.md", "tests/Dockerfile", "tests/test.sh", "tests/verify.py", "solution/solve.sh"):
                copy(TASK / prefix / name, staged / prefix / name)
            verifier_files = ("checkpoint.py", "probes.py")
            step_number = int(step["name"][:2])
            if step_number >= 4:
                verifier_files += ("handover_checks.py",)
            if step_number >= 5:
                verifier_files += ("servo_checks.py",)
            for name in verifier_files:
                copy(TASK / "common" / "verifier" / name, staged / prefix / "tests" / name)
            runtime.extend(modules)
            for name in runtime:
                path = Path("control_recovery", name)
                copy(TASK / "common" / "oracle" / path, staged / prefix / "solution" / path)
            if step_number >= 6:
                native = Path("native", "fenced_drive")
                for name in ("CMakeLists.txt", "package.xml", "plugins.xml", "src/system.cpp",
                             "src/device_slot.hpp", "scripts/recover_drive"):
                    path = native / name
                    source_step = Path("steps/07-restore-native-manager") if step_number == 8 else prefix
                    override = TASK / source_step / "solution" / path
                    source = override if override.is_file() else TASK / "common" / "oracle" / path
                    copy(source, staged / prefix / "solution" / path)
                native_tests = TASK / "steps/06-recover-native-controller-manager/tests"
                copy(native_tests / "native_checks.py", staged / prefix / "tests/native_checks.py")
            if step_number >= 7:
                predecessor = TASK / "steps/07-restore-native-manager"
                header = Path("solution/native/fenced_drive/src/generation_ledger.hpp")
                copy(predecessor / header, staged / prefix / header)
                copy(native_tests / "verify.py", staged / prefix / "tests/verify_native.py")
                copy(predecessor / "tests/restart_checks.py", staged / prefix / "tests/restart_checks.py")
            if step_number >= 8:
                copy(predecessor / "tests/verify.py", staged / prefix / "tests/verify_restart.py")
                copy(TASK / prefix / "tests/lift_checks.py", staged / prefix / "tests/lift_checks.py")
                for folder, location, filenames in (
                    ("common/oracle/native/coupled_handover", "solution/native/coupled_handover",
                     ("CMakeLists.txt", "package.xml", "controllers.xml", "src/controllers.cpp", "scripts/recover_pair")),
                    ("common/verifier/lift_device", "tests/lift_device",
                     ("CMakeLists.txt", "package.xml", "hardware.xml", "src/device.cpp")),
                ):
                    for name in filenames:
                        copy(TASK / folder / name, staged / prefix / location / name)
        staged.rename(target)
    return target


def main() -> None:
    """Build the configured bundle with optional caller-selected parent directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(parser.parse_args().output))


if __name__ == "__main__":
    main()
