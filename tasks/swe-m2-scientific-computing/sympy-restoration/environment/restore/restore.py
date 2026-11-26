#!/usr/bin/env python3
"""restore - workspace helper for restoring SymPy's function bodies.

  restore status                 progress summary
  restore next [N] [--file F]    next N units still to restore; F is a file or a directory
  restore show UID               where the unit is and what its docstring specifies
  restore rules                  the complete list of constructs a body may not use
  restore check UID... | FILE... | --all | --failed | --unchecked   [-q]
                                 run the docstring examples of restored units (20 s per
                                 unit); the first failing example is shown for up to
                                 three failing units per call
  restore pytest [pytest args]   run the repository tests on your tree as the build takes it
                                 (60 s per test unless --timeout is given)
  restore sync FILE              rewrite FILE as the build takes it (refused while a body
                                 in it uses a listed construct or the file does not parse)
  restore reset FILE             put FILE back to its blanked state

The build takes only the bodies of the restorable functions from your tree;
`check` and `pytest` run on your tree in that form.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys

BASE = os.environ.get("RESTORE_BASE", "/opt/restore")
WORK = os.environ.get("RESTORE_WORK", "/app")
SKEL = os.path.join(BASE, "skeleton")
VAR = os.environ.get("RESTORE_VAR", os.path.join(BASE, "var"))
CAND = os.path.join(VAR, "cand")
UNITS = os.path.join(BASE, "units.json")
STATE = os.path.join(VAR, "state.json")
sys.path.insert(0, os.path.join(BASE, "lib"))
import restorelib  # noqa: E402

UNITCHECK = os.path.join(BASE, "lib", "unitcheck.py")


RESTARTS = 8


def run_examples(names_by_module, workers, timeout=20.0):
    """Run docstring examples, one process per module. Returns {dotted: result}.

    A unit that ends its process, or keeps it busy past its time, fails alone: the
    units behind it run again in a new process, at most RESTARTS times per module.
    """
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    scratch = tempfile.mkdtemp(prefix="restore-check-")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")

    def run(k, mod, names, start):
        npath = os.path.join(scratch, f"n{k}.{start}.json")
        with open(npath, "w", encoding="utf-8") as f:
            json.dump(names, f)
        out, err, code = "", "", None
        try:
            p = subprocess.run([sys.executable, "-P", "-s", "-B", UNITCHECK, CAND, mod, npath, str(timeout)],
                               capture_output=True, text=True, env=env, cwd=CAND,
                               timeout=min(timeout * (len(names) + 2) + 60, 900))
            out, err, code = p.stdout, p.stderr[-300:], p.returncode
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = "the unit did not finish in time"
        got, merr = {}, None
        for line in out.splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and "name" in rec:
                got.setdefault(rec["name"], rec)
            elif isinstance(rec, dict) and "module_error" in rec:
                merr = rec
        return got, merr, err, code

    def one(item):
        k, (mod, names) = item
        res, pending, crashes, starts = {}, list(names), 0, 0
        while pending:
            got, merr, err, code = run(k, mod, pending, starts)
            starts += 1
            if merr is not None:
                for n in pending:
                    res[n] = {"status": "error", "exc": "module import failed: " + merr["module_error"],
                              "blocked_by": merr.get("blocked_by") or [], "out": merr.get("tb", "")}
                break
            res.update({n: rec for n, rec in got.items() if n in pending})
            rest = [n for n in pending if n not in got]
            if not rest:
                break
            if code == 3 and len(rest) < len(pending):
                pending = rest   # the runner started afresh after a unit that ran out of time
                continue
            # the process ended, or stopped, at the first unit without a result
            res[rest[0]] = {"status": "crash", "exc": err or "the runner ended during this unit"}
            pending, crashes = rest[1:], crashes + 1
            if crashes > RESTARTS:
                for n in pending:
                    res[n] = {"status": "crash", "exc": "runner stopped before this unit"}
                break
        return res

    results = {}
    try:
        with ThreadPoolExecutor(max(1, workers)) as ex:
            for res in ex.map(one, list(enumerate(sorted(names_by_module.items())))):
                results.update(res)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return results


def load_state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"files": {}, "results": {}}


def save_state(st):
    tmp = STATE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f)
        os.replace(tmp, STATE)
    except OSError as e:
        print(f"warning: could not save checker state ({e}); results are still valid")


def refresh(st):
    units, byfile = restorelib.load_units(UNITS)
    states, notes = restorelib.build_candidate(SKEL, WORK, CAND, byfile, st["files"])
    return units, byfile, states, notes


def body_sig(u):
    """Signature of the candidate file holding the unit (results are per file content)."""
    try:
        return hashlib.sha1(open(os.path.join(CAND, u["file"]), "rb").read()).hexdigest()[:16]
    except OSError:
        return ""


def current_line(u, cache={}):
    """Line of the unit's def in the work tree (best effort)."""
    f = u["file"]
    if f not in cache:
        try:
            tree = ast.parse(open(os.path.join(WORK, f), encoding="utf-8").read())
            cache[f] = restorelib.index_functions(tree)
        except (OSError, SyntaxError, ValueError):
            cache[f] = {}
    nodes = cache[f].get(u["qualname"]) or []
    occ = u.get("occ", 0)
    return nodes[occ].lineno if len(nodes) > occ else 0


