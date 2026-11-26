"""Write the starter's vendor .import files with explicit import settings (author tool).

Never packaged. Run it inside scripts/heavy.py: it runs three headless imports, one after
another, each after a fresh check for free memory:

  python scripts/heavy.py -- python scripts/make_vendor_imports.py --work DIR

1. Stage a probe project (the starter plus the art binaries, scripts/stage_project.py)
   without any vendor .import file, and import it with the engine's defaults, so the
   engine writes a complete .import file for every asset.
2. Patch them:
   - textures: VRAM-compressed with mipmaps, "detect 3D" off, the normal-map flag set
     (on for *_Normal*, off otherwise). Headless one-shot imports never run the editor's
     detection, so left implicit the textures import slowly as lossless images, and an
     editor session would later rewrite the files;
   - the bodies, the hair and the animation library: retargeted through
     humanoid_bone_map.tres (panel decision 2026-11-26, option A); the library imported
     as an AnimationLibrary (it holds clips, not a scene).
3. Delete the import cache and import from scratch with the patched files (the engine
   completes and rewrites them), then import once more with the cache in place: no .import
   file may change on that last pass.
4. Copy the .import files into environment/game/assets/vendor/ with the packs' licences.

Results (times, cache size, counts) go to experiment/phase1c/vendor_imports.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))
sys.path.insert(0, str(TASK / "scripts"))

from heavy import wait_for_memory
from qakit.prepare import cache_mb, import_project
from qakit.procs import Limits, which_godot
from stage_project import PACKS, STARTER, VENDOR, licences, stage

GODOT_MAC = (
    Path.home()
    / "Documents/github/Abundant/game-spike/vendor/godot-4.7.2/Godot.app/Contents/MacOS/Godot"
)
BONE_MAP = 'Resource("res://assets/vendor/humanoid_bone_map.tres")'
RETARGET = (
    '_subresources={\n"nodes": {\n"PATH:Armature/Skeleton3D": {\n'
    f'"retarget/bone_map": {BONE_MAP}\n}}\n}}\n}}'
)
OUT = TASK / "experiment" / "phase1c"


def params_block(text: str) -> tuple[int, int]:
    """Start and end offsets of the [params] section's body in an .import file."""
    m = re.search(r"^\[params\]\n", text, re.MULTILINE)
    if not m:
        raise ValueError("no [params] section")
    nxt = re.search(r"^\[", text[m.end() :], re.MULTILINE)
    return m.end(), (m.end() + nxt.start()) if nxt else len(text)


def set_param(text: str, key: str, value: str) -> str:
    """Set one key=value line of the [params] section (added when absent)."""
    a, b = params_block(text)
    body = text[a:b]
    line = f"{key}={value}"
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    body = (
        pat.sub(line, body) if pat.search(body) else body.rstrip("\n") + f"\n{line}\n"
    )
    return text[:a] + body + text[b:]


def drop_param(text: str, key: str) -> str:
    """Remove one key (and a multi-line value that follows it) from [params]."""
    a, b = params_block(text)
    lines = text[a:b].split("\n")
    out, skipping, depth = [], False, 0
    for ln in lines:
        if not skipping and ln.startswith(f"{key}="):
            v = ln[len(key) + 1 :]
            depth = v.count("{") + v.count("[") - v.count("}") - v.count("]")
            skipping = depth > 0
            continue
        if skipping:
            depth += ln.count("{") + ln.count("[") - ln.count("}") - ln.count("]")
            skipping = depth > 0
            continue
        out.append(ln)
    return text[:a] + "\n".join(out) + text[b:]


def patch(rel: str, text: str) -> str:
    """The explicit settings for one vendor .import file (rel: path under assets/vendor)."""
    importer = re.search(r'^importer="([^"]+)"', text, re.MULTILINE)
    kind = importer.group(1) if importer else ""
    pack = rel.split("/", 1)[0]
    if kind == "texture":
        normal = "_normal" in Path(rel).name.lower()
        text = set_param(text, "compress/mode", "2")
        text = set_param(text, "mipmaps/generate", "true")
        text = set_param(text, "detect_3d/compress_to", "0")
        text = set_param(text, "compress/normal_map", "1" if normal else "2")
        return text
    if pack in ("ubc", "ubc_hair") and kind == "scene":
        text = drop_param(text, "_subresources")
        a, _ = params_block(text)
        return text[:a] + RETARGET + "\n" + text[a:]
    if pack == "ual":
        # The clips: an AnimationLibrary retargeted through the bone map. The engine
        # fills in the rest of the importer's settings on the next import.
        src = re.search(r'^source_file="([^"]+)"', text, re.MULTILINE).group(1)
        return (
            '[remap]\n\nimporter="animation_library"\nimporter_version=1\n'
            f'type="AnimationLibrary"\n\n[deps]\n\nsource_file="{src}"\n\n'
            f"[params]\n\n{RETARGET}\n"
        )
    return text


