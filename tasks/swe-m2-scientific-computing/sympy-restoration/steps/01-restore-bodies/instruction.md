# Restore the missing function bodies of SymPy

## Goal

Our analysis service is built on SymPy 1.14.0, a pure-Python computer algebra library, and our
build takes SymPy from the copy in `/app/sympy`. A faulty clean-up step in our packaging blanked
the bodies of 2,114 functions and methods, spread over 322 files, before anyone noticed. I need
them written back, so that our code, and the parts of SymPy that call these functions, work again.

## Context

Each blanked body was replaced by one placeholder statement:

```python
raise NotImplementedError("RESTORE U0421")
```

`U0421` is the unit id, and each of these functions is a unit. Signatures, decorators,
docstrings and every function that was not blanked are intact. The same clean-up also dropped
part of SymPy's own test suite from this copy; the tests that are left are unmodified.

There is no network access. The only other copies of this tree in the image are the
`restore` tool's own, under `/opt/restore`, and they are blanked the same way; `mpmath`,
SymPy's only dependency, is installed. Licence and provenance are in `/app/ATTRIBUTION.txt`.

Our build runs offline and takes in only this copy and code written here, so write the bodies
yourself, from what is in this copy and what you know. Another copy of SymPy's source, from an
installed package, a download, a mirror or any other place, is not to be used, in whole or in
part.

## What to deliver

The restored bodies, in place, in `/app/sympy`.

Our code calls these functions with its own arguments, well beyond the examples in their
docstrings and the repository's tests, and relies on what SymPy 1.14.0 gives back for any
argument a function accepts: the same value, of the same type and container, in the same
order, a returned expression in the same form, and the same state of every object the function
builds or changes, apart from values kept only as a cache. An equal value of another kind
breaks it: an `int` where SymPy gives an `Integer`, a list where it gives a tuple, or the same
expression written another way. Which error a function raises for an argument it does not
accept matters to us only where an example in its docstring shows it. Where the docstring and
the tests leave such a detail open, the code that calls the function and the habits of its
module are the evidence. Our code runs these functions over many arguments in a row, so
restored code should not be much slower than SymPy 1.14.0 itself on the library's own examples
and tests.

Our build takes only the bodies of the units from your tree:

- Leave signatures, decorators, docstrings, module-level code, other functions and tests as
  they are. Changes outside unit bodies do not reach the build.
- A body may use every name already defined or imported in its module, may define nested
  helpers, and may import inside the function. Write each body in the style of its module.
- Leave each function where it is. Do not rename, move or delete a unit, and do not add
  another definition with the same name in the same file.
- A body must not use the constructs that `restore rules` lists, which reach the process, the
  file system, the interpreter or a test framework: imports such as `os`, `sys`, `subprocess`,
  `importlib`, `inspect`, `io`, `builtins`, `doctest`, `pytest`, `unittest` and SymPy's own
  testing modules (also when the module already imports them); builtins such as `eval`,
  `exec`, `compile`, `open`, `__import__`, `globals` and `locals`; and attributes that
  expose interpreter internals, such as `__globals__`, `__code__`, `__subclasses__`,
  `f_back`, `stdout` or `stderr`. None of SymPy 1.14.0's own bodies needs any of them, and
  our build does not take a body that uses one: `restore check` shows such a body as `BROKEN`
  and names the construct.
- Do not change how the library's examples or tests are run or how they report results.
- Keep every file a regular, UTF-8 encoded Python file under 4 MB that parses. If a file
  does not parse, none of the bodies in it can be used.

## Tools

The `restore` command (on `PATH`) reports progress and runs the examples and the tests on your
tree as our build takes it: the blanked copy with your unit bodies in it, and nothing else from
your tree.

| Command | What it does |
| --- | --- |
| `restore status` | Summary: units to do, restored, and how they fared when last checked. |
| `restore next 10` | The next 10 units to restore, in a suggested order that mostly puts a unit after the units it calls. Add `--file /app/sympy/ntheory/factor_.py` (or a directory) to narrow it. |
| `restore show U0421` | File, line numbers, signature and docstring of a unit. |
| `restore check U0421 U0422` | Run the docstring examples of these units. Also accepts a file or directory, `--all`, `--failed`, `--unchecked`, and `-q` for a short report. |
| `restore pytest /app/sympy/ntheory/tests/test_factor_.py -x` | Run repository tests on your tree as the build takes it. Arguments are passed to pytest. |
| `restore rules` | The complete list of constructs a body may not use. |
| `restore sync FILE` | Rewrite a file as the build takes it (the blanked file plus your bodies). Refused while a body in the file uses a listed construct or the file does not parse. |
| `restore reset FILE` | Put a file back to its blanked state. |

`restore check` prints one line per unit:

- `PASS`: every example passes.
- `FAIL`: the first failing example follows, with expected and actual output (for up to
  three failing units per call).
- `BLOCKED`: the first failing example calls another unit that is not restored yet. Restore
  that one first.
- `TODO`: the placeholder is still there.
- `BROKEN`: the body uses a listed construct or the file does not parse; the reason is
  printed.

## Working on it

- The run can end at any time, so keep the work runnable and the log below current. Keep
  going until every function is back.
- Keep a running log in `/app/PROGRESS.md` of where the work stands, so that it can be taken
  up again after a break. When you start, then at least every 30 minutes and whenever you
  finish a module, append one line with the time (`date -u`), the counts that
  `restore status` prints, and what you will do next. The log is not part of what you
  deliver.
- A wrong body in a function that many others call makes later units fail, so a unit is
  worth checking before others are built on it. `restore status` summarises earlier
  checks; only `restore check` re-runs them.
- `restore check --all` takes a few minutes. Checking single units, files or directories is
  much faster.

## Switching back

We switch our build back to this copy once every function gives back what SymPy 1.14.0 gives,
as described above, and raises what its examples show. No unit left to restore and
`restore check --all` reporting every unit as `PASS` come first; the repository tests under
`restore pytest` help beyond that. If the work stops before then, what is in `/app/sympy`
goes into the build as it stands.