def fresh_result(st, u, sig=None):
    r = st["results"].get(u["uid"])
    if r and r.get("sig") == (sig or body_sig(u)):
        return r
    return None


def cmd_status(args):
    st = load_state()
    units, byfile, states, notes = refresh(st)
    save_state(st)
    n = len(units)
    todo = sum(1 for u in units if states[u["uid"]] == "todo")
    bad = [u for u in units if states[u["uid"]] not in ("todo", "restored")]
    restored = [u for u in units if states[u["uid"]] == "restored"]
    ok = fail = blocked = unchecked = 0
    for u in restored:
        r = fresh_result(st, u)
        if r is None:
            unchecked += 1
        elif r["status"] == "pass":
            ok += 1
        elif r["status"] == "blocked":
            blocked += 1
        else:
            fail += 1
    print(f"units {n} | todo {todo} | restored {len(restored)}: pass {ok}, failing {fail}, blocked {blocked}, "
          f"unchecked {unchecked}" + (f" | broken {len(bad)}" if bad else "") + "   (results as of each unit's last check)")
    for u in bad[:10]:
        print(f"  {u['uid']} {u['file']}::{u['qualname']} -> {states[u['uid']]}")
    if len(bad) > 10:
        print(f"  ... and {len(bad) - 10} more broken")
    for rel in notes[:5]:
        print(f"  note: {rel} has edits outside restorable bodies; they do not reach the build")
    if todo:
        nxt = min((u for u in units if states[u["uid"]] == "todo"), key=lambda u: u["order"])
        print(f"next: {nxt['uid']} {nxt['file']}:{current_line(nxt)} {nxt['qualname']}")
    if todo == 0 and not bad and fail == 0 and blocked == 0 and unchecked == 0:
        print("Every unit is restored and its docstring examples passed when last checked. `restore check --all` re-runs all of them.")
    elif todo == 0 and not bad:
        print("No unit left to restore; run `restore check --failed --unchecked` and fix what fails.")


def cmd_next(args):
    k = 10
    only = None
    it = iter(args)
    for a in it:
        if a == "--file":
            only = next(it, None)
        elif a.isdigit():
            k = int(a)
    st = load_state()
    units, byfile, states, notes = refresh(st)
    save_state(st)
    if only:
        only = os.path.relpath(os.path.abspath(only), WORK) if os.path.isabs(only) or os.path.exists(only) else only
    def in_scope(u):
        return not only or u["file"] == only or u["file"].startswith(only.rstrip("/") + "/")

    todo = [u for u in sorted(units, key=lambda u: u["order"]) if states[u["uid"]] == "todo" and in_scope(u)]
    for u in todo[:k]:
        print(f"{u['uid']}  {u['file']}:{current_line(u)}  {u['qualname']}")
    if only and not any(in_scope(u) for u in units):
        print(f"no restorable unit under '{only}'")
        return 2
    print(f"-- {len(todo)} to restore" + (f" in {only}" if only else ""))


def find_unit(units, key):
    for u in units:
        if u["uid"] == key or u["dotted"] == key or f"{u['file']}::{u['qualname']}" == key:
            return u
    return None


