"""Derive the sealed upstream-test list and the visible/held-out split.

usage: sealed.py <work_dir> <out.json> [--holdout 0.30] [--max-sec 8]
Reads work_dir/junit_pristine_*.xml (certification) and work_dir/junit_skel_*.xml.
"""

from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("work")
ap.add_argument("out")
ap.add_argument("--holdout", type=float, default=0.30)
ap.add_argument("--max-sec", type=float, default=8.0)
args = ap.parse_args()


def parse(path):
    """nodeid -> (outcome, seconds)"""
    out = {}
    for tc in ET.parse(path).iter("testcase"):
        f = tc.get("file")
        cls = tc.get("classname") or ""
        name = tc.get("name") or ""
        if not f:
            continue
        mod = f[:-3].replace("/", ".")
        rest = cls[len(mod) :].strip(".") if cls.startswith(mod) else ""
        nid = f + "::" + ("::".join(rest.split(".")) + "::" if rest else "") + name
        oc = "passed"
        for ch in tc:
            if ch.tag in ("failure", "error"):
                oc = "failed"
            elif ch.tag == "skipped":
                oc = "skipped"
        if nid in out and out[nid][0] != oc:
            oc = "failed"
        out[nid] = (oc, float(tc.get("time") or 0))
    return out


pri = [
    parse(p) for p in sorted(glob.glob(os.path.join(args.work, "junit_pristine_*.xml")))
]
skel = [
    parse(p) for p in sorted(glob.glob(os.path.join(args.work, "junit_skel_*.xml")))
]
assert pri and skel
cert = set(pri[0])
for r in pri:
    cert &= {n for n, (oc, _) in r.items() if oc == "passed"}
slow = {n for n in cert if max(r[n][1] for r in pri) > args.max_sec}
cert -= slow
EXCLUDE = (
    "sympy/testing/",  # tests of the test runner; depend on repo layout
    "sympy/utilities/tests/test_code_quality.py",  # style checks over the source tree
    "sympy/utilities/tests/test_deprecated.py",
    "sympy/tests/",
    "sympy/external/",  # need compilers or optional packages
)
cert = {n for n in cert if not n.startswith(EXCLUDE)}
extra_drop = os.path.join(args.work, "sealed_drop.json")
if os.path.exists(extra_drop):
    cert -= set(json.loads(Path(extra_drop).read_text()))
disc = {n for n in cert if any(s.get(n, ("absent", 0))[0] != "passed" for s in skel)}


def func_key(nid):
    f, rest = nid.split("::", 1)
    return f + "::" + rest.split("[")[0]


def frac(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


byfunc = collections.defaultdict(list)
for n in disc:
    byfunc[func_key(n)].append(n)
# test_args.py checks itself against the package (one test per class); keep it whole
NO_HOLDOUT = ("sympy/core/tests/test_args.py",)

# The hold-out decision is taken on the body of the test function, so identical copies of
# a test in two files are held out together, and a test that other code in its file calls
# stays visible.
import ast

_parsed = {}
xfail = set()


def _info(path):
    if path not in _parsed:
        src = Path(os.path.join(args.work, "pristine", path)).read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        bodies, refs = {}, collections.Counter()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bodies[node.name] = ast.dump(
                    ast.Module(body=node.body, type_ignores=[]),
                    include_attributes=False,
                )
                if any(
                    "XFAIL" in ast.dump(d) or "xfail" in ast.dump(d)
                    for d in node.decorator_list
                ):
                    xfail.add(path + "::" + node.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                refs[node.id] += 1
            elif isinstance(node, ast.Attribute):
                refs[node.attr] += 1
        _parsed[path] = (bodies, refs)
    return _parsed[path]


held_funcs = []
for k in sorted(byfunc):
    if k.count("::") != 1 or k.startswith(NO_HOLDOUT):
        continue
    f, name = k.split("::")
    bodies, refs = _info(f)
    if name not in bodies or refs[name] > 0:
        continue
    if frac(bodies[name]) < args.holdout:
        held_funcs.append(k)
# tests marked as expected failures are not graded
for k in sorted(byfunc):
    if k.count("::") == 1:
        _info(k.split("::")[0])
dropped_xfail = [n for n in disc if func_key(n) in xfail]
disc -= set(dropped_xfail)
held_funcs = [k for k in held_funcs if k not in xfail]
held = sorted(n for k in held_funcs for n in byfunc[k])
visible = sorted(disc - set(held))
with open(args.out, "w") as stream:
    json.dump(
        {
            "tests": sorted(disc),
            "held_out": held,
            "held_out_functions": held_funcs,
            "visible": visible,
            "pristine_runs": len(pri),
            "pristine_cpu_sec": round(sum(pri[0][n][1] for n in disc)),
        },
        stream,
    )
print(
    "pristine runs",
    len(pri),
    "| certified",
    len(cert),
    "| dropped slow",
    len(slow),
    "| discriminating",
    len(disc),
    "| held-out",
    len(held),
    f"({len(held_funcs)} functions)",
    "| visible",
    len(visible),
    "| cpu-sec (run 1)",
    round(sum(pri[0][n][1] for n in disc)),
)
print(
    "files with sealed tests:",
    len({n.split("::")[0] for n in disc}),
    "| expected-failure tests dropped:",
    len(dropped_xfail),
)
