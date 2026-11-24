"""Write a course manifest and annotated initial example observations."""

import json
from pathlib import Path
import sys


def main(output):
    source=Path(__file__).resolve().parent
    base=json.loads((source/'manifest.json').read_text())
    base['actor']=str(source/'policy.onnx')
    base['course']={'extent':[-1.,5.,-2.15,2.15],'goal':[3.9,.0,.0],
                    'footprint_radius_m':.46,'max_speed_mps':.56,'max_pose_age_ticks':7,
                    'max_map_age_ticks':12,'max_map_lease_ticks':11,'completion_tick':1449}
    output.mkdir(parents=True,exist_ok=True)
    (output/'course.json').write_text(json.dumps(base,indent=2)+'\n')
    with (output/'course-start.ndjson').open('w') as f:
        for row in (source/'starter.ndjson').read_text().splitlines():
            item=json.loads(row)
            item.pop('request',None)
            tick=item['tick']
            item['localization']={'capture_tick':tick,'position':[0.,0.],
                                  'heading_rad':0.,'velocity':[0.,0.]}
            item['map']={'revision':1,'capture_tick':tick,'valid_until_tick':tick+9,
                         'obstacles':[[1.31,1.59,-.52,.52]]}
            print(json.dumps(item),file=f)


if __name__=='__main__':
    main(Path(sys.argv[1]))
