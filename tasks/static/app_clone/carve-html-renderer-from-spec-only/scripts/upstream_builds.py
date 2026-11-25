"""Record what of the original upstream publishes ready to run, for the verifier's refusal of fetched builds.

usage: upstream_builds.py [--out PATH]

A process the agent leaves behind gets public internet for a while after its session ends, before
its delivery is collected (harbor-lh ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md); it could drop
a published build of the original, or another engine, into /app/rebuild. This lists, for the
verifier (tests/verifier/upstream_builds.json):

- `sha256`: every asset of every carve-rs GitHub release (the digests GitHub reports), the `carve`
  binary inside each x86-64 Linux archive (downloaded), every x86-64 Linux wheel of `carve-lang` on
  PyPI (carve-py, a PyO3 binding over carve-rs) and each file inside it, every version of the
  carve-go module (a Go wrapper over carve-rs compiled to WebAssembly) with each `.wasm` inside
  it, every committed version of the docs site's WebAssembly build of carve-rs
  (docs/.vitepress/carve-wasm/carve_wasm_bg.wasm), the files of Carve's executable spec model at
  the pinned commit and at every spec tag, every ohm-js 17 tarball on npm and its files, and every
  carve-js (`@markup-carve/carve`) tarball on npm and its files.
- `strings`: text at least STRING_LEN characters long that every carve-rs build (the native binary,
  the Python extension and the WebAssembly module) holds and that an HTML renderer written from
  the specification has no reason to hold: carve-rs's own usage lines and messages of the parts out
  of scope (importers, migration, lint, the other output targets), none of them in the shipped
  specification or documentation, nor in a plain Rust build (the Rust tools here). The verifier
  refuses a delivered file that holds `strings_needed` of them.
- `runtimes`: markers of foreign language runtimes (JavaScript, WebAssembly, PHP, Ruby) that no
  renderer in Python, Go or Rust with their standard libraries holds; a delivered program holding
  two markers of one runtime is refused, since the instruction allows no third-party runtime.

Downloads go to experiment/upstream/ (one directory per source), are checked against the digests
their registries publish where there is one, and are never run.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import carve_text as ct

TASK_ROOT = Path(__file__).resolve().parent.parent
OUT = TASK_ROOT / "tests" / "verifier" / "upstream_builds.json"
CACHE = TASK_ROOT / "experiment" / "upstream"
PYPI = "https://pypi.org/pypi/carve-lang/json"
GOPROXY = "https://proxy.golang.org/github.com/markup-carve/carve-go/@v/"
NPM = "https://registry.npmjs.org/"
LINUX = ("x86_64-unknown-linux-gnu", "x86_64-unknown-linux-musl")
# Source files of carve-rs's parts out of scope: their message text appears in no HTML renderer.
OUT_OF_SCOPE_SOURCES = (
    "src/main.rs",
    "src/lint",
    "src/lint.rs",
    "src/html_import",
    "src/html_import.rs",
    "src/markdown_import",
    "src/markdown_import.rs",
    "src/djot_migrate",
    "src/djot_migrate.rs",
    "src/bbcode_migrate.rs",
    "src/migrate_directory.rs",
    "src/migration.rs",
    "src/render_ansi.rs",
    "src/render_plain.rs",
    "src/render_markdown.rs",
    "src/render_carve",
    "src/render_carve.rs",
    "src/ast_merge.rs",
    "src/stamp.rs",
)
STRING_LEN = 40  # a tripwire string is at least this long (QA 04 F6: short fragments are easy to reproduce)
STRINGS_NEEDED = 3
MIN_MEMBER = 4096  # bytes a file inside an archive must have to be listed
# Phrases a renderer's own warnings, or its patterns, could share: never used.
GENERIC = re.compile(
    r"\\|\(\?|has no matching definition|has an empty destination|matches no link definition|opens at line|"
    r"adds no block"
)
RUNTIMES = {
    "node": [
        "node::Environment",
        "v8::internal::",
        "NODE_OPTIONS",
        "process.binding",
        "napi_create_",
    ],
    "bun": ["JavaScriptCore", "bun-v1.", "BUN_INSTALL", "Bun.serve", "JSC::"],
    "deno": ["deno_core", "DENO_DIR", "op_crate", "deno_runtime", "Deno.core"],
    "quickjs": ["QuickJS", "JS_NewContext", "js_std_", "JS_EvalFunction", "quickjs"],
    "wasm": [
        "wasmtime",
        "wasmer_",
        "wasmi_",
        "wasm3_",
        "wasmedge",
        "wazero",
        "WebAssembly.instantiate",
    ],
    "php": [
        "Zend Engine",
        "zend_execute",
        "PHP_VERSION",
        "php_request_startup",
        "ZEND_",
    ],
    "ruby": [
        "ruby_init",
        "rb_define_method",
        "RUBY_VERSION",
        "ruby_options",
        "rb_raise",
    ],
}


def fetch(url: str, place: Path) -> bytes:
    """`url`'s bytes, cached at `place`."""
    if place.is_file():
        return place.read_bytes()
    data = urllib.request.urlopen(url, timeout=300).read()
    place.parent.mkdir(parents=True, exist_ok=True)
    place.write_bytes(data)
    return data


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strings_of(data: bytes, least: int = STRING_LEN) -> set[str]:
    """The printable ASCII runs of `data` at least `least` long."""
    return {match.decode() for match in re.findall(rb"[\x20-\x7e]{%d,}" % least, data)}


