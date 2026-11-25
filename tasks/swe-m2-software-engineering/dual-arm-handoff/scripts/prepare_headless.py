"""Derive the collision-only runtime asset from the pinned BSD Menagerie UR5e."""

import argparse
from hashlib import sha256
from pathlib import Path
import xml.etree.ElementTree as XML

SOURCE_SHA256 = 'ffd0a7b336d3c2d27c35a15cc0d4aaa95196769aca190ac8d6522d3318c345a0'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('upstream', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    original = args.upstream.read_bytes()
    if sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError('UR5e asset changed from the pinned source')
    model = XML.fromstring(original)
    model.find('compiler').attrib.pop('meshdir')
    model.remove(model.find('asset'))
    model.find('worldbody').remove(model.find('worldbody/light'))
    defaults = model.find('default/default')
    defaults.remove(defaults.find('material'))
    defaults.remove(defaults.find("default[@class='visual']"))
    for body in model.iter('body'):
        for geom in list(body.findall('geom')):
            if 'mesh' in geom.attrib:
                body.remove(geom)
        for index, geom in enumerate(body.findall('geom')):
            geom.set('name', f"{body.attrib['name']}_collision_{index}")
    XML.indent(model)
    args.output.write_text(XML.tostring(model, encoding='unicode') + '\n')


if __name__ == '__main__':
    main()
