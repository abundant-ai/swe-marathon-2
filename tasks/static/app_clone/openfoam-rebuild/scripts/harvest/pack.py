"""Moves the files of recorded runs into a shared store, one copy per distinct content.
Each record's input/ and output/ folders become input.json and output.json, which map each
file's path to its content hash (empty folders: "path/": null; symbolic links:
"link:<target>"); the content lives in <store>/<hash>.
usage: pack.py <store> <record dirs or tutorial record dirs>..."""

import hashlib
import json
import os
import shutil
import sys


def pack_dir(folder, store):
    index = {}
    for d, dirs, files in os.walk(folder):
        if not dirs and not files and d != folder:
            index[os.path.relpath(d, folder) + "/"] = None  # empty folder
        for f in files:
            path = os.path.join(d, f)
            if os.path.islink(path):
                index[os.path.relpath(path, folder)] = "link:" + os.readlink(path)
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            h = hashlib.sha256(data).hexdigest()
            blob = os.path.join(store, h)
            if not os.path.exists(blob):
                with open(blob + ".tmp", "wb") as out:
                    out.write(data)
                os.replace(blob + ".tmp", blob)
            index[os.path.relpath(path, folder)] = h
    return dict(sorted(index.items()))


def main():
    store, *dirs = sys.argv[1:]
    os.makedirs(store, exist_ok=True)
    recs = []
    for d in dirs:
        if os.path.exists(os.path.join(d, "cmd.json")):
            recs.append(d)
        else:
            recs += [
                os.path.join(d, x)
                for x in sorted(os.listdir(d))
                if os.path.exists(os.path.join(d, x, "cmd.json"))
            ]
    for rec in recs:
        for part in ("input", "output"):
            folder = os.path.join(rec, part)
            if os.path.isdir(folder):
                with open(folder + ".json", "w") as stream:
                    json.dump(pack_dir(folder, store), stream, indent=0)
                shutil.rmtree(folder)


if __name__ == "__main__":
    main()