def archive_members(data: bytes, mode: str = "r:gz") -> list[tuple[str, bytes]]:
    """The regular files in a tar archive, by name."""
    found = []
    with tarfile.open(fileobj=io.BytesIO(data), mode=mode) as archive:
        for member in archive.getmembers():
            if member.isfile():
                found.append((member.name, archive.extractfile(member).read()))
    return found


def carve_rs(found: dict[str, str]) -> bytes:
    """Record every release asset's digest and the binary of each x86-64 Linux archive; the
    pinned 0.1.14 musl binary's bytes."""
    releases = json.loads(
        subprocess.run(
            [
                "gh",
                "api",
                "--paginate",
                "repos/markup-carve/carve-rs/releases?per_page=100",
            ],
            check=True,
            capture_output=True,
            timeout=300,
        ).stdout
    )
    pinned = b""
    for release in releases:
        for asset in release["assets"]:
            digest = (asset.get("digest") or "").removeprefix("sha256:")
            if digest:
                found[digest] = (
                    f"carve-rs {release['tag_name']} release asset {asset['name']}"
                )
            if not asset["name"].endswith(".tar.gz") or not any(
                target in asset["name"] for target in LINUX
            ):
                continue
            data = fetch(
                asset["browser_download_url"],
                CACHE / "carve-rs" / release["tag_name"] / asset["name"],
            )
            if digest and sha256(data) != digest:
                raise SystemExit(f"{asset['name']}: not the digest GitHub reports")
            found[sha256(data)] = (
                f"carve-rs {release['tag_name']} release asset {asset['name']}"
            )
            for name, body in archive_members(data):
                if name.rsplit("/", 1)[-1] == "carve":
                    found[sha256(body)] = (
                        f"carve-rs {release['tag_name']} binary from {asset['name']}"
                    )
                    if asset["name"] == ct.LINUX_ARCHIVE:
                        pinned = body
    if sha256(pinned) != ct.LINUX_BINARY_SHA256:
        raise SystemExit("the pinned release binary was not among the assets")
    return pinned


def carve_py(found: dict[str, str]) -> bytes:
    """Record every x86-64 Linux wheel of carve-lang and each file in it; the newest wheel's
    extension module."""
    index = json.loads(fetch(PYPI, CACHE / "carve-py" / "index.json"))
    newest = b""
    for version, files in sorted(index["releases"].items()):
        for item in files:
            name = item["filename"]
            if not (
                name.endswith(".whl")
                and "x86_64" in name
                and ("manylinux" in name or "musllinux" in name)
            ):
                continue
            data = fetch(item["url"], CACHE / "carve-py" / version / name)
            if sha256(data) != item["digests"]["sha256"]:
                raise SystemExit(f"{name}: not the digest PyPI reports")
            found[sha256(data)] = f"carve-lang {version} wheel {name}"
            with zipfile.ZipFile(io.BytesIO(data)) as wheel:
                for member in wheel.infolist():
                    if member.file_size >= MIN_MEMBER:
                        body = wheel.read(member)
                        found[sha256(body)] = (
                            f"carve-lang {version} {member.filename} from {name}"
                        )
                        if (
                            member.filename.endswith(".so")
                            and version == index["info"]["version"]
                        ):
                            newest = body
    return newest


def carve_go(found: dict[str, str]) -> bytes:
    """Record every version of the carve-go module and each .wasm inside it; the newest .wasm."""
    versions = sorted(
        fetch(GOPROXY + "list", CACHE / "carve-go" / "list.txt").decode().split(),
        key=lambda v: [int(part) for part in re.findall(r"\d+", v)],
    )
    newest = b""
    for version in versions:
        data = fetch(GOPROXY + f"{version}.zip", CACHE / "carve-go" / f"{version}.zip")
        found[sha256(data)] = f"carve-go {version} module zip"
        with zipfile.ZipFile(io.BytesIO(data)) as module:
            for member in module.infolist():
                if member.filename.endswith(".wasm"):
                    body = module.read(member)
                    found[sha256(body)] = (
                        f"carve-go {version} {member.filename.rsplit('/', 1)[-1]}"
                    )
                    newest = body
    return newest


def carve_wasm(found: dict[str, str]) -> None:
    """Record every committed version of the docs site's WebAssembly build of carve-rs."""
    path = "docs/.vitepress/carve-wasm/carve_wasm_bg.wasm"
    commits = (
        ct.git(ct.SPEC_CHECKOUT, "log", "--format=%H", "--diff-filter=AM", "--", path)
        .decode()
        .split()
    )
    for commit in commits:
        try:
            body = ct.git_bytes(ct.SPEC_CHECKOUT, path, commit)
        except subprocess.CalledProcessError:
            continue
        found[sha256(body)] = f"carve docs carve_wasm_bg.wasm at {commit[:12]}"


