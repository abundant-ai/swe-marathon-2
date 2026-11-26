"""Generate the method-bind hash header for the QA telemetry native core.

Author tool (never packaged). The native core (common/probe/native/) calls engine methods
through `classdb_get_method_bind` and `variant_get_ptr_builtin_method`, which need the
signature hash of each method. The hashes come from the `extension_api.json` that the
pinned Godot binary dumps:

    <godot> --headless --dump-extension-api --dump-gdextension-interface

This script reads that dump and writes `common/probe/native/gen/binds.h` with one
`#define` per method the core uses, plus the engine constants it needs. It fails when a
method is missing or its signature changed, so an engine upgrade cannot silently leave
the core calling a method with the wrong arguments.

Usage:
  python scripts/gen_telemetry_binds.py --api PATH/extension_api.json [--out PATH]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
DEFAULT_OUT = TASK / "common/probe/native/gen/binds.h"

# (class, method, return type, argument types): what the native core expects. A
# mismatch with the dump means the core's calling convention no longer holds.
CLASS_METHODS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("Object", "get_meta", "Variant", ("StringName", "Variant")),
    ("Object", "has_meta", "bool", ("StringName",)),
    ("Object", "is_class", "bool", ("StringName",)),
    ("Object", "notification", "", ("int", "bool")),
    ("Node", "get_tree", "SceneTree", ()),
    ("Node", "get_index", "int", ("bool",)),
    ("Node", "set_physics_process_internal", "", ("bool",)),
    ("Node", "set_physics_process_priority", "", ("int",)),
    ("Node", "set_process_mode", "", ("enum::Node.ProcessMode",)),
    ("Node", "find_children", "typedarray::Node", ("String", "String", "bool", "bool")),
    ("Node", "get_parent", "Node", ()),
    ("Node", "is_in_group", "bool", ("StringName",)),
    ("Node", "get_viewport", "Viewport", ()),
    ("SceneTree", "get_nodes_in_group", "typedarray::Node", ("StringName",)),
    ("SceneTree", "get_root", "Window", ()),
    ("SceneTree", "quit", "", ("int",)),
    ("Node3D", "get_global_transform", "Transform3D", ()),
    ("Skeleton3D", "find_bone", "int", ("String",)),
    ("Skeleton3D", "get_bone_global_pose", "Transform3D", ("int",)),
    ("Skeleton3D", "get_bone_count", "int", ()),
    ("RigidBody3D", "get_linear_velocity", "Vector3", ()),
    ("CharacterBody3D", "get_real_velocity", "Vector3", ()),
    ("Engine", "get_physics_frames", "int", ()),
    ("Viewport", "get_camera_3d", "Camera3D", ()),
    ("Camera3D", "is_position_in_frustum", "bool", ("Vector3",)),
    ("JSON", "parse_string", "Variant", ("String",)),
)

# (builtin type, method, return type)
BUILTIN_METHODS: tuple[tuple[str, str, str], ...] = (
    ("Array", "size", "int"),
    ("Dictionary", "keys", "Array"),
    ("Dictionary", "size", "int"),
)

# (class, constant or enum value name, kind) where kind is "constant" or an enum name.
CONSTANTS: tuple[tuple[str, str, str], ...] = (
    ("Object", "NOTIFICATION_POSTINITIALIZE", "constant"),
    ("Object", "NOTIFICATION_PREDELETE", "constant"),
    ("Node", "NOTIFICATION_EXIT_TREE", "constant"),
    ("Node", "NOTIFICATION_READY", "constant"),
    ("Node", "NOTIFICATION_INTERNAL_PHYSICS_PROCESS", "constant"),
    ("Node", "PROCESS_MODE_ALWAYS", "ProcessMode"),
)


def method_hash(
    api: dict, cls: str, method: str, ret: str, args: tuple[str, ...]
) -> int:
    """Return the signature hash of one engine class method, checking its signature.

    Called by `render_header` for every entry of CLASS_METHODS.

    Args:
        api: The parsed extension_api.json of the pinned engine binary.
        cls: Engine class name, such as "Node3D".
        method: Method name on that class (not inherited from a parent class).
        ret: Expected return type as the dump spells it ("" for no return value).
        args: Expected argument types in order, as the dump spells them.

    Returns:
        The method's hash, to pass to classdb_get_method_bind.

    Raises:
        KeyError: The class or method is not in the dump.
        ValueError: The method's return or argument types differ from the expectation.
    """
    classes = {c["name"]: c for c in api["classes"]}
    methods = {m["name"]: m for m in classes[cls].get("methods", [])}
    m = methods[method]
    got_ret = m.get("return_value", {}).get("type", "")
    got_args = tuple(a["type"] for a in m.get("arguments", []))
    if got_ret != ret or got_args != args:
        raise ValueError(
            f"{cls}.{method}: signature {got_ret} {got_args}, expected {ret} {args}"
        )
    return int(m["hash"])


def builtin_hash(api: dict, typ: str, method: str, ret: str) -> int:
    """Return the hash of a builtin type's method (Array.size, Dictionary.keys, ...).

    Args:
        api: The parsed extension_api.json.
        typ: Builtin type name, such as "Array".
        method: Method name on that type.
        ret: Expected return type.

    Returns:
        The hash to pass to variant_get_ptr_builtin_method.

    Raises:
        KeyError: The type or method is not in the dump.
        ValueError: The return type differs.
    """
    types = {c["name"]: c for c in api["builtin_classes"]}
    methods = {m["name"]: m for m in types[typ].get("methods", [])}
    m = methods[method]
    if m.get("return_type", "") != ret:
        raise ValueError(f"{typ}.{method}: returns {m.get('return_type')}, not {ret}")
    return int(m["hash"])


def constant_value(api: dict, cls: str, name: str, kind: str) -> int:
    """Return an engine constant or enum value.

    Args:
        api: The parsed extension_api.json.
        cls: Class that declares the constant or enum.
        name: Constant or enum value name.
        kind: "constant" for a class constant, else the enum's name.

    Returns:
        The integer value.

    Raises:
        KeyError: The constant is not declared where expected.
    """
    c = {c["name"]: c for c in api["classes"]}[cls]
    if kind == "constant":
        return {k["name"]: int(k["value"]) for k in c.get("constants", [])}[name]
    enum = {e["name"]: e for e in c.get("enums", [])}[kind]
    return {v["name"]: int(v["value"]) for v in enum["values"]}[name]


def render_header(api: dict, api_sha256: str) -> str:
    """Render the full text of binds.h from the dump.

    Args:
        api: The parsed extension_api.json.
        api_sha256: Hex SHA-256 of the dump file, recorded in the header comment so a
            reader can tell which dump produced it.

    Returns:
        The header text, ending in a newline.

    Raises:
        KeyError, ValueError: As raised by method_hash, builtin_hash, constant_value.
    """
    head = api["header"]
    lines = [
        "// Generated by scripts/gen_telemetry_binds.py from the engine's API dump.",
        f"// Engine: {head['version_full_name']} ({head['precision']} precision)",
        f"// Dump SHA-256: {api_sha256}",
        "// Do not edit by hand; regenerate after an engine upgrade.",
        "#pragma once",
        "",
    ]
    for cls, method, ret, args in CLASS_METHODS:
        h = method_hash(api, cls, method, ret, args)
        lines.append(f"#define H_{cls}_{method} {h}LL")
    for typ, method, ret in BUILTIN_METHODS:
        h = builtin_hash(api, typ, method, ret)
        lines.append(f"#define HB_{typ}_{method} {h}LL")
    for cls, name, kind in CONSTANTS:
        lines.append(f"#define K_{name} {constant_value(api, cls, name, kind)}")
    lines.append(
        f'#define ENGINE_VERSION "{head["version_major"]}.{head["version_minor"]}.'
        f'{head["version_patch"]}"'
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    """Read the dump given on the command line and write the header.

    Returns:
        Process exit code: 0 when the header was written, 1 on a signature problem.
    """
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    raw = a.api.read_bytes()
    try:
        text = render_header(json.loads(raw), hashlib.sha256(raw).hexdigest())
    except (KeyError, ValueError) as exc:
        print(f"binds: {exc}", file=sys.stderr)
        return 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
