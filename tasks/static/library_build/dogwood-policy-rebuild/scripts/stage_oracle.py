"""Stage the oracle's source: Dogwood 1.2.0 as one offline-buildable Cargo project.

Runs inside the toolchain container (python3 -I), never on the host. Inputs are the published
`dogwood-cli-1.2.0.crate` and the vendored crates; the other four `dogwood-*` crates come from the
vendor directory, which holds exactly what the published lock names. Layout: the project root is
`dogwood-cli` itself, and the four library crates sit under `crates/`, outside the workspace, so
the lock resolves the same packages as the published one. The edits are the minimum an offline
project needs:
- each `dogwood-*` dependency gets a `path` next to its version;
- `dogwood-cli` turns `experimental-arithmetic` on by default, as the installed build has it;
- the lock is generated offline from the registry the agent has (no `dogwood-*` crates) and must
  name the same version of every package as the published lock.

Usage: stage_oracle.py --crate CLI.crate --vendor DIR --registry-config FILE --out DIR
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

CRATES = ("dogwood-language", "dogwood-ops", "dogwood-formatter", "dogwood-syntax")
VERSION = "1.2.0"
DEP_TABLE = re.compile(r"\[(?:dev-|build-)?dependencies\.(dogwood-[a-z]+)\]")


def add_paths(manifest: Path, prefix: str) -> None:
    """Give every `[dependencies.dogwood-*]` table a path to the crate it names."""
    out = []
    for line in manifest.read_text().splitlines():
        out.append(line)
        m = DEP_TABLE.fullmatch(line.strip())
        if m:
            out.append(f'path = "{prefix}{m.group(1)}"')
    manifest.write_text("\n".join(out) + "\n")


def arithmetic_by_default(manifest: Path) -> None:
    text = manifest.read_text()
    features = tomllib.loads(text).get("features", {})
    if "experimental-arithmetic" not in features or "default" in features:
        raise SystemExit("unexpected [features] in dogwood-cli; edit by hand")
    manifest.write_text(
        text.replace(
            "[features]\n", '[features]\ndefault = ["experimental-arithmetic"]\n', 1
        )
    )


def lock_versions(lock: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for pkg in tomllib.loads(lock.read_text()).get("package", []):
        if not pkg["name"].startswith("dogwood-"):
            out.setdefault(pkg["name"], []).append(pkg["version"])
    return {k: sorted(v) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crate", required=True, type=Path)
    ap.add_argument("--vendor", required=True, type=Path)
    ap.add_argument("--registry-config", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    out: Path = a.out
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    tmp = Path("/tmp/stage-cli")
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "-xzf", str(a.crate), "-C", str(tmp), "--no-same-owner"], check=True
    )
    shutil.copytree(tmp / f"dogwood-cli-{VERSION}", out)
    published = lock_versions(out / "Cargo.lock")
    for leftover in ("Cargo.lock", "Cargo.toml.orig", ".cargo_vcs_info.json"):
        (out / leftover).unlink(missing_ok=True)
    for name in CRATES:
        shutil.copytree(a.vendor / f"{name}-{VERSION}", out / "crates" / name)
        (out / "crates" / name / ".cargo-checksum.json").unlink()
        for leftover in ("Cargo.toml.orig", ".cargo_vcs_info.json"):
            (out / "crates" / name / leftover).unlink(missing_ok=True)
        add_paths(out / "crates" / name / "Cargo.toml", "../")
    add_paths(out / "Cargo.toml", "crates/")
    arithmetic_by_default(out / "Cargo.toml")
    with (out / "Cargo.toml").open("a") as f:
        f.write('\n[workspace]\nexclude = ["crates"]\n')

    cargo_home = Path("/tmp/stage-cargo-home")
    cargo_home.mkdir(exist_ok=True)
    shutil.copyfile(a.registry_config, cargo_home / "config.toml")
    env = dict(os.environ, CARGO_HOME=str(cargo_home))
    subprocess.run(
        ["cargo", "generate-lockfile", "--offline"], cwd=out, env=env, check=True
    )
    staged = lock_versions(out / "Cargo.lock")
    if staged != published:
        diff = {
            k: (published.get(k), staged.get(k))
            for k in set(published) | set(staged)
            if published.get(k) != staged.get(k)
        }
        print("staged lock differs from the published one:", diff, file=sys.stderr)
        return 1
    print(f"staged {out}: {len(staged)} third-party packages at the published versions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
