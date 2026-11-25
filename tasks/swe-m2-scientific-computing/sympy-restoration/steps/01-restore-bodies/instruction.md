# Restore the missing function bodies of SymPy

## Goal

`/app/sympy` is a checkout of SymPy 1.14.0, a pure-Python computer algebra library. The
bodies of 2,176 functions and methods, spread over 324 files, are gone. I need them written
back, so that the library again behaves as its docstrings and its tests say it does.

## Context

Each missing body was replaced by one placeholder statement:

```python
raise NotImplementedError("RESTORE U0421")
```

`U0421` is the unit id, and each of these functions is a unit. Signatures, decorators,
docstrings and every other function are intact. Some of the upstream tests are not in this
checkout; the tests that are here are unmodified.

There is no network access. The only other copies of this tree in the image are the
`restore` tool's own, under `/opt/restore`, and they are as damaged as this one; `mpmath`,
SymPy's only dependency, is installed. Licence and provenance are in `/app/ATTRIBUTION.txt`.

Write the bodies yourself, from what is in this copy and what you know. Another copy of
SymPy's source, from an installed package, a download, a mirror or any other place, is not to
be used, in whole or in part.

## What to deliver

The restored bodies, in place, in `/app/sympy`.

A body is right when the function behaves exactly as SymPy 1.14.0's does: for the examples
in its docstring, for the repository's tests, and for every other argument it accepts. Which
error it raises for an argument it does not accept I need only where an example or a test
shows it. The same means the same, not an
equivalent: the same type and container, the same order, the same form of a returned
expression, and the same state of every object the function builds or changes, apart from
values kept only as a cache. Where the docstring and the tests leave such a detail open, the
code that calls the function and the habits of its module are the evidence. Returning the
documented outputs for the documented inputs is not a restoration. Speed is part of the
behaviour: restored code should not be much slower than SymPy 1.14.0 itself on the library's
own examples and tests.

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

- The run can end at any time, so keep the work runnable and the log below current. Keep
  going until the work is complete.
- Keep a running log in `/app/PROGRESS.md` of where the work stands, so that it can be taken
  up again after a break. When you start, then at least every 30 minutes and whenever you
  finish a module, append one line with the time (`date -u`), the counts that
  `restore status` prints, and what you will do next. The log is not part of what you
  deliver.
- The work is complete when every function returns and changes exactly what SymPy 1.14.0's
  does, and raises what its examples and tests show. No unit left to restore,
  `restore check --all` reporting every unit as `PASS` and the repository tests passing
  under `restore pytest` are the least of that: a function must also return and change what
  the original does for arguments that no example or test uses. Work that is not finished is
  delivered as it stands when your session ends.
- A wrong body in a function that many others call makes later units fail, so a unit is
  worth checking before others are built on it. `restore status` summarises earlier
  checks; only `restore check` re-runs them.
- `restore check --all` takes a few minutes. Checking single units, files or directories is
  much faster.
