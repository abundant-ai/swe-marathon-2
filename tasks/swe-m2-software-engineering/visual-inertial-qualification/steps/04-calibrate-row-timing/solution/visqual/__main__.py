"""Work with calibrated stereo and inertial pose recordings."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import numpy as np

from .calibration import calibrate
from .pose import obj
from .qualification import qualify
from .rolling import solve as calibrate_row_timing
from .stereo import triangulate


def main():
    """Handle one estimator operation and atomically publish its report."""
    operations={"triangulate":triangulate,"calibrate":calibrate,"qualify":qualify,
                "calibrate-row-timing":calibrate_row_timing}
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    for name in operations:
        cli=sub.add_parser(name)
        cli.add_argument("--spec",type=Path,required=True)
        cli.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    try:
        spec=obj(json.loads(args.spec.read_text()))
        content=json.dumps(operations[args.command](spec),indent=2,allow_nan=False)+"\n"
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=args.output.parent) as work:
            temp=Path(work)/"report"
            temp.write_text(content)
            temp.replace(args.output)
    except (OSError,KeyError,TypeError,ValueError,OverflowError,np.linalg.LinAlgError) as error:
        print(f"visqual: {error}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    sys.exit(main())
