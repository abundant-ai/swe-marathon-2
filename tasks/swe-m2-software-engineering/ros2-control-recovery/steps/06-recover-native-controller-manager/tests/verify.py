"""Build untrusted source, retain earlier behavior, and grade against native Jazzy."""

import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile


def build(package, directory, user):
    """Compile the artifact under candidate credentials, without trusted file access."""
    if not (package / 'CMakeLists.txt').is_file():
        return None, 'Missing fenced_drive package.'
    directory.chmod(0o755)
    if user:
        os.chown(directory, user['user'], user['group'])
    source = directory / 'source'
    shutil.copytree(package, source)
    for entry in source.rglob('*'):
        entry.chmod(0o755 if entry.is_dir() or entry.stat().st_mode & 0o111 else 0o644)
    installation = directory / 'install'
    scratch = directory / 'build'
    cmake = os.environ.get('FENCED_CMAKE', 'cmake')
    commands = [
        [cmake, '-S', source, '-B', scratch, '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(installation)],
        [cmake, '--build', scratch, '-j', '2'],
        [cmake, '--install', scratch],
    ]
    with tempfile.TemporaryFile(mode='w+') as output:
        for command in commands:
            with subprocess.Popen(command, cwd=directory, stdout=output, stderr=subprocess.STDOUT,
                                  start_new_session=True, **user) as process:
                try:
                    status = process.wait(timeout=90)
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=4)
            if status:
                output.seek(0)
                return None, output.read()[-5000:]
    return installation, None


def evaluate(artifact):
    """Keep the fifth checkpoint and sample independent native recovery runs."""
    from checkpoint import grade, stage
    from native_checks import run

    retained = grade(artifact, 5)
    native = {}
    observations = {}
    user = {}
    if os.geteuid() == 0:
        account = pwd.getpwnam('candidate')
        user = {'user': account.pw_uid, 'group': account.pw_gid, 'extra_groups': []}
    with tempfile.TemporaryDirectory(prefix='fenced-build-') as scratch:
        root = Path(scratch)
        root.chmod(0o711)
        upload = root / 'upload'
        work = root / 'work'
        work.mkdir()
        try:
            if stage(artifact, upload):
                installation, failure = build(upload / 'control_recovery/native/fenced_drive', work, user)
            else:
                installation, failure = None, 'Missing or invalid control_recovery artifact tree.'
        except (OSError, subprocess.TimeoutExpired) as exc:
            installation, failure = None, str(exc)
        if failure:
            observations['build_error'] = failure
        else:
            for name, seed in (('driver', 2401), ('offline_supervisor', 5780), ('late_supervisor', 8407)):
                native[name], observations[name] = run(installation, user, seed, name)

    driver = native.get('driver', {})
    startup = driver.get('initial_claims_and_motion', False)
    protections = ('overlapping_native_modes_rejected', 'inhibit_torn', 'inhibit_stale', 'inhibit_nan',
                   'inhibit_future', 'inhibit_offline', 'offline_release_and_rejection',
                   'fresh_effort_and_generation_replay', 'strict_combined_mode_switch')
    fencing = sum(driver.get(key, False) for key in protections) / len(protections) if startup else 0.0
    recovery = 0
    for name in ('offline_supervisor', 'late_supervisor'):
        evidence = native.get(name, {})
        fenced = 'stale_claim_fenced_at_healthy_boot' if name == 'late_supervisor' else 'stale_claim_fenced_while_offline'
        factors = {fenced: 0.10, 'old_controller_released_through_manager': 0.15,
                   'new_controller_owns_native_interface': 0.20, 'recovered_motion': 0.35,
                   'healthy_joint_never_interrupted': 0.20}
        case = sum(weight for key, weight in factors.items() if evidence.get(key))
        recovery += case / 2
    native_score = 0.10 * startup + 0.20 * fencing + 0.70 * recovery
    return {
        'stage': 6, 'checks': {'retained': retained['checks'], 'native': native},
        'native_observations': observations,
        'component_scores': {'retained': retained['reward'], 'native': native_score},
        'reward': 0.20 * retained['reward'] + 0.80 * native_score,
    }


def main():
    """Write private logs using the Harbor checkpoint contract."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=Path, default=Path('/app/control_recovery'))
    parser.add_argument('--logs', type=Path, default=Path('/logs/verifier'))
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ros = Path(os.environ.get('ROS_JAZZY_PREFIX', '/opt/ros/jazzy'))
    sys.path.append(str(ros / 'lib/python3.12/site-packages'))
    report = evaluate(args.artifact)
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    (args.logs / 'checkpoint.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.logs / 'reward.txt').write_text(f"{report['reward']:.12g}\n")


if __name__ == '__main__':
    main()
