"""Grade raw-scan native Go2 routes and retention of the earlier policy bridge."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parent))
from grade_bridge import grade, stage
from scan_checks import MISSIONS, run_scan_case
from transport import Rejected


def evaluate(artifact, retain=True):
    retained = grade(artifact,8) if retain else {'reward':0.,'checks':{},'observations':{}}
    current, measured = {}, {}
    with TemporaryDirectory(prefix='go2-scan-checkpoint-') as folder:
        root=Path(folder)
        root.chmod(0o755)
        app=root/'app'
        app.mkdir()
        portable=stage(artifact,app)
        for index,case in enumerate(MISSIONS):
            name=case['name']
            current[name]=False
            if not portable:
                measured[name]='no usable application artifact'
                continue
            scratch=root/f'mission-{index}'
            scratch.mkdir()
            try:
                measured[name]=run_scan_case(app,scratch,**case)
                current[name]=True
            except (Rejected,ValueError,TypeError,KeyError,OverflowError,IndexError,OSError) as exc:
                measured[name]=str(exc)
    score=sum(current.values())/len(MISSIONS)
    return {'stage':9,'reward':round(.20*retained['reward']+.80*score,12),
            'checks':dict(retained['checks'],**current), 'scan_fraction':score,
            'retained_reward':retained['reward'],'observations':dict(retained['observations'],**measured)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=int,choices=[9],default=9)
    parser.add_argument('--artifact',type=Path,default=Path('/app/policy_bridge'))
    parser.add_argument('--output',type=Path,default=Path('/logs/verifier'))
    parser.add_argument('--scan-only',action='store_true')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    args.output.chmod(0o700)
    reward=args.output/'reward.txt'
    reward.unlink(missing_ok=True)
    report=evaluate(args.artifact,retain=not args.scan_only)
    (args.output/'checkpoint.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    reward.write_text(f"{report['reward']:.12g}\n")


if __name__=='__main__':
    main()
