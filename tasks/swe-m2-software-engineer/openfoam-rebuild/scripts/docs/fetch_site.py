"""Saves the OpenFOAM v2606 documentation site (doc.openfoam.com/2606, CC BY-NC-ND 4.0) as one
Markdown file per page, keeping the site's folder structure, for /app/docs.

Each page's article text is kept, without the site's navigation; links between pages become
relative links to the saved files. Images are saved next to the pages.

usage: fetch_site.py <out dir>     (needs beautifulsoup4 and markdownify)
"""
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import deque

from bs4 import BeautifulSoup
from markdownify import markdownify

ROOT = "https://doc.openfoam.com/2606/"
AGENT = "Mozilla/5.0 (offline copy for a benchmark environment)"


def get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(), r.headers.get_content_type()
        except Exception as e:   # transient errors: retry, then report
            if attempt == 3:
                print(f"failed {url}: {e}", flush=True)
                return None, None
            time.sleep(2 ** attempt)


def page_path(url):
    """https://doc.openfoam.com/2606/a/b/ -> a/b/index.md; .../a/b -> a/b.md"""
    rel = urllib.parse.urlparse(url).path[len("/2606/"):]
    return (rel + "index.md") if rel == "" or rel.endswith("/") else rel + ".md"


def inside(url):
    u = urllib.parse.urlparse(url)
    return u.netloc == "doc.openfoam.com" and u.path.startswith("/2606/") and "/assets/" not in u.path


def main():
    out = sys.argv[1]
    seen, queue, images = {ROOT}, deque([ROOT]), set()
    while queue:
        url = queue.popleft()
        body, kind = get(url)
        if body is None or kind != "text/html":
            continue
        soup = BeautifulSoup(body, "html.parser")
        here = page_path(url)
        for a in soup.find_all("a", href=True):
            target = urllib.parse.urljoin(url, a["href"]).split("#")[0]
            if inside(target) and not os.path.splitext(urllib.parse.urlparse(target).path)[1]:
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
                frag = a["href"].split("#")[1] if "#" in a["href"] else ""
                a["href"] = os.path.relpath(page_path(target), os.path.dirname(here) or ".") + (f"#{frag}" if frag else "")
        article = soup.find("article") or soup.find("main")
        if article is None:
            continue
        for img in article.find_all("img", src=True):
            src = urllib.parse.urljoin(url, img["src"])
            if src.startswith(ROOT):
                rel = urllib.parse.urlparse(src).path[len("/2606/"):]
                images.add((src, rel))
                img["src"] = os.path.relpath(rel, os.path.dirname(here) or ".")
        for junk in article.select("nav, .theme-doc-footer, .pagination-nav, button, a.hash-link"):
            junk.decompose()
        text = markdownify(str(article), heading_style="ATX", code_language="")
        text = "\n".join(line.rstrip() for line in text.splitlines())
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        dest = os.path.join(out, here)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as f:
            f.write(f"<!-- {url} -->\n\n{text.strip()}\n")
        print(f"{len(seen) - len(queue)}/{len(seen)} {here}", flush=True)
        time.sleep(0.2)
    for src, rel in sorted(images):
        body, _ = get(src)
        if body:
            dest = os.path.join(out, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "wb").write(body)
    print(f"{len(seen)} pages, {len(images)} images", flush=True)


if __name__ == "__main__":
    main()