def vendor_imports(project: Path) -> dict[str, str]:
    """{path under assets/vendor: text} of every .import file there."""
    root = project / "assets" / "vendor"
    return {
        f.relative_to(root).as_posix(): f.read_text()
        for f in sorted(root.rglob("*.import"))
    }


def digest(files: dict[str, str]) -> str:
    """One hash over a set of files' names and contents."""
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode() + b"\0" + files[k].encode() + b"\0")
    return h.hexdigest()


def run_import(project: Path, godot: str, work: Path, name: str) -> dict:
    """One headless import of project after a fresh memory check; returns its numbers."""
    pct = wait_for_memory(30, 120.0, lambda m: print(m, flush=True))
    t0 = time.monotonic()
    ex = import_project(
        project,
        godot,
        work / f"{name}-home",
        Limits(wall_s=900, memory_mb=4096, cpu_s=1800),
        work / f"{name}.log",
    )
    return {
        "name": name,
        "free_memory_before_pct": pct,
        "wall_s": round(time.monotonic() - t0, 2),
        "cpu_s": ex.cpu_s,
        "peak_memory_mb": round(ex.peak_memory_mb, 1),
        "exit_code": ex.code,
        "signal": ex.signal,
        "violation": ex.violation,
        "cache_mb": round(cache_mb(project), 2),
    }


def main() -> int:
    """Run the three imports, patch, check and copy the .import files."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--godot", default=None)
    ap.add_argument("--vendor", type=Path, default=VENDOR)
    ap.add_argument("--no-copy", action="store_true", help="leave the starter alone")
    a = ap.parse_args()
    godot = which_godot(a.godot or str(GODOT_MAC))
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    probe = work / "probe"
    n_art = stage(probe, [], a.vendor)
    for f in sorted((probe / "assets" / "vendor").rglob("*.import")):
        f.unlink()  # start from the engine's own defaults
    result: dict = {"art_files": n_art, "imports": []}
    result["imports"].append(run_import(probe, godot, work, "1-defaults"))
    defaults = vendor_imports(probe)
    root = probe / "assets" / "vendor"
    for rel, text in defaults.items():
        (root / rel).write_text(patch(rel, text))
    shutil.rmtree(probe / ".godot")
    result["imports"].append(run_import(probe, godot, work, "2-explicit-fresh"))
    explicit = vendor_imports(probe)
    result["imports"].append(run_import(probe, godot, work, "3-explicit-cached"))
    again = vendor_imports(probe)
    changed = sorted(k for k in explicit if again.get(k) != explicit[k])
    kinds: dict[str, int] = {}
    for text in explicit.values():
        m = re.search(r'^importer="([^"]+)"', text, re.MULTILINE)
        kinds[m.group(1) if m else "?"] = kinds.get(m.group(1) if m else "?", 0) + 1
    result.update(
        import_files=len(explicit),
        importers=kinds,
        changed_on_last_pass=changed,
        digest=digest(explicit),
        retargeted=sorted(k for k, v in explicit.items() if "humanoid_bone_map" in v),
        textures_vram=sorted(
            k
            for k, v in explicit.items()
            if 'importer="texture"' in v and "compress/mode=2" in v
        ),
    )
    if not changed and not a.no_copy:
        dest = STARTER / "assets" / "vendor"
        for rel, text in explicit.items():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_text(text)
        for src, rel in licences(a.vendor):
            shutil.copyfile(src, dest / rel)
        result["copied_to"] = str(dest)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "vendor_imports.json").write_text(json.dumps(result, indent=1))
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("retargeted", "textures_vram")
            },
            indent=1,
        )
    )
    print(f"packs: {', '.join(PACKS)}")
    return 0 if not changed else 1


if __name__ == "__main__":
    sys.exit(main())
