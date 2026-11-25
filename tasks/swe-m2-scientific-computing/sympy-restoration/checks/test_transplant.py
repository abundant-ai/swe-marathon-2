"""Only unit bodies travel from the submitted tree into the graded tree."""


def test_only_accepted_unit_bodies_reach_the_graded_tree(scenario):
    data = scenario("transplant")
    assert data["states"]["U0001"] == "restored"
    assert data["states"]["U0002"] == "todo"
    assert data["states"]["U0003"].startswith("rejected")
    candidate = data["candidate"]
    assert "return x * 2" in candidate
    # edits outside unit bodies and rejected bodies never arrive
    assert "return x + 1\n" in candidate and "x + 100" not in candidate
    assert "HELPER" not in candidate and "os.getcwd" not in candidate
    assert 'raise NotImplementedError("RESTORE U0003")' in candidate


def test_missing_file_keeps_the_skeleton(scenario):
    data = scenario("transplant")
    assert data["missing_states"] == {"U0001": "missing"}
    assert data["missing_is_skeleton"] is True


def test_routes_to_the_process_and_to_files_are_rejected_and_every_original_body_passes(task_root):
    """The re-checks' routes, each a construct no original body uses, are rejected; every original body
    of a unit still passes the same rules."""
    import ast
    import sys

    sys.path.insert(0, str(task_root / "common"))
    import restorelib

    hostile = {
        "posixpath.os": "import posixpath\nreturn posixpath.os.getcwd()",
        "random._os": "return random._os",
        "import_module posix": "return import_module('posix')",
        "sys.modules": "return sympy.utilities.misc.sys.modules",
        "codecs.open": "import codecs\nreturn codecs.open('f', 'w')",
        "logging": "import logging\nreturn logging.FileHandler('f')",
        "preview": "from sympy import preview\nreturn preview(x, viewer='BytesIO', outputbuffer=None, outputTexFile='/tmp/f')",
        "preview attribute": "return sympy.preview(x)",
        "runtests attribute": "return sympy.testing.runtests",
        "traceback frames": "try:\n    1 / 0\nexcept Exception as e:\n    return e.__traceback__",
        "attrgetter": "from operator import attrgetter\nreturn attrgetter('f_back')(x)",
        "attrgetter dotted": "return operator.attrgetter('tb_frame.f_back')(x)",
        "methodcaller": "return operator.methodcaller('write', 'x')(x)",
        "json rebinding": "import json\njson.dumps = str\nreturn 1",
        "a handle's write": "return x.write('data')",
        "getattr os": "return getattr(posixpath, 'os')",
    }
    for name, body in hostile.items():
        tree = ast.parse("def f(x):\n" + "\n".join("    " + line for line in body.split("\n")))
        assert restorelib.scan_body(tree.body[0].body, tree.body[0]) is not None, name
    allowed = {"getattr": "return getattr(x, 'name')", "import_module": "return import_module('z3')",
               "list.remove": "x.remove(1)\nreturn x", "operator": "return operator.add(x, 1)"}
    for name, body in allowed.items():
        tree = ast.parse("def f(x):\n" + "\n".join("    " + line for line in body.split("\n")))
        assert restorelib.scan_body(tree.body[0].body, tree.body[0]) is None, name
    units, byfile = restorelib.load_units(str(task_root / "environment" / "data" / "units.json"))
    original = task_root / "steps" / "01-restore-bodies" / "solution" / "data"
    rejected = []
    for rel, keys in byfile.items():
        functions = restorelib.index_functions(ast.parse((original / rel).read_text(encoding="utf-8")))
        for key, uid in keys.items():
            name, occ, _nocc = restorelib._split_key(key)
            fn = functions[name][occ]
            _doc, rest = restorelib._doc_and_rest(fn)
            if restorelib.scan_body(rest, fn) is not None:
                rejected.append(uid)
    assert units and rejected == [], rejected[:10]