def cmd_show(args):
    if not args:
        print("usage: restore show UID")
        return 2
    units, byfile = restorelib.load_units(UNITS)
    u = find_unit(units, args[0])
    if u is None:
        print("unknown unit:", args[0])
        return 2
    path = os.path.join(WORK, u["file"])
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    try:
        nodes = restorelib.index_functions(ast.parse(src)).get(u["qualname"]) or []
        fn = nodes[u.get("occ", 0)] if len(nodes) > u.get("occ", 0) else None
    except SyntaxError as e:
        print(f"{u['file']} does not parse (line {e.lineno}); fix it first")
        return 1
    if fn is None:
        print(f"{u['uid']}: function {u['qualname']} not found in {u['file']} (was it renamed or deleted?)")
        return 1
    doc, rest = restorelib._doc_and_rest(fn)
    start = min([d.lineno for d in fn.decorator_list] + [fn.lineno])
    end = doc.end_lineno if doc is not None else fn.lineno
    print(f"{u['uid']}  {u['file']}  {u['qualname']}  (def at line {fn.lineno}, body lines {end + 1}-{fn.end_lineno})")
    for i in range(start, end + 1):
        print(f"{i:6d}  {lines[i - 1]}")


def select_units(units, states, st, args):
    sel = []
    flags = {a for a in args if a.startswith("--")}
    keys = [a for a in args if not a.startswith("-")]
    if "--all" in flags:
        sel = list(units)
    if "--failed" in flags:
        for u in units:
            r = fresh_result(st, u)
            if states[u["uid"]] not in ("todo", "restored") or (states[u["uid"]] == "restored" and r is not None and r["status"] != "pass"):
                sel.append(u)
    if "--unchecked" in flags:
        sel += [u for u in units if states[u["uid"]] == "restored" and fresh_result(st, u) is None]
    for k in keys:
        u = find_unit(units, k)
        if u is not None:
            sel.append(u)
            continue
        rel = k
        if os.path.exists(k):
            rel = os.path.relpath(os.path.abspath(k), WORK)
        hit = [u for u in units if u["file"] == rel or u["file"].startswith(rel.rstrip("/") + "/")]
        if not hit:
            print(f"no restorable unit matches '{k}'")
        sel += hit
    seen = set()
    out = []
    for u in sel:
        if u["uid"] not in seen:
            seen.add(u["uid"])
            out.append(u)
    return out


def excerpt(out, limit=22):
    lines = [ln for ln in (out or "").split("\n")]
    # first failure block only
    blocks = []
    cur = []
    for ln in lines:
        if ln.startswith("*" * 20):
            if cur:
                blocks.append(cur)
            cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    first = blocks[0] if blocks else []
    first = [ln for ln in first if ln.strip()]
    if len(first) > limit:
        first = first[: limit - 6] + ["    ..."] + first[-5:]
    return "\n".join("    " + ln[:200] for ln in first), len(blocks)


