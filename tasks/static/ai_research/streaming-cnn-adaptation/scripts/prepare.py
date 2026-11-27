"""Build the pilot's mutually exclusive capture splits from ContinualAI's CORe50 mini archive."""

import argparse
import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ARCHIVE_MD5 = "d89d34cdc0281fa84074430e9a22b728"
NAME = re.compile(r"core50_32x32/s(\d+)/o(\d+)/C_\d+_\d+_(\d{3})\.png")
CLASSES = [
    "plug adapter",
    "mobile phone",
    "scissors",
    "light bulb",
    "can",
    "glass",
    "ball",
    "marker",
    "cup",
    "remote control",
]


def prepare(archive, output):
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "md5").hexdigest() != ARCHIVE_MD5:
            raise ValueError("Unexpected CORe50 mini archive")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with zipfile.ZipFile(archive) as z:
        clips = defaultdict(list)
        for name in z.namelist():
            match = NAME.fullmatch(name)
            if match:
                session, obj, index = map(int, match.groups())
                clips[session, obj].append((index, name))

        def extract(key, sessions, slots, count):
            images, cats, names, ids = [], [], [], []
            for session in sessions:
                for cat in range(10):
                    for slot in slots[session] if isinstance(slots, dict) else slots:
                        obj = 5 * cat + slot
                        paths = sorted(clips[session, obj])
                        if len(paths) < count:
                            raise ValueError((session, obj, len(paths)))
                        for i in (
                            np.linspace(0, len(paths) - 1, count).round().astype(int)
                        ):
                            frame_id, name = paths[i]
                            with Image.open(io.BytesIO(z.read(name))) as im:
                                images.append(np.array(im.convert("RGB")))
                            cats.append(cat)
                            names.append(name)
                            ids.append((session, obj, frame_id))
            manifest[key] = names
            data = {
                "x": np.stack(images),
                "y": np.array(cats, np.int64),
                "ids": np.array(ids, np.int16),
            }
            np.savez_compressed(output / (key + ".npz"), **data)
            return data

        source_sessions = [1, 2, 4, 5, 6, 8]
        reserved = {s: [1 + i % 5] for i, s in enumerate(source_sessions)}
        training = {
            s: [j for j in range(1, 6) if j not in reserved[s]] for s in source_sessions
        }
        extract("source", source_sessions, training, 24)
        extract("source_probe", source_sessions, reserved, 4)
        extract("development", [9, 11], [2, 3, 4, 5], 8)
        for target, session in [("a", 3), ("b", 7)]:
            previews = extract("preview_" + target, [session], [1], 2)
            sheet = Image.new("RGB", (5 * 128, 2 * 128))
            for idx, frame in enumerate(previews["x"][::2]):
                sheet.paste(
                    Image.fromarray(frame).resize((128, 128), Image.Resampling.NEAREST),
                    ((idx % 5) * 128, (idx // 5) * 128),
                )
            sheet.save(output / ("preview_" + target + ".png"))
            extract(target + "_arrival", [session], [2], 8)
            extract(target + "_return", [session], [3], 8)
            extract(target + "_probe", [session], [4, 5], 4)
        extract("middle", [10], [2], 8)
        extract("middle_probe", [10], [4, 5], 4)
    assigned = {}
    for split, names in manifest.items():
        for clip in {str(Path(name).parent) for name in names}:
            if clip in assigned:
                raise ValueError((clip, split, assigned[clip]))
            assigned[clip] = split
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    (output / "public-splits.json").write_text(
        json.dumps(
            {
                "categories": CLASSES,
                "source_sessions": [1, 2, 4, 5, 6, 8],
                "development_sessions": [9, 11],
                "source_captures": sorted(
                    k for k, v in assigned.items() if v == "source"
                ),
                "development_captures": sorted(
                    k for k, v in assigned.items() if v == "development"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print({k: len(v) for k, v in manifest.items()}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.archive, args.output)
