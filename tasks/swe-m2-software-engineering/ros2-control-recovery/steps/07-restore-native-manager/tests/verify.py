"""Grade native cross-process durable authority and physical restoration."""

import argparse
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from checkpoint import stage
from verify_native import build, evaluate as retained_evaluate

CASES = {
    'driver_strict_after_sigkill': (19541, True),
    'supervised_rejoin_after_sigkill': (45809, False),
}
WEIGHTS = {
    'initial_claim_and_motion': 0.08,
    'higher_epoch_observed_while_offline': 0.07,
    'retired_epoch_never_claimed': 0.20,
    'retired_epoch_never_wrote': 0.15,
    'fresh_native_effort_claim': 0.15,
    'fresh_measured_motion': 0.22,
    'independent_manager_kept_actuating': 0.13,
}


def evaluate(artifact, retain=True):
    """Run stage 6 and two physical restart missions with shared score semantics."""
    from restart_checks import run_restart

    retained = retained_evaluate(artifact) if retain else {'reward': 0.0, 'checks': {}}
    evidence, observations, rewards = {}, {}, {}
    user = {}
    if os.geteuid() == 0:
        account = pwd.getpwnam('candidate')
        user = {'user': account.pw_uid, 'group': account.pw_gid, 'extra_groups': []}
    with tempfile.TemporaryDirectory(prefix='restart-build-') as scratch:
        root = Path(scratch)
        root.chmod(0o711)
        upload, work = root / 'upload', root / 'work'
        work.mkdir()
        installation = None
        try:
            if stage(artifact, upload):
                installation, failure = build(upload / 'control_recovery/native/fenced_drive', work, user)
            else:
                failure = 'Missing or invalid control_recovery artifact tree.'
        except (OSError, subprocess.TimeoutExpired) as exc:
            failure = str(exc)
        if failure:
            observations['build_error'] = failure
        elif installation is not None:
            for label, (seed, driver) in CASES.items():
                result, observations[label] = run_restart(installation, user, seed, driver)
                checks = {key: bool(result.get(key)) for key in WEIGHTS}
                evidence[label] = checks
                weight = sum(value for name, value in WEIGHTS.items() if checks[name])
                safe = checks['retired_epoch_never_claimed'] and checks['retired_epoch_never_wrote']
                if not safe:
                    weight = min(weight, 0.25)
                rewards[label] = round(weight, 12)
    restart = sum(rewards.values()) / len(CASES)
    return {
        'stage': 7,
        'checks': {'retained': retained['checks'], 'restart': evidence},
        'restart_observations': observations,
        'case_scores': rewards,
        'component_scores': {'retained': retained['reward'], 'restart': restart},
        'reward': round(0.20 * retained['reward'] + 0.80 * restart, 12),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=Path, default=Path('/app/control_recovery'))
    parser.add_argument('--logs', type=Path, default=Path('/logs/verifier'))
    parser.add_argument('--restart-only', action='store_true', help='local restart diagnostic')
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    ros = Path(os.environ.get('ROS_JAZZY_PREFIX', '/opt/ros/jazzy'))
    sys.path.append(str(ros / 'lib/python3.12/site-packages'))
    report = evaluate(args.artifact, retain=not args.restart_only)
    (args.logs / 'checkpoint.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.logs / 'reward.txt').write_text(f"{report['reward']:.12g}\n")


if __name__ == '__main__':
    main()
