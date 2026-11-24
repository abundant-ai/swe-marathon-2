"""Writes the kept records of one harvest run in the dataset layout and uploads them.

  records/<tutorial path>/<NNN-program>.json   one file per recorded run: command, input and
                                               expected output (file lists), printed output, exit code
  files/<h[:2]>/<h>                            file contents, named by their sha256, unchanged

The store is extracted from the archive one part at a time, so a run larger than the free
disk can still be published.

usage: publish.py <repo> <tests.json> <tutorials.txt> <run name> <records archive>...
  HF_TOKEN in the environment; archive parts are given in order
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from huggingface_hub import HfApi

PART = 1.5e9   # bytes of file contents extracted and uploaded at a time


def tutorial_paths(tutorials_txt):
    """Record folder name -> path in the dataset: OpenFOAM's tutorial path, or _generated/..."""
    out = {}
    for line in open(tutorials_txt):
        p = line.strip()
        if p:
            out[p.replace("/", "_")] = "_generated/" + p[len("/cases/"):] if p.startswith("/cases/") else p
    return out


def tar(archives, *args):
    """Runs tar on the concatenated archive parts."""
    cat = subprocess.Popen(["cat", *archives], stdout=subprocess.PIPE)
    subprocess.run(["tar", "xzf", "-", *args], stdin=cat.stdout, check=True)
    cat.wait()


def text(path):
    return open(path, errors="replace").read() if os.path.exists(path) else ""


def record_json(d):
    rd = lambda n: json.load(open(os.path.join(d, n)))
    return {"command": rd("cmd.json"), "input": rd("input.json"), "output": rd("output.json"),
            "removed": [x for x in text(os.path.join(d, "removed")).split("\n") if x],
            "exit": int(text(os.path.join(d, "exit")).strip()),
            "stdout": text(os.path.join(d, "stdout")), "stderr": text(os.path.join(d, "stderr"))}


def blobs(rec):
    return {v for m in (rec["input"], rec["output"]) for v in m.values()
            if isinstance(v, str) and not v.startswith("link:")}


def main():
    repo, tests_json, tutorials_txt, run, archives = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
    api = HfApi(token=os.environ["HF_TOKEN"])
    upload = lambda folder, msg: api.upload_folder(repo_id=repo, repo_type="dataset", folder_path=folder, commit_message=msg)
    names = tutorial_paths(tutorials_txt)
    ids = [t["id"] for t in json.load(open(tests_json)) if t["run"] == run]
    work = tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))
    try:
        # 1. record descriptions
        tar(archives, "-C", work, "--exclude", "records/store/*")
        stage = os.path.join(work, "stage")
        needed = set()
        for i in ids:
            case, rec = i.split("/")
            r = record_json(os.path.join(work, "records", case, rec))
            needed |= blobs(r)
            dest = os.path.join(stage, "records", names[case], rec + ".json")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            json.dump(r, open(dest, "w"), indent=1)
        shutil.rmtree(os.path.join(work, "records"))
        upload(stage, f"{run}: records")
        shutil.rmtree(stage)
        # files already in the dataset (shared with another run, or from an interrupted upload)
        needed -= {p.rsplit("/", 1)[1] for p in api.list_repo_files(repo, repo_type="dataset")
                   if p.startswith("files/")}
        print(f"{run}: {len(ids)} records uploaded; {len(needed)} files to upload", flush=True)

        # 2. file contents, in parts of about PART bytes (grouped by the first hex digits of the name)
        sizes = {}
        listing = subprocess.run(f"cat {' '.join(map(repr, archives))} | tar tzvf -", shell=True,
                                 capture_output=True, text=True, check=True).stdout
        for line in listing.splitlines():
            f = line.split()
            if "/store/" in f[-1] and f[-1].rsplit("/", 1)[-1] in needed:
                sizes[f[-1].rsplit("/", 1)[-1]] = int(f[4])
        total = sum(sizes.values())
        digits = 1 if total > PART else 0
        while digits < 3 and total / 16 ** digits > PART:
            digits += 1
        prefixes = [format(k, f"0{digits}x") for k in range(16 ** digits)] if digits else [""]
        for p in prefixes:
            part = sorted(h for h in sizes if h.startswith(p))
            if not part:
                continue
            members = os.path.join(work, "members")
            open(members, "w").write("".join(f"records/store/{h}\n" for h in part))
            tar(archives, "-C", work, "-T", members)
            stage = os.path.join(work, "stage")
            for h in part:
                dest = os.path.join(stage, "files", h[:2], h)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                os.replace(os.path.join(work, "records", "store", h), dest)
            upload(stage, f"{run}: files {p}*")
            shutil.rmtree(stage)
            shutil.rmtree(os.path.join(work, "records"), ignore_errors=True)
            print(f"{run}: files {p or 'all'}* uploaded ({len(part)})", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
