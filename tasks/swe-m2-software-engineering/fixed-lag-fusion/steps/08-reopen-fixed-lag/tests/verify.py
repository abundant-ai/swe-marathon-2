"""Grade the independent replay checks and retain the preceding checkpoints."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkpoint import stage, verify
from rewind_probes import rewind_cases


def evaluate(artifact, dataset, retain=True):
    retained = verify(7, artifact, dataset) if retain else {'reward': 0., 'groups': {}, 'component_scores': {}}
    with TemporaryDirectory(prefix='lagfusion-rewind-') as folder:
        root = Path(folder)
        root.chmod(0o711)
        app = root / 'app'
        if stage(artifact, app):
            checks, evidence = rewind_cases(app, root)
        else:
            checks, evidence = {}, {'artifact_error': 'Missing or invalid lagfusion application artifact'}
    score = sum(all(mission.values()) for mission in checks.values()) / 3
    report = {
        'stage': 8,
        'groups': dict(retained['groups'], rewind=checks),
        'component_scores': dict(retained['component_scores'], retained=retained['reward'], rewind=score),
        'rewind_observations': evidence,
        'reward': round(.20*retained['reward'] + .80*score, 12),
    }
    if 'vision_observations' in retained:
        report['vision_observations'] = retained['vision_observations']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=int, default=8, choices=[8])
    parser.add_argument('--artifact', type=Path, default=Path('/app/lagfusion'))
    parser.add_argument('--logs', type=Path, default=Path('/logs/verifier'))
    parser.add_argument('--dataset', type=Path, default=Path(__file__).with_name('room1_xy.csv'))
    parser.add_argument('--new-only', action='store_true', help='run the new missions for local diagnosis')
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward = args.logs / 'reward.json'
    reward.unlink(missing_ok=True)
    result = evaluate(args.artifact, args.dataset, retain=not args.new_only)
    (args.logs / 'checkpoint.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    reward.write_text(json.dumps({'reward': result['reward']})+'\n')


if __name__ == '__main__':
    main()
