"""Rebuild the stock pilot from the original CORe50 mini archive and train both source starts."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]


def build(archive, destination):
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        scratch = Path(tmp)
        base, cameras, stock = [scratch / name for name in ("base","cameras","stock")]
        def run(script,*args):
            subprocess.run([sys.executable,"-B",str(script),*map(str,args)],check=True)
        run(TASK/"scripts/prepare.py",archive,base)
        for name,seed in (("common",37),("replicate",73)):
            run(TASK/"public/train.py","--data",base/"source.npz","--out",base/(name+".npz"),"--seed",seed)
        run(TASK/"routed/prepare.py","--reacquired",base,cameras)
        run(TASK/"inventory/prepare.py",base,cameras,stock)
        run(TASK/"scripts/stage.py","--inventory-site",stock,scratch/"packages")
        run(TASK/"inventory/check_handover.py",scratch/"packages")
        (scratch/"packages").rename(destination)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    build(args.archive,args.destination)
