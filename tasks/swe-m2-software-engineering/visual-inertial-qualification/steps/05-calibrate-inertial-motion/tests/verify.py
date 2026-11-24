"""Grade raw inertial calibration and retain the four earlier checkpoints."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parent))
from checkpoint import Candidate, stage
from inertial_probes import evaluate_cases
from verify_rolling import evaluate as retained_evaluate


def evaluate(artifact, dataset, retain=True):
    earlier=retained_evaluate(artifact,dataset) if retain else {'reward':0.,'checks':{}}
    with TemporaryDirectory(prefix='visqual-inertial-') as folder:
        root=Path(folder)
        root.chmod(0o755)
        app=root/'app'
        if stage(artifact,app):
            checks,observations=evaluate_cases(Candidate(app,root))
        else:
            checks,observations={}, {'artifact_error':'Missing or invalid visqual application'}
    score=sum(all(case.values()) for case in checks.values())/2
    return {'stage':5,'reward':round(.2*earlier['reward']+.8*score,12),
            'checks':{'retained':earlier['checks'],'inertial_motion':checks},
            'component_scores':{'retained':earlier['reward'],'inertial_motion':score},
            'inertial_observations':observations,'retained_observations':earlier.get('observations',{})}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--stage',type=int,choices=[5],default=5)
    cli.add_argument('--artifact',type=Path,default=Path('/app/visqual'))
    cli.add_argument('--dataset',type=Path,default=Path(__file__).with_name('fixture'))
    cli.add_argument('--logs',type=Path,default=Path('/logs/verifier'))
    cli.add_argument('--new-only',action='store_true')
    args=cli.parse_args()
    args.logs.mkdir(parents=True,exist_ok=True)
    args.logs.chmod(0o700)
    reward=args.logs/'reward.json'
    reward.unlink(missing_ok=True)
    report=evaluate(args.artifact,args.dataset,retain=not args.new_only)
    (args.logs/'checkpoint.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    reward.write_text(json.dumps({'reward':report['reward']})+'\n')


if __name__=='__main__':
    main()
