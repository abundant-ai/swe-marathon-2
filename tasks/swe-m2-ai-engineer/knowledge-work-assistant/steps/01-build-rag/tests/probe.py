"""Public interface observations, executed only as the unprivileged candidate."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import runpy
import sys
from pathlib import Path
from types import FrameType, ModuleType
from typing import Any, get_args, get_origin, get_type_hints, is_typeddict


def check_record(record: object, fields: dict[str, object]) -> None:
    """Check a TypedDict's required fields without imposing an internal design.

    Args:
        record: Resolved annotation from the submitted module.
        fields: Required field names and types.

    Raises:
        AssertionError: The declared public type has missing or invalid fields.
    """
    assert is_typeddict(record), "Public structured types must be TypedDicts"
    hints = get_type_hints(record)
    assert set(fields) <= record.__required_keys__, "Fields must be required"
    for name, expected in fields.items():
        assert hints.get(name) == expected, f"Incorrect type for {name}"


def check_interfaces(module: ModuleType) -> None:
    """Validate the three async functions and their structured annotations.

    Args:
        module: Candidate main.py loaded in the candidate subprocess.

    Raises:
        AssertionError: A required function, parameter, or type is missing.
    """
    event = getattr(module, "IngestEvent")
    retrieved = getattr(module, "RetrievedItem")
    generated = getattr(module, "GeneratedAnswer")
    check_record(event, {"corpus_path": str, "refresh": bool})
    for record, field in ((retrieved, "passages"), (generated, "citations")):
        assert is_typeddict(record)
        assert field in record.__required_keys__
        annotation = get_type_hints(record)[field]
        assert get_origin(annotation) is list
        check_record(get_args(annotation)[0], {"doc_id": str, "quote": str})
    check_record(generated, {"answer": str})
    for name, parameter, parameter_type, result_type in (
        ("ingest", "event", event, type(None)),
        ("retrieve", "query", str, retrieved),
        ("generate", "query", str, generated),
    ):
        function = getattr(module, name)
        assert inspect.iscoroutinefunction(function), f"{name} must be async"
        signature = inspect.signature(function)
        assert tuple(signature.parameters) == (parameter,), f"Incorrect {name} arguments"
        hints = get_type_hints(function)
        assert hints.get(parameter) is parameter_type
        assert hints.get("return") is result_type


def main() -> None:
    """Perform one observation and append a JSON result after application output.

    A profile hook observes calls to the exported functions, including references
    imported under aliases. It is behavioral evidence, not a security sandbox.
    """
    request = json.loads(sys.stdin.read())
    sys.path.insert(0, str(Path.cwd()))
    module = importlib.import_module("main")
    operation = request["operation"]
    calls: set[str] = set()
    codes = {
        getattr(module, name).__code__: name
        for name in ("ingest", "retrieve", "generate")
    }

    def record_call(frame: FrameType, event: str, arg: object) -> None:
        """Record entry into exported application functions.

        Args:
            frame: Executing Python frame.
            event: Profiler event name.
            arg: Profiler payload; unused for call events.
        """
        if event == "call" and frame.f_code in codes:
            calls.add(codes[frame.f_code])

    value: object = None
    exit_code = 0
    sys.setprofile(record_call)
    try:
        if operation == "interfaces":
            check_interfaces(module)
        elif operation == "cli":
            sys.argv = ["orange", *request["payload"]]
            try:
                runpy.run_path(str(Path.cwd() / "cli.py"), run_name="__main__")
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        else:
            value = asyncio.run(getattr(module, operation)(request["payload"]))
    finally:
        sys.setprofile(None)
    print("\nORANGE_PROBE=" + json.dumps({"value": value, "calls": sorted(calls), "exit_code": exit_code}))


if __name__ == "__main__":
    main()
