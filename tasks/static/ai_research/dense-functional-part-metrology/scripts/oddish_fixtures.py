"""Read selected members of a pinned Oddish task revision into a scratch directory."""

import json
import os
import shutil
import tarfile
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def download(task: str, version: int, names: list[str], destination: Path) -> None:
    """Fetch requested files through the versioned listing used by the Oddish CLI.

    Args:
        task: Registered Oddish task ID.
        version: Frozen positive version number from the runtime inventory.
        names: Trusted relative paths from that inventory.
        destination: Empty scratch directory, never the final installation.

    A version may be stored as one compressed archive or as individual objects.
    The caller verifies checksums before installing any file. Only the API
    listing receives the account credential. Signed storage requests receive
    none. No archive path other than a requested regular file is written.
    """
    if not names:
        return
    key = os.environ.get("ODDISH_API_KEY")
    if not key:
        raise RuntimeError("Set ODDISH_API_KEY or supply a local --bundle")
    api = os.environ.get("ODDISH_API_URL", "https://api.oddish.app").rstrip("/")
    query = f"version={version}&recursive=true&presign=true&inline=false"
    url = f"{api}/tasks/{quote(task, safe='')}/files?{query}"
    request = Request(url, headers={"Authorization": f"Bearer {key}"})
    with urlopen(request, timeout=90) as response:
        listing = json.load(response)
    entries = {entry["path"]: entry for entry in listing["files"]}
    pending = set(names)
    if pending.difference(entries):
        raise ValueError("The pinned task listing is missing requested files")
    for name in names:
        (destination / name).parent.mkdir(parents=True, exist_ok=True)
    if archive_url := listing.get("archive_url"):
        with (
            urlopen(archive_url, timeout=180) as response,
            tarfile.open(fileobj=response, mode="r|*") as archive,
        ):
            for member in archive:
                name = member.name.removeprefix("./")
                if name in pending:
                    if not member.isfile() or member.size != entries[name]["size"]:
                        raise ValueError(f"Unexpected archived entry for {name}")
                    with (
                        archive.extractfile(member) as source,
                        (destination / name).open("xb") as output,
                    ):
                        shutil.copyfileobj(source, output)
                    pending.remove(name)
        if pending:
            raise ValueError(f"Missing archive members: {sorted(pending)}")
    else:
        for name in names:
            with (
                urlopen(entries[name]["url"], timeout=180) as response,
                (destination / name).open("xb") as output,
            ):
                shutil.copyfileobj(response, output)
