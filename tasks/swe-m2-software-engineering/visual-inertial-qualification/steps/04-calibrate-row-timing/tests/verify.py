"""Grade frozen rolling-shutter calibration on independent raw pixels."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parent))
from checkpoint import Candidate, stage, verify
from rolling_probes import evaluate_cases


def evaluate(artifact, dataset, retain=True):
    retained = verify(3,artifact,dataset) if retain else {'reward':0.,'checks':{}}
    with TemporaryDirectory(prefix='visqual-rolling-') as folder:
        workspace=Path(folder)
        workspace.chmod(0o755)
        app=workspace/'app'
        portable=stage(artifact,app)
        if portable:
            cases,observations=evaluate_cases(Candidate(app,workspace),dataset/'tumvi-room1-poses.csv')
        else:
            cases,observations={}, {'artifact_error':'Missing or invalid visqual artifact'}
    new_score=sum(all(case.values()) for case in cases.values())/3
    return {'stage':4,'checks':{'retained':retained['checks'],'raw_calibration':cases},
            'component_scores':{'retained':retained['reward'],'raw_calibration':new_score},
            'observations':observations,'reward':round(.2*retained['reward']+.8*new_score,12)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=int,choices=[4],default=4)
    parser.add_argument('--artifact',type=Path,default=Path('/app/visqual'))
    parser.add_argument('--dataset',type=Path,default=Path(__file__).with_name('fixture'))
    parser.add_argument('--logs',type=Path,default=Path('/logs/verifier'))
    parser.add_argument('--new-only',action='store_true')
    args=parser.parse_args()
    args.logs.mkdir(parents=True,exist_ok=True)
    args.logs.chmod(0o700)
    reward=args.logs/'reward.json'
    reward.unlink(missing_ok=True)
    report=evaluate(args.artifact,args.dataset,retain=not args.new_only)
    (args.logs/'checkpoint.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    reward.write_text(json.dumps({'reward':report['reward']})+'\n')


if __name__=='__main__':
    main()
