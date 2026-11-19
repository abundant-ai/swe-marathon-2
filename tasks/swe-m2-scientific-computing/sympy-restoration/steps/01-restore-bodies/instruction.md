# Restore the missing function bodies of SymPy

## Goal

`/app/sympy` is a checkout of SymPy 1.14.0, a pure-Python computer algebra library. The
bodies of 2,671 functions and methods, spread over 355 files, are gone. I need them written
back, so that the library again behaves as its docstrings and its tests say it does.

## Context

Each missing body was replaced by one placeholder statement:

```python
raise NotImplementedError("RESTORE U0421")
```

`U0421` is the unit id, and each of these functions is a unit. Signatures, decorators,
docstrings and every other function are intact. Some of the upstream tests are not in this
checkout; the tests that are here are unmodified.

There is no network access. SymPy is not installed anywhere else in the image; `mpmath`,
its only dependency, is. Licence and provenance are in `/app/ATTRIBUTION.txt`.

## What to deliver

The restored bodies, in place, in `/app/sympy`.

A body is right when the function behaves as SymPy 1.14.0 does: for the examples in its
docstring, for the repository's tests, and for every other valid input. Returning the
documented outputs for the documented inputs is not a restoration. Speed is part of the
behaviour: restored code should not be more than about three times slower than SymPy 1.14.0
itself on the library's own examples and tests.

Only the bodies of the units are part of the deliverable:

- Leave signatures, decorators, docstrings, module-level code, other functions and tests as
  they are. Changes outside unit bodies are not taken over.
- A body may use every name already defined or imported in its module, may define nested
  helpers, and may import inside the function. Write each body in the style of its module.
- Leave each function where it is. Do not rename, move or delete a unit, and do not add
  another definition with the same name in the same file.
- A body must not contain constructs for reaching the process, the file system, the
  interpreter or a test framework. That covers imports such as `os`, `sys`, `subprocess`,
  `importlib`, `inspect`, `io`, `builtins`, `doctest`, `pytest`, `unittest` and SymPy's own
  testing modules (also when the module already imports them); builtins such as `eval`,
  `exec`, `compile`, `open`, `__import__`, `globals` and `locals`; and attributes that
  expose interpreter internals, such as `__globals__`, `__code__`, `__subclasses__`,
  `f_back`, `stdout` or `stderr`. `restore rules` prints the complete list. No original
  body needed any of these, and a body that uses one is rejected.
  `restore check` shows such a body as `BROKEN` and names the construct.
- Do not change how the library's examples or tests are run or how they report results.
- Keep every file a regular, UTF-8 encoded Python file under 4 MB that parses. If a file
  does not parse, none of the bodies in it can be used.

## Tools

The `restore` command (on `PATH`) reports progress and checks your work in delivered form:
the original skeleton with your unit bodies in it, and nothing else from your tree.

| Command | What it does |
| --- | --- |
| `restore status` | Summary: units to do, restored, and how they fared when last checked. |
| `restore next 10` | The next 10 units to restore, in a suggested order that mostly puts a unit after the units it calls. Add `--file /app/sympy/ntheory/factor_.py` (or a directory) to narrow it. |
| `restore show U0421` | File, line numbers, signature and docstring of a unit. |
| `restore check U0421 U0422` | Run the docstring examples of these units. Also accepts a file or directory, `--all`, `--failed`, `--unchecked`, and `-q` for a short report. |
| `restore pytest /app/sympy/ntheory/tests/test_factor_.py -x` | Run repository tests against the delivered form of your tree. Arguments are passed to pytest. |
| `restore rules` | The complete list of constructs a body may not use. |
| `restore sync FILE` | Rewrite a file in delivered form (skeleton plus your bodies). Refused while a body in the file is rejected or the file does not parse. |
| `restore reset FILE` | Put a file back to its original skeleton state. |

`restore check` prints one line per unit:

- `PASS`: every example passes.
- `FAIL`: the first failing example follows, with expected and actual output (for up to
  three failing units per call).
- `BLOCKED`: the first failing example calls another unit that is not restored yet. Restore
  that one first.
- `TODO`: the placeholder is still there.
- `BROKEN`: the body was rejected or the file does not parse; the reason is printed.

## Time and completion

- You have 12 hours of wall-clock time at most, and the run can end before then;
  `/app/timer.sh` prints the seconds that remain. Plan the work to fit, and keep going until
  the work is complete or the time is up.
- Keep a running log in `/app/PROGRESS.md`, so that anyone looking in can see where the work
  stands. When you start, then at least every 30 minutes and whenever you finish a module,
  append one line with the time (`date -u`), the counts that `restore status` prints, and
  what you will do next.
- The work is complete when no unit is left to restore, `restore check --all` reports every
  unit as `PASS`, and the repository tests pass under `restore pytest`. Work that is not
  finished is delivered as it stands.
- A wrong body in a function that many others call makes later units fail, so a unit is
  worth checking before others are built on it. `restore status` summarises earlier
  checks; only `restore check` re-runs them.
- `restore check --all` takes a few minutes. Checking single units, files or directories is
  much faster.
