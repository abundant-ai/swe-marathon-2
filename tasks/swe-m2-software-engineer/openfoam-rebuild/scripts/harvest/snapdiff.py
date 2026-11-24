"""Copies files new or changed in <after> to <out>; lists removed ones in <out>/../removed.
usage: snapdiff.py <before> <after> <out>"""
import filecmp
import os
import shutil
import sys


def files(root):
    out = set()
    for d, dirs, fs in os.walk(root):
        for f in fs:
            rel = os.path.relpath(os.path.join(d, f), root)
            if not os.path.basename(rel).startswith("log."):
                out.add(rel)
    return out


before, after, out = sys.argv[1:]
fb, fa = files(before), files(after)
os.makedirs(out, exist_ok=True)
for rel in sorted(fa):
    a = os.path.join(after, rel)
    b = os.path.join(before, rel)
    if rel not in fb or not filecmp.cmp(a, b, shallow=False):
        dst = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(a, dst, follow_symlinks=False)
with open(os.path.join(os.path.dirname(out.rstrip("/")), "removed"), "w") as f:
    f.writelines(rel + "\n" for rel in sorted(fb - fa))