def cmd_check(args):
    if not args:
        print("usage: restore check UID... | FILE... | --all | --failed | --unchecked   [-q]")
        return 2
    quiet = "-q" in args
    args = [a for a in args if a != "-q"]
    st = load_state()
    units, byfile, states, notes = refresh(st)
    by_uid = {u["uid"]: u for u in units}
    sel = select_units(units, states, st, args)
    if not sel:
        save_state(st)
        print("nothing to check")
        return 0
    run = {}
    for u in sel:
        if states[u["uid"]] == "restored":
            run.setdefault(u["module"], []).append(u["dotted"])
    results = {}
    if run:
        workers = min(len(run), max(1, min(os.cpu_count() or 2, 4)))
        results = run_examples(run, workers, timeout=20.0)
    counts = {"pass": 0, "fail": 0, "todo": 0, "blocked": 0, "broken": 0}
    shown = 0
    for u in sel:
        s = states[u["uid"]]
        tag = f"{u['uid']} {u['file']}::{u['qualname']}"
        if s == "todo":
            counts["todo"] += 1
            if not quiet:
                print(f"TODO     {tag}")
            continue
        if s != "restored":
            counts["broken"] += 1
            print(f"BROKEN   {tag}\n    {s}")
            continue
        r = results.get(u["dotted"], {"status": "crash"})
        blocked = []
        if r["status"] != "pass":
            blocked = [b for b in r.get("blocked_by", []) if b != u["uid"] and states.get(b) != "restored"]
            # only when the first failing example is the missing unit: a failure before that
            # is the body's own
            if blocked and r["status"] == "fail" and not r.get("first_blocked", True):
                blocked = []
        st["results"][u["uid"]] = {"status": "blocked" if blocked else r["status"], "sig": body_sig(u)}
        if r["status"] == "pass":
            counts["pass"] += 1
            if not quiet:
                print(f"PASS     {tag}")
            continue
        if blocked:
            counts["blocked"] += 1
            names = ", ".join(f"{b} ({by_uid[b]['file']}::{by_uid[b]['qualname']})" if b in by_uid else b for b in blocked[:3])
            print(f"BLOCKED  {tag}\n    needs a unit that is not restored: {names}{' ...' if len(blocked) > 3 else ''}")
            continue
        counts["fail"] += 1
        head = f"FAIL     {tag}"
        if r["status"] == "timeout":
            head += "  (timed out after 20s)"
        elif r["status"] in ("error", "crash", "notfound"):
            head += f"  ({r.get('exc') or r['status']})"
        elif "failed" in r:
            head += f"  ({r['failed']} of {r['tried']} examples fail)"
        print(head)
        if shown < 3 or len(sel) <= 3:
            ex, nblocks = excerpt(r.get("out"))
            if ex:
                print(ex)
            shown += 1
    save_state(st)
    for rel in notes[:5]:
        print(f"note: {rel} has edits outside restorable bodies; they do not reach the build")
    print("checked {}: {} pass, {} fail, {} blocked, {} todo{}".format(
        len(sel), counts["pass"], counts["fail"], counts["blocked"], counts["todo"],
        f", {counts['broken']} broken" if counts["broken"] else ""))
    left = [u for u in units if states[u["uid"]] == "todo"]
    if left:
        nxt = min(left, key=lambda u: u["order"])
        print(f"{len(left)} of {len(units)} units still to restore; next: "
              f"{nxt['uid']} {nxt['file']}:{current_line(nxt)} {nxt['qualname']}")
    return 0 if counts["fail"] == 0 and counts["broken"] == 0 and counts["blocked"] == 0 and counts["todo"] == 0 else 1


def cmd_pytest(args):
    st = load_state()
    refresh(st)
    save_state(st)
    base = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q"]
    if not any(a.startswith("--timeout") for a in args):
        base += ["--timeout", "60"]
    # paths inside the work tree, absolute or relative to the current directory, are run
    # on the tree in the form the build takes
    mapped = []
    root = os.path.realpath(WORK)
    for a in args:
        head = a.split("::")[0]
        if head and not head.startswith("-"):
            full = os.path.realpath(head)
            if (full == root or full.startswith(root + os.sep)) and os.path.exists(full):
                a = os.path.relpath(full, root) + a[len(head):]
        mapped.append(a)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    return subprocess.call(base + mapped, cwd=CAND, env=env)


def _rel(arg):
    return os.path.relpath(os.path.abspath(arg), WORK) if os.path.exists(arg) else arg


def cmd_sync(args):
    if len(args) != 1:
        print("usage: restore sync FILE")
        return 2
    st = load_state()
    units, byfile, states, notes = refresh(st)
    save_state(st)
    rel = _rel(args[0])
    if rel not in byfile:
        print(f"{rel}: no restorable unit in this file")
        return 2
    lost = [uid for uid in byfile[rel].values() if states.get(uid) not in ("restored", "todo")]
    if lost:
        print(f"{rel}: not rewritten. {len(lost)} unit(s) in it use a listed construct or the file does not parse, "
              "and rewriting would replace their bodies with placeholders. Fix them first (see `restore check`).")
        return 1
    shutil.copyfile(os.path.join(CAND, rel), os.path.join(WORK, rel))
    print(f"{rel} rewritten as the build takes it (the blanked file + your restored bodies)")


def cmd_reset(args):
    if len(args) != 1:
        print("usage: restore reset FILE")
        return 2
    rel = _rel(args[0])
    src = os.path.join(SKEL, rel)
    if not os.path.isfile(src):
        print(f"{rel}: not a file of the checkout")
        return 2
    shutil.copyfile(src, os.path.join(WORK, rel))
    print(f"{rel} reset to its blanked state (restored bodies in it are gone)")


def cmd_rules(args):
    print(restorelib.rules_text())


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, args = argv[0], argv[1:]
    fn = {"status": cmd_status, "next": cmd_next, "show": cmd_show, "check": cmd_check,
          "pytest": cmd_pytest, "sync": cmd_sync, "reset": cmd_reset, "rules": cmd_rules}.get(cmd)
    if fn is None:
        print(f"unknown command '{cmd}'\n\n" + __doc__.strip())
        return 2
    return fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
