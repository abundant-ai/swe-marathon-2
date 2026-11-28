"""Command line: carve [--safe] [--html] [FILE]"""

import os
import sys

from .source import normalize


def main(argv):
    safe = False
    files = []
    for a in argv:
        if a == "--safe":
            safe = True
        elif a == "--html":
            pass
        elif a == "-":
            files.append(a)
        elif a.startswith("-"):
            return 2
        else:
            files.append(a)
    if len(files) > 1:
        return 2
    try:
        if not files or files[0] == "-":
            data = sys.stdin.buffer.read()
        else:
            path = files[0]
            if os.path.isdir(path):
                return 2
            with open(path, "rb") as fh:
                data = fh.read()
    except (OSError, ValueError):
        return 2
    text = normalize(data)
    from .render import render_html

    html = render_html(text, safe=safe)
    out = (html + "\n").encode("utf-8", errors="surrogatepass")
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    return 0