def spec_model(found: dict[str, str]) -> None:
    """Record the files of the executable spec model at the pinned commit and at every spec tag."""
    tags = ct.git(ct.SPEC_CHECKOUT, "tag", "--list").decode().split()
    for commit in [ct.SPEC_COMMIT] + tags:
        for prefix in ("scripts/spec", "scripts/lib", "resources/carve-core.ohm"):
            try:
                paths = ct.git_files(ct.SPEC_CHECKOUT, prefix, commit)
            except subprocess.CalledProcessError:
                continue
            for path in paths:
                body = ct.git_bytes(ct.SPEC_CHECKOUT, path, commit)
                if len(body) >= MIN_MEMBER:
                    found.setdefault(
                        sha256(body), f"carve spec model {path} at {commit[:12]}"
                    )


def npm_package(
    found: dict[str, str], package: str, label: str, keep: callable = lambda v: True
) -> None:
    """Record every tarball of an npm package (checked against the registry's integrity) and the
    files inside each."""
    index = json.loads(
        fetch(
            NPM + package.replace("/", "%2F"),
            CACHE / "npm" / f"{package.replace('/', '__')}.json",
        )
    )
    for version, item in sorted(index["versions"].items()):
        if not keep(version):
            continue
        data = fetch(
            item["dist"]["tarball"],
            CACHE / "npm" / package.replace("/", "__") / f"{version}.tgz",
        )
        integrity = item["dist"].get("integrity", "")
        if (
            integrity.startswith("sha512-")
            and base64.b64encode(hashlib.sha512(data).digest()).decode()
            != integrity[7:]
        ):
            raise SystemExit(f"{package}@{version}: not the integrity npm reports")
        found[sha256(data)] = f"{label} {version} npm tarball"
        for name, body in archive_members(data):
            if len(body) >= MIN_MEMBER:
                found.setdefault(sha256(body), f"{label} {version} {name}")


def sources(prefixes: tuple[str, ...]) -> str:
    """carve-rs's Rust sources under `prefixes` at the pinned commit, joined."""
    return "\n".join(
        ct.git_text(ct.RS_CHECKOUT, path, ct.CARVE_RS_COMMIT)
        for prefix in prefixes
        for path in ct.git_files(ct.RS_CHECKOUT, prefix, ct.CARVE_RS_COMMIT)
        if path.endswith(".rs")
    )


def distinctive(
    builds: list[bytes],
    only_first: bool = False,
    prefixes: tuple[str, ...] = OUT_OF_SCOPE_SOURCES,
    most: int = 40,
) -> list[str]:
    """Strings every build holds (with `only_first`, the first build), at least STRING_LEN long,
    that come from carve-rs's sources under `prefixes` at the pinned commit, and that neither the
    shipped text (even with its whitespace removed) nor a plain Rust build holds, nor GENERIC
    phrases."""
    common = (
        strings_of(builds[0])
        if only_first
        else set.intersection(*(strings_of(build) for build in builds))
    )
    source = sources(prefixes)
    pages = list(ct.specification().values()) + list(ct.documentation().values())
    shipped = "\n".join(pages)
    flat = ct.compact(shipped)
    plain = set()
    for tool in (shutil.which("cargo"), shutil.which("rustc"), shutil.which("rustup")):
        if tool:
            plain |= strings_of(Path(tool).resolve().read_bytes())
    picked = [
        text
        for text in common
        if text in source
        and text.strip() not in shipped
        and ct.compact(text) not in flat
        and text not in plain
        and not re.search(r"[<>]|class=|\{\}", text)
        and not GENERIC.search(text)
    ]
    return sorted(picked, key=lambda text: (-len(text), text))[:most]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    found: dict[str, str] = {}
    native = carve_rs(found)
    extension = carve_py(found)
    wasm = carve_go(found)
    carve_wasm(found)
    spec_model(found)
    npm_package(found, "ohm-js", "ohm-js", keep=lambda v: v.startswith("17."))
    npm_package(found, "@markup-carve/carve", "carve-js")
    strings = distinctive([native, extension, wasm])
    usage = distinctive(
        [native], only_first=True, prefixes=("src/main.rs",), most=12
    )  # the command line's own text
    record = {
        "comment": "sha256 of the builds of the original and of the other engines that upstream publishes, text every carve-rs build "
        "holds, and markers of foreign runtimes.",
        "sha256": dict(sorted(found.items())),
        "strings": sorted(set(strings) | set(usage)),
        "strings_needed": STRINGS_NEEDED,
        "runtimes": RUNTIMES,
        "runtime_markers_needed": 2,
    }
    args.out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    kinds = {}
    for label in found.values():
        kinds[label.split(" ")[0]] = kinds.get(label.split(" ")[0], 0) + 1
    print(
        json.dumps(
            {
                "hashes": len(found),
                "by_source": kinds,
                "strings": len(record["strings"]),
                "shortest": min(map(len, record["strings"])),
                "sample": record["strings"][:6],
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
