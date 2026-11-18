"""Make the real-world media the scenarios upload: messy PDFs, large photos, long videos, audio.

usage: make_media.py --out DIR --seed N [--small]

Two sets are made with different seeds: one is shipped to the candidate as samples, the
other is used only by the private scenarios, so no private upload is a file the candidate has
seen. Needs a Python with Pillow, PyMuPDF (fitz) and numpy, and ffmpeg on PATH; runs on the
author's machine only. Output is deterministic for a given seed on one machine (ffmpeg is run
single-threaded with bit-exact flags); `manifest.json` lists every file with its size and
SHA-256. `--small` makes a quick, tiny set for development.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import re
import struct
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
SUPPLIERS = ["Harbour Steel Works", "Northwind Kitchens", "Alpenrose Dairy", "Kestrel Packaging", "Meridian Glassware",
             "Okoro Textiles", "Sato Precision", "Bramble & Finch", "Lindqvist Timber", "Copperleaf Coffee"]
ITEMS = ["Stainless steel tray", "Insulated jug 2L", "Oak chopping board", "Glass tumbler 330ml", "Cotton apron",
         "Cold-chain liner", "Corrugated box 40x30", "Espresso cups (6)", "Bread knife", "Ceramic plate 27cm"]


# ------------------------------------------------------------------ invoice content

def invoice_lines(rng: random.Random) -> dict:
    supplier = rng.choice(SUPPLIERS)
    lines = []
    for _ in range(rng.randint(3, 14)):
        qty, price = rng.randint(1, 60), rng.randint(150, 48000)
        lines.append((rng.choice(ITEMS), qty, price, qty * price))
    net = sum(line[3] for line in lines)
    tax = round(net * rng.choice([0.0, 0.07, 0.19, 0.2]))
    return {"supplier": supplier, "number": f"{rng.choice(['INV', 'RE', 'F', 'SI'])}-{rng.randint(1000, 99999)}",
            "date": f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}", "currency": rng.choice(["EUR", "USD", "GBP"]),
            "lines": lines, "net": net, "tax": tax, "total": net + tax}


def money(cents: int) -> str:
    return f"{cents // 100:,}.{cents % 100:02d}"


def invoice_text(data: dict, rng: random.Random) -> list[str]:
    header = [data["supplier"], f"{rng.randint(1, 240)} {rng.choice(['Quay Road', 'Mill Lane', 'Station St', 'Kanalweg'])}",
              "", f"Invoice {data['number']}", f"Date: {data['date']}", f"Currency: {data['currency']}", ""]
    body = [f"{name:<28}{qty:>5} x {money(price):>10} = {money(total):>12}" for name, qty, price, total in data["lines"]]
    return header + ["Item                          Qty     Price          Amount"] + body + [
        "", f"Net {money(data['net']):>40}", f"Tax {money(data['tax']):>40}", f"Total due {money(data['total']):>34}"]


# ------------------------------------------------------------------ PDFs

def scanned_pdf(rng: random.Random, pages: int) -> bytes:
    """Image-only pages: rendered text, slight skew, speckle noise, JPEG at 150 dpi."""
    doc = fitz.open()
    font = ImageFont.truetype(str(FONT_DIR / "Courier New.ttf"), 26)
    for _ in range(pages):
        image = Image.new("L", (1240, 1754), 245 + rng.randint(-8, 8))
        draw = ImageDraw.Draw(image)
        for row, line in enumerate(invoice_text(invoice_lines(rng), rng)):
            draw.text((90 + rng.randint(-3, 3), 120 + row * 38), line, fill=rng.randint(10, 60), font=font)
        image = image.rotate(rng.uniform(-1.6, 1.6), resample=Image.BICUBIC, fillcolor=240)
        noise = np.random.default_rng(rng.randint(0, 2**31)).integers(0, 255, size=(image.height, image.width))
        pixels = np.array(image, dtype=np.int16)
        pixels[noise < 3] = 30
        pixels[noise > 252] = 255
        image = Image.fromarray(pixels.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=rng.randint(55, 75))
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buffer.getvalue())
    return doc.tobytes(garbage=3, deflate=True)


def text_pdf(rng: random.Random, kind: str) -> bytes:
    """A typed invoice made the way different producers make PDFs."""
    doc = fitz.open()
    data = invoice_lines(rng)
    fonts = {"helv": None, "tiro": None, "cour": None}
    fontname = rng.choice(list(fonts))
    page = doc.new_page(width=595, height=842)
    if kind == "cid":
        page.insert_font(fontname="sysfont", fontfile=str(FONT_DIR / rng.choice(["Arial Unicode.ttf", "Verdana.ttf", "Georgia.ttf"])))
        fontname = "sysfont"
    y = 72
    for line in invoice_text(data, rng):
        page.insert_text((60, y), line, fontname=fontname, fontsize=rng.choice([9, 10, 11]))
        y += 15
    if kind == "rotated":
        page.set_rotation(90)
    if kind == "two_column":
        right = doc.new_page(width=842, height=595)
        for column in range(2):
            ty = 60
            for line in invoice_text(invoice_lines(rng), rng):
                right.insert_text((40 + column * 400, ty), line[:52], fontname="helv", fontsize=8)
                ty += 12
    if kind == "cid":
        doc.subset_fonts()  # embed only the glyphs used, as most producers do
    options = {"garbage": 3, "deflate": True}
    if kind == "objstm":
        options["use_objstms"] = 1
    if kind in ("rc4", "aes", "password"):
        options["encryption"] = fitz.PDF_ENCRYPT_RC4_128 if kind == "rc4" else fitz.PDF_ENCRYPT_AES_128
        options["owner_pw"] = "owner-" + str(rng.randint(1000, 9999))
        options["user_pw"] = "letmein" if kind == "password" else ""
        options["permissions"] = fitz.PDF_PERM_PRINT
    data_bytes = doc.tobytes(**options)
    if kind == "incremental":
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invoice.pdf"
            path.write_bytes(data_bytes)
            again = fitz.open(path)
            again[0].insert_text((60, 800), f"Paid {data['date']} ref {rng.randint(100000, 999999)}", fontname="helv", fontsize=9)
            again.saveIncr()
            again.close()
            data_bytes = path.read_bytes()
    if kind == "broken_xref":
        # every in-use offset in the table now points 7 bytes past its object: readers must rebuild it
        start = data_bytes.rfind(b"\nxref")
        table, rest = data_bytes[start:].split(b"trailer", 1)
        moved = re.sub(rb"(\d{10}) (\d{5}) n", lambda m: b"%010d %s n" % (int(m.group(1)) + 7, m.group(2)), table)
        data_bytes = data_bytes[:start] + moved + b"trailer" + rest
    return data_bytes


def catalogue_pdf(rng: random.Random, pages: int) -> bytes:
    doc = fitz.open()
    for number in range(1, pages + 1):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 50), f"Price list 2027 - page {number}", fontname="tiro", fontsize=14)
        for row in range(48):
            sku = f"{rng.choice(['WTR', 'KIT', 'GLS', 'TXT', 'PKG'])}-{rng.randint(100, 999)}-{rng.randint(10, 99)}"
            page.insert_text((60, 80 + row * 15), f"{sku:<16}{rng.choice(ITEMS):<30}{money(rng.randint(100, 90000)):>12}",
                             fontname="cour", fontsize=9)
    return doc.tobytes(garbage=3, deflate=True)


def mixed_pdf(rng: random.Random) -> bytes:
    """Typed first pages followed by scanned attachments, as an accounts team receives them."""
    typed = fitz.open(stream=text_pdf(rng, "plain"), filetype="pdf")
    typed.insert_pdf(fitz.open(stream=scanned_pdf(rng, rng.randint(2, 4)), filetype="pdf"))
    return typed.tobytes(garbage=3, deflate=True)


# ------------------------------------------------------------------ images

def photo(rng: random.Random, full_width: int, full_height: int) -> Image.Image:
    """A smooth, photo-like scene (sky gradient, ground, soft shapes, sensor noise), drawn at a
    quarter of the size and enlarged, so a 24-megapixel photo needs little memory."""
    width, height = max(8, full_width // 4), max(8, full_height // 4)
    generator = np.random.default_rng(rng.randint(0, 2**31))
    y = np.linspace(0, 1, height)[:, None]
    x = np.linspace(0, 1, width)[None, :]
    full = np.ones((height, width))
    sky = np.stack([(120 + 80 * y + 20 * x) * full, (160 + 60 * y) * full, (220 - 40 * y) * full], axis=-1)
    ground = np.stack([(70 + 60 * x) * full, (110 + 30 * y) * full, (50 + 20 * x) * full], axis=-1)
    horizon = 0.45 + 0.08 * np.sin(x * 9 + rng.random() * 6)
    pixels = np.where(((y * full) > (horizon * full))[..., None], ground, sky)
    for _ in range(6):
        cx, cy, r = generator.random() * width, generator.random() * height, (0.05 + 0.15 * generator.random()) * min(width, height)
        mask = ((np.arange(width)[None, :] - cx) ** 2 + (np.arange(height)[:, None] - cy) ** 2) < r * r
        pixels[mask] = pixels[mask] * 0.6 + generator.integers(0, 255, 3) * 0.4
    pixels = pixels + generator.normal(0, 4, pixels.shape)
    small = Image.fromarray(pixels.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    return small.resize((full_width, full_height), Image.BICUBIC)


def _ifd(entries: list[tuple[int, int, bytes]], start: int, next_ifd: int = 0) -> bytes:
    """A little-endian TIFF IFD; values longer than 4 bytes go after it."""
    count = len(entries)
    data_at = start + 2 + count * 12 + 4
    head, tail = struct.pack("<H", count), b""
    for tag, kind, value in sorted(entries):
        size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1}[kind]
        units = len(value) // size
        if len(value) <= 4:
            head += struct.pack("<HHI", tag, kind, units) + value.ljust(4, b"\0")
        else:
            head += struct.pack("<HHII", tag, kind, units, data_at + len(tail))
            tail += value + (b"\0" if len(value) % 2 else b"")
    return head + struct.pack("<I", next_ifd) + tail


def exif_block(rng: random.Random, orientation: int, thumbnail: bytes | None) -> bytes:
    """APP1 Exif payload with IFD0, Exif, GPS and (optionally) IFD1 with a JPEG thumbnail."""
    def text(value: str) -> bytes:
        return value.encode() + b"\0"

    def rational(*pairs: tuple[int, int]) -> bytes:
        return b"".join(struct.pack("<II", a, b) for a, b in pairs)

    lat, lon = rng.uniform(35, 60), rng.uniform(-10, 25)
    def dms(value: float) -> bytes:
        degrees = int(value); minutes = int((value - degrees) * 60); seconds = round(((value - degrees) * 60 - minutes) * 60 * 100)
        return rational((degrees, 1), (minutes, 1), (seconds, 100))

    taken = f"2026:{rng.randint(1, 10):02d}:{rng.randint(1, 28):02d} {rng.randint(7, 19):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
    exif_entries = [(0x9003, 2, text(taken)), (0x829A, 5, rational((1, rng.choice([60, 120, 250, 500])))),
                    (0x829D, 5, rational((rng.choice([18, 28, 40, 56]), 10))), (0x8827, 3, struct.pack("<H", rng.choice([50, 100, 400, 1600]))),
                    (0x920A, 5, rational((rng.choice([26, 52, 77]), 10)))]
    gps_entries = [(0x0001, 2, b"N\0"), (0x0002, 5, dms(lat)), (0x0003, 2, b"E\0"), (0x0004, 5, dms(lon)),
                   (0x0006, 5, rational((rng.randint(0, 900), 1)))]
    make, model = rng.choice([("Pixelcraft", "PC-9 Pro"), ("Lumenor", "L12"), ("Fieldcam", "FC Mini")])
    # Lay out: header(8) | IFD0 | Exif IFD | GPS IFD | IFD1 | thumbnail
    def build(exif_at: int, gps_at: int, ifd1_at: int, thumb_at: int) -> bytes:
        ifd0 = _ifd([(0x010F, 2, text(make)), (0x0110, 2, text(model)), (0x0112, 3, struct.pack("<H", orientation)),
                     (0x0131, 2, text("Field app 4.2")), (0x8769, 4, struct.pack("<I", exif_at)), (0x8825, 4, struct.pack("<I", gps_at))],
                    8, ifd1_at if thumbnail else 0)
        exif = _ifd(exif_entries, exif_at)
        gps = _ifd(gps_entries, gps_at)
        ifd1 = _ifd([(0x0103, 3, struct.pack("<H", 6)), (0x0201, 4, struct.pack("<I", thumb_at)),
                     (0x0202, 4, struct.pack("<I", len(thumbnail)))], ifd1_at) if thumbnail else b""
        return ifd0, exif, gps, ifd1
    sizes = [len(part) for part in build(0, 0, 0, 0)]
    exif_at = 8 + sizes[0]; gps_at = exif_at + sizes[1]; ifd1_at = gps_at + sizes[2]; thumb_at = ifd1_at + sizes[3]
    parts = build(exif_at, gps_at, ifd1_at, thumb_at)
    return b"Exif\0\0" + b"II*\0" + struct.pack("<I", 8) + b"".join(parts) + (thumbnail or b"")


def jpeg_with_exif(image: Image.Image, rng: random.Random, orientation: int, progressive: bool, with_thumbnail: bool) -> bytes:
    thumb = None
    if with_thumbnail:
        small = image.copy()
        small.thumbnail((160, 120))
        buffer = io.BytesIO()
        small.save(buffer, "JPEG", quality=70)
        thumb = buffer.getvalue()
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=rng.choice([82, 88, 92]), progressive=progressive, optimize=progressive,
               subsampling=rng.choice([0, 1, 2]), exif=exif_block(rng, orientation, thumb))
    return buffer.getvalue()


def animated_gif(rng: random.Random, frames: int, size: tuple[int, int]) -> bytes:
    images = []
    for index in range(frames):
        frame = Image.new("RGB", size, (20, 24, 32))
        draw = ImageDraw.Draw(frame)
        x = int((index / frames) * size[0])
        draw.rectangle([x - 30, size[1] // 2 - 30, x + 30, size[1] // 2 + 30], fill=(230, 140 + index % 80, 40))
        draw.text((10, 10), f"pallet {rng.randint(1, 99)} frame {index}", fill=(240, 240, 240))
        images.append(frame.convert("P", palette=Image.ADAPTIVE, colors=rng.choice([16, 64, 128])))
    buffer = io.BytesIO()
    images[0].save(buffer, "GIF", save_all=True, append_images=images[1:], duration=[rng.choice([40, 60, 100]) for _ in images],
                   loop=rng.choice([0, 3]), disposal=2, optimize=False)
    return buffer.getvalue()


# ------------------------------------------------------------------ video and audio

def ffmpeg(args: list[str], target: Path) -> bytes:
    """Run ffmpeg into `target` with metadata stripped and bit-exact muxing, and return the bytes."""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, "-threads", "2", "-map_metadata", "-1",
                    "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", str(target)], check=True, timeout=1800)
    return target.read_bytes()


def videos(rng: random.Random, out: Path, small: bool) -> dict[str, bytes]:
    seconds = 4 if small else rng.choice([45, 60, 75])
    scene = rng.choice(["testsrc2=size=1280x720:rate=30", "smptehdbars=size=1280x720:rate=30",
                        "life=size=1280x720:rate=25:ratio=0.2:life_color=#2d7d46:death_color=#c83232"])
    tone = f"sine=frequency={rng.randint(220, 880)}:duration={seconds}"
    source = ["-f", "lavfi", "-i", scene, "-f", "lavfi", "-i", tone]
    short, half = str(max(3, seconds // 3)), str(max(3, seconds // 2))
    made: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(dir=out) as folder:
        tmp = Path(folder)
        made["video/site-walkthrough.mp4"] = ffmpeg(source + ["-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast", "-b:v", "400k",
                                                              "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart"], tmp / "a.mp4")
        made["video/forklift-stream.mp4"] = ffmpeg(source + ["-t", str(seconds), "-vf", "scale=854:480", "-c:v", "libx264", "-preset", "veryfast",
                                                             "-b:v", "250k", "-c:a", "aac", "-movflags", "+frag_keyframe+empty_moov+default_base_moof"],
                                                   tmp / "b.mp4")
        ffmpeg(source + ["-t", short, "-c:v", "libx265", "-preset", "ultrafast", "-tag:v", "hvc1", "-b:v", "350k", "-c:a", "aac"], tmp / "c0.mov")
        made["video/phone-portrait.mov"] = ffmpeg(["-display_rotation", "90", "-i", str(tmp / "c0.mov"), "-c", "copy"], tmp / "c.mov")
        made["video/dock-camera.webm"] = ffmpeg(source + ["-t", str(seconds), "-vf", "scale=640:360", "-c:v", "libvpx-vp9", "-b:v", "200k",
                                                          "-deadline", "realtime", "-cpu-used", "8", "-c:a", "libopus", "-b:a", "48k"], tmp / "d.webm")
        made["video/inspection.mkv"] = ffmpeg(source + ["-t", half, "-vf", "scale=960:540", "-c:v", "libx264", "-preset", "veryfast", "-b:v", "300k",
                                                        "-c:a", "libopus", "-b:a", "48k"], tmp / "e.mkv")
        made["video/label-printer.avi"] = ffmpeg(source + ["-t", str(min(8, seconds)), "-vf", "scale=320:240", "-c:v", "mjpeg", "-q:v", "6",
                                                           "-c:a", "pcm_s16le", "-ar", "16000"], tmp / "f.avi")
        made["video/trimmed-clip.mp4"] = ffmpeg(["-ss", "1.3", "-i", str(tmp / "a.mp4"), "-c", "copy"], tmp / "g.mp4")
        voice = ["-f", "lavfi", "-i", f"anoisesrc=d={seconds * 2}:c=pink:a=0.05", "-f", "lavfi",
                 "-i", f"sine=frequency={rng.randint(150, 300)}:duration={seconds * 2}", "-filter_complex", "amix=inputs=2"]
        made["audio/voice-note.mp3"] = ffmpeg(voice + ["-c:a", "libmp3lame", "-q:a", "5"], tmp / "h.mp3")
        made["audio/call-recording.ogg"] = ffmpeg(voice + ["-c:a", "libopus", "-b:a", "24k"], tmp / "i.ogg")
        made["audio/alarm.wav"] = ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={rng.randint(600, 1200)}:duration=6", "-ac", "2", "-ar", "22050"],
                                         tmp / "j.wav")
    return made


# ------------------------------------------------------------------ main

def build(seed: int, small: bool, out: Path) -> dict[str, bytes]:
    rng = random.Random(seed)
    files: dict[str, bytes] = {}
    pages = (lambda big: 2 if small else big)
    files["pdf/scanned-invoice.pdf"] = scanned_pdf(rng, pages(rng.randint(6, 10)))
    files["pdf/scanned-statement.pdf"] = scanned_pdf(rng, pages(rng.randint(3, 5)))
    for kind in ("plain", "cid", "rotated", "two_column", "objstm", "rc4", "aes", "incremental", "broken_xref", "password"):
        files[f"pdf/invoice-{kind.replace('_', '-')}.pdf"] = text_pdf(rng, kind)
    files["pdf/price-list.pdf"] = catalogue_pdf(rng, pages(rng.randint(120, 180)))
    files["pdf/mixed-bundle.pdf"] = mixed_pdf(rng)
    files["pdf/truncated.pdf"] = files["pdf/invoice-plain.pdf"][: len(files["pdf/invoice-plain.pdf"]) // 2]
    size = (lambda w, h: (w // 8, h // 8) if small else (w, h))
    for name, (w, h), orientation, progressive, thumb in (
            ("photo/pallet-damage.jpg", (4032, 3024), 6, False, True), ("photo/shelf-wide.jpg", (6000, 4000), 1, True, False),
            ("photo/delivery-proof.jpg", (3000, 4000), 8, False, False), ("photo/label-closeup.jpg", (1600, 1200), 3, True, True)):
        files[name] = jpeg_with_exif(photo(rng, *size(w, h)), rng, orientation, progressive, thumb)
    cmyk = io.BytesIO()
    photo(rng, *size(2400, 1600)).convert("CMYK").save(cmyk, "JPEG", quality=85)
    files["photo/print-proof-cmyk.jpg"] = cmyk.getvalue()
    png = io.BytesIO()
    photo(rng, *size(2000, 1500)).convert("RGBA").save(png, "PNG")
    files["photo/floor-plan.png"] = png.getvalue()
    files["photo/conveyor.gif"] = animated_gif(rng, 12 if small else rng.randint(80, 140), (320, 240))
    files.update(videos(rng, out, small))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--small", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    files = build(args.seed, args.small, args.out)
    manifest = {}
    for name, data in sorted(files.items()):
        target = args.out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (args.out / "manifest.json").write_text(json.dumps({"seed": args.seed, "small": args.small, "files": manifest}, indent=1, sort_keys=True))
    print(json.dumps({"files": len(manifest), "megabytes": round(sum(f["bytes"] for f in manifest.values()) / 1e6, 1)}))


if __name__ == "__main__":
    main()
