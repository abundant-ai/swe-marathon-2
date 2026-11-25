"""Find units whose original body also survives in code that stays visible.

usage: twin_scan.py <work_dir> <out_drop.json>
A unit is dropped when a function that is NOT a unit has a body that is AST-identical to
the unit's original body, or (same function name) at least 85% similar as text, and the
body has two or more statements.  Single-statement bodies are only dropped on an exact
match with a same-named function.
"""
import ast, collections, difflib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "task_src"))
import restorelib
W, outp = sys.argv[1], sys.argv[2]
units = json.load(open(os.path.join(W, "units.json")))
pristine = os.path.join(W, "pristine")
unit_keys = {(u["file"], u["qualname"], u.get("occ", 0)) for u in units}

def body_of(fn):
    doc, rest = restorelib._doc_and_rest(fn)
    return rest

def norm(rest):
    return "\n".join(ast.dump(s, include_attributes=False) for s in rest)

def text(rest):
    return "\n".join(ast.unparse(s) for s in rest)


class _Blind(ast.NodeTransformer):
    """Rename every identifier, so that a body and a renamed copy of it look the same."""

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        node.attr = "_"
        return node

    def visit_arg(self, node):
        node.arg = "_"
        node.annotation = None
        return node

    def visit_keyword(self, node):
        self.generic_visit(node)
        node.arg = "_" if node.arg else None
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.name = "_"
        return node


def blind(rest):
    import copy

    nodes = [_Blind().visit(copy.deepcopy(s)) for s in rest]
    return "\n".join(ast.dump(s, include_attributes=False) for s in nodes)


def nnodes(rest):
    return sum(1 for s in rest for _ in ast.walk(s))

# index every function body in the tree (tests included: they stay visible too)
by_dump = collections.defaultdict(list)
by_name = collections.defaultdict(list)
by_blind = collections.defaultdict(list)
by_file = collections.defaultdict(list)
unit_bodies = {}
for dp, dn, fn in os.walk(os.path.join(pristine, "sympy")):
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, pristine)
        try:
            tree = ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError:
            continue
        for q, nodes in restorelib.index_functions(tree).items():
            for occ, node in enumerate(nodes):
                rest = body_of(node)
                if not rest:
                    continue
                key = (rel, q, occ)
                nn = nnodes(rest)
                rec = (key, node.name, norm(rest), text(rest), len(rest), nn, blind(rest) if nn >= 25 else None)
                if key in unit_keys:
                    unit_bodies[key] = rec
                else:
                    by_dump[rec[2]].append(rec)
                    by_name[node.name].append(rec)
                    by_file[rel].append(rec)
                    if rec[6] is not None:
                        by_blind[rec[6]].append(rec)
drop, why = [], collections.Counter()
for u in units:
    key = (u["file"], u["qualname"], u.get("occ", 0))
    rec = unit_bodies.get(key)
    if rec is None:
        continue
    _, name, dump, txt, n, nn, bl = rec
    nst = u["n_stmts"]
    exact = by_dump.get(dump, [])
    same_name_exact = [r for r in exact if r[1] == name]
    hit = None
    if same_name_exact:
        hit = "exact-same-name"
    elif exact and (nst >= 3 or nn >= 12):
        hit = "exact-other-name"
    elif bl is not None and by_blind.get(bl):
        hit = "same-after-renaming"
    elif nst >= 2:
        for r in by_name.get(name, []) + by_file.get(u["file"], []):
            if abs(len(r[3]) - len(txt)) > 0.3 * max(len(txt), 1):
                continue
            if difflib.SequenceMatcher(None, txt, r[3], autojunk=False).ratio() >= 0.85:
                hit = "similar-same-name" if r[1] == name else "similar-sibling"
                break
    if hit:
        drop.append(u["dotted"])
        why[hit] += 1
json.dump(sorted(drop), open(outp, "w"))
print("units with a surviving twin:", len(drop), dict(why))
k = collections.Counter("/".join(d.split(".")[1:3]) for d in drop)
print(k.most_common(12))
