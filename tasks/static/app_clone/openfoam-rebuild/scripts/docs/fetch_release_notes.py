"""Saves the OpenFOAM v2606 release notes (openfoam.com/news/main-news/openfoam-v2606 and its
sections) as one Markdown file, for /app/docs.

usage: fetch_release_notes.py <out.md>     (needs beautifulsoup4 and markdownify)
"""

import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

BASE = "https://www.openfoam.com/news/main-news/openfoam-v2606"
SECTIONS = [
    "",
    "/pre-processing",
    "/numerics",
    "/solvers-and-physics",
    "/post-processing",
    "/infrastructure",
    "/parallel",
    "/plugins",
    "/community",
]


def main():
    parts = []
    for s in SECTIONS:
        url = BASE + s
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(
            urllib.request.urlopen(req, timeout=60).read(), "html.parser"
        )
        body = soup.select_one("#block-bs4esi-content")
        for junk in body.select("nav, .menu, .block-menu, script, style"):
            junk.decompose()
        text = markdownify(str(body), heading_style="ATX").strip()
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        parts.append(f"<!-- {url} -->\n\n{text}\n")
        print(url, len(text), flush=True)
    Path(sys.argv[1]).write_text("\n\n---\n\n".join(parts))


if __name__ == "__main__":
    main()
