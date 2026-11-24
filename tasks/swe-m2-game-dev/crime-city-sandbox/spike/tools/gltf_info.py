#!/usr/bin/env python3
"""Print skeleton/animation facts of a glTF/GLB file (read-only)."""
import json, struct, sys

def load(path):
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] == b'glTF':
        # GLB: header (12 bytes) then chunks
        off = 12
        clen, ctype = struct.unpack_from('<II', data, off)
        js = json.loads(data[off+8:off+8+clen])
        return js
    return json.loads(data)

def main(path, full=False):
    js = load(path)
    nodes = js.get('nodes', [])
    skins = js.get('skins', [])
    anims = js.get('animations', [])
    meshes = js.get('meshes', [])
    print(f"file: {path}")
    print(f"nodes={len(nodes)} meshes={len(meshes)} skins={len(skins)} animations={len(anims)} images={len(js.get('images', []))} materials={len(js.get('materials', []))}")
    for si, s in enumerate(skins):
        joints = s['joints']
        names = [nodes[j].get('name') for j in joints]
        print(f"skin {si}: {len(joints)} joints")
        print("  " + ", ".join(names))
    tri = 0
    acc = js.get('accessors', [])
    for m in meshes:
        for p in m['primitives']:
            if 'indices' in p:
                tri += acc[p['indices']]['count'] // 3
    print(f"triangles~{tri}")
    names = [a.get('name') for a in anims]
    print(f"animation names ({len(names)}): " + ", ".join(names[:200]))
    if full:
        # node hierarchy of first few levels
        def walk(i, d):
            n = nodes[i]
            print("  " * d + f"- {n.get('name')} mesh={n.get('mesh')} skin={n.get('skin')} t={n.get('translation')} r={n.get('rotation')} s={n.get('scale')}")
            for c in n.get('children', []):
                if d < 2:
                    walk(c, d + 1)
        for sc in js.get('scenes', []):
            for r in sc['nodes']:
                walk(r, 0)

if __name__ == '__main__':
    main(sys.argv[1], full=len(sys.argv) > 2)
