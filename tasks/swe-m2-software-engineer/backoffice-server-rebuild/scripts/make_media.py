"""Make the real-world media the scenarios upload: messy PDFs, large photos, long videos, audio.

usage: make_media.py --out DIR --seed N [--small] [--big]

Two sets are made with different seeds: one is shipped to the candidate as samples, the
other is used only by the private scenarios, so no private upload is a file the candidate has
seen. Names are what phones, scanners and suppliers' systems call their files, drawn from the
seed, so the two sets share none. Needs a Python with Pillow, PyMuPDF (fitz) and numpy, and
ffmpeg on PATH; runs on the author's machine only. Output is deterministic for a given seed on
one machine (ffmpeg with bit-exact flags); `manifest.json` lists every file with its size and
SHA-256. `--big` (the private set) makes the largest files at full size: a phone clip just under
the 64 MiB upload limit, a camera export over five minutes, a scanned bundle of tens of
megabytes, a 20-megapixel photo and a 25-minute voice memo; without it they are smaller
versions of the same kinds. `--small` makes a quick, tiny set for development.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import re
import shutil
import struct
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
SUPPLIERS = ["Harbour Steel Works", "Northwind Kitchens", "Alpenrose Dairy", "Kestrel Packaging", "Meridian Glassware",
             "Okoro Textiles", "Sato Precision", "Bramble & Finch", "Lindqvist Timber", "Copperleaf Coffee"]
ITEMS = ["Stainless steel tray", "Insulated jug 2L", "Oak chopping board", "Glass tumbler 330ml", "Cotton apron",
         "Cold-chain liner", "Corrugated box 40x30", "Espresso cups (6)", "Bread knife", "Ceramic plate 27cm"]
# what wrote the PDF (producer, creator, the version its files declare), as their metadata says
TYPED_PRODUCERS = (("Microsoft® Word for Microsoft 365", "Microsoft® Word for Microsoft 365", "1.7"), ("LibreOffice 7.6", "Writer", "1.6"),
                   ("Crystal Reports", "Sage 50 Accounts", "1.4"), ("QuickBooks PDF Converter", "QuickBooks Desktop", "1.3"),
                   ("Skia/PDF m118", "Chromium", "1.4"), ("wkhtmltopdf 0.12.6", "wkhtmltopdf", "1.4"),
                   ("iText® 7.2.5 ©2000-2023 iText Group NV", "Odoo", "1.7"), ("Adobe PDF Library 17.0", "Adobe InDesign 18.2", "1.6"),
                   ("GPL Ghostscript 9.56.1", "PScript5.dll Version 5.2.2", "1.4"), ("macOS Version 14.4 Quartz PDFContext", "Pages", "1.3"),
                   ("pdfTeX-1.40.25", "LaTeX with hyperref", "1.5"), ("Apache FOP Version 2.9", "Apache FOP", "2.0"))
SCAN_PRODUCERS = (("Canon iR-ADV C5535 PDF", "Canon iR-ADV C5535", "1.4"), ("ScanSnap Manager #iX1600", "ScanSnap Home", "1.6"),
                  ("HP Digital Sending", "HP LaserJet MFP M428", "1.4"), ("Adobe Scan for Android", "Adobe Scan", "1.7"),
                  ("Genius Scan", "Genius Scan for iOS", "1.3"), ("RICOH IM C3000", "RICOH IM C3000", "1.4"))
MINIMUM = {"objstm": "1.5", "rc4": "1.4", "aes": "1.6", "password": "1.6"}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


# ------------------------------------------------------------------ names

class Names:
    """File names as their makers write them, drawn from the set's seed; never the same name twice in a set."""

    def __init__(self, rng: random.Random) -> None:
        self.rng, self.used = rng, set()

    def stamp(self) -> tuple[str, str]:
        rng = self.rng
        return (f"2031{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}", f"{rng.randint(6, 19):02d}{rng.randint(0, 59):02d}{rng.randint(0, 59):02d}")

    def pick(self, folder: str, make) -> str:
        while True:
            name = make(self.rng)
            if (folder, name.lower()) not in self.used:
                self.used.add((folder, name.lower()))
                return f"{folder}/{name}"

    def invoice(self) -> str:
        styles = (lambda r: f"INV-{r.randint(10000, 99999)}.pdf", lambda r: f"Invoice_{r.randint(100000, 999999)}.pdf",
                  lambda r: f"RE{r.randint(2031000, 2031999)}.pdf", lambda r: f"Facture F{r.randint(1000, 9999)}.pdf",
                  lambda r: f"{r.choice(SUPPLIERS).split()[0]} invoice {r.randint(1000, 9999)}.pdf", lambda r: f"SI{r.randint(10000, 99999)}.pdf",
                  lambda r: f"Rechnung {r.randint(20000, 29999)}.pdf")
        return self.pick("pdf", lambda r: r.choice(styles)(r))

    def scan(self) -> str:
        day, time_ = self.stamp()
        return self.pick("pdf", lambda r: r.choice((f"Scan_{day[:4]}-{day[4:6]}-{day[6:]}_{time_[:4]}.pdf", f"scan{r.randint(1, 999):04d}.pdf",
                                                    f"SKM_C30{r.randint(0, 9)}{day[2:]}{time_}.pdf", f"Doc{r.randint(1, 99)}.pdf")))

    def photo(self, extension: str = "jpg") -> str:
        day, time_ = self.stamp()
        upper = extension.upper()
        return self.pick("photo", lambda r: r.choice((f"IMG_{day}_{time_}.{extension}", f"PXL_{day}_{time_}{r.randint(100, 999)}.{extension}",
                                                      f"DSC0{r.randint(1000, 9999)}.{upper}", f"IMG_{r.randint(1000, 9999)}.{upper}",
                                                      f"photo_{day}_{r.randint(1, 40)}.{extension}")))

    def video(self, extension: str) -> str:
        day, time_ = self.stamp()
        return self.pick("video", lambda r: r.choice((f"VID_{day}_{time_}.{extension}", f"PXL_{day}_{time_}{r.randint(100, 999)}.{extension}",
                                                      f"IMG_{r.randint(1000, 9999)}.{extension.upper()}")))

    def camera(self, extension: str) -> str:
        day, time_ = self.stamp()
        return self.pick("video", lambda r: f"{r.choice(('dock', 'yard', 'gate', 'bay'))}-cam-{r.randint(1, 8)}_{day}_{time_}.{extension}")

    def sound(self, extension: str) -> str:
        day, _ = self.stamp()
        return self.pick("audio", lambda r: r.choice((f"Voice Memo {r.randint(1, 120)}.{extension}", f"New Recording {r.randint(1, 80)}.{extension}",
                                                      f"AUD-{day}-WA{r.randint(0, 99):04d}.{extension}", f"call_{day}_{r.randint(100, 999)}.{extension}")))


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
            "date": f"2031-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "currency": rng.choice(["EUR", "USD", "GBP"]),
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

def finish_pdf(doc: fitz.Document, rng: random.Random, options: dict, producers: tuple, kind: str = "plain") -> bytes:
    """The document's bytes with the metadata and the header version its producer writes (at least what `kind` needs)."""
    producer, creator, version = rng.choice(producers)
    version = max(version, MINIMUM.get(kind, "1.0"))
    day = f"2031{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}{rng.randint(6, 19):02d}{rng.randint(0, 59):02d}{rng.randint(0, 59):02d}"
    zone = rng.choice(["+01'00'", "+02'00'", "Z", "-05'00'", "+00'00'"])
    doc.set_metadata({"producer": producer, "creator": creator, "title": rng.choice(["", "", "Invoice", "Scan", "Document1"]),
                      "author": rng.choice(["", "accounts", "Administrator", "scanner"]), "creationDate": f"D:{day}{zone}",
                      "modDate": f"D:{day}{zone}"})
    data = doc.tobytes(**options)
    return re.sub(rb"\A%PDF-\d\.\d", f"%PDF-{version}".encode(), data, count=1)


def scanned_pdf(rng: random.Random, pages: int, dpi: int = 150, colour: bool = False) -> bytes:
    """Image-only pages: rendered text, slight skew, speckle noise, JPEG; at 200 dpi in colour a page is half a megabyte."""
    doc = fitz.open()
    width, height = round(8.27 * dpi), round(11.69 * dpi)
    font = ImageFont.truetype(str(FONT_DIR / "Courier New.ttf"), round(26 * dpi / 150))
    for _ in range(pages):
        image = Image.new("L", (width, height), 245 + rng.randint(-8, 8))
        draw = ImageDraw.Draw(image)
        for row, line in enumerate(invoice_text(invoice_lines(rng), rng)):
            draw.text((round(90 * dpi / 150) + rng.randint(-3, 3), round((120 + row * 38) * dpi / 150)), line, fill=rng.randint(10, 60), font=font)
        image = image.rotate(rng.uniform(-1.6, 1.6), resample=Image.BICUBIC, fillcolor=240)
        noise = np.random.default_rng(rng.randint(0, 2**31)).integers(0, 255, size=(image.height, image.width), dtype=np.uint8)
        pixels = np.array(image, dtype=np.uint8)
        pixels[noise < 3] = 30
        pixels[noise > 252] = 255
        image = Image.fromarray(pixels).filter(ImageFilter.GaussianBlur(0.6))
        if colour:  # the paper's tone and the scanner's colour noise
            image = grain(ImageChops.multiply(image.convert("RGB"), Image.new("RGB", image.size, (250, 246, 236))), rng, 4)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=rng.randint(55, 75))
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buffer.getvalue())
    return finish_pdf(doc, rng, {"garbage": 3, "deflate": True}, SCAN_PRODUCERS)


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
    data_bytes = finish_pdf(doc, rng, options, TYPED_PRODUCERS, kind)
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
        page.insert_text((60, 50), f"Price list 2031 - page {number}", fontname="tiro", fontsize=14)
        for row in range(48):
            sku = f"{rng.choice(['WTR', 'KIT', 'GLS', 'TXT', 'PKG'])}-{rng.randint(100, 999)}-{rng.randint(10, 99)}"
            page.insert_text((60, 80 + row * 15), f"{sku:<16}{rng.choice(ITEMS):<30}{money(rng.randint(100, 90000)):>12}",
                             fontname="cour", fontsize=9)
    return finish_pdf(doc, rng, {"garbage": 3, "deflate": True}, TYPED_PRODUCERS)


def mixed_pdf(rng: random.Random) -> bytes:
    """Typed first pages followed by scanned attachments, as an accounts team receives them."""
    typed = fitz.open(stream=text_pdf(rng, "plain"), filetype="pdf")
    typed.insert_pdf(fitz.open(stream=scanned_pdf(rng, rng.randint(2, 4)), filetype="pdf"))
    return finish_pdf(typed, rng, {"garbage": 3, "deflate": True}, TYPED_PRODUCERS)


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


def grain(image: Image.Image, rng: random.Random, sigma: float) -> Image.Image:
    """A sensor's noise at full resolution, added a strip at a time so a large photo never exists as floats."""
    generator = np.random.default_rng(rng.randint(0, 2**31))
    for top in range(0, image.height, 256):
        box = (0, top, image.width, min(image.height, top + 256))
        strip = np.asarray(image.crop(box), dtype=np.int16)
        strip = strip + generator.normal(0, sigma, strip.shape).astype(np.int16)
        image.paste(Image.fromarray(strip.clip(0, 255).astype(np.uint8)), box[:2])
    return image


def _ifd(entries: list[tuple[int, int, bytes]], start: int, next_ifd: int = 0, order: str = "<") -> bytes:
    """A TIFF IFD in byte order `order` ("<" little-endian, ">" big-endian); values longer than 4 bytes go after it."""
    count = len(entries)
    data_at = start + 2 + count * 12 + 4
    head, tail = struct.pack(order + "H", count), b""
    for tag, kind, value in sorted(entries):
        size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1}[kind]
        units = len(value) // size
        if len(value) <= 4:
            head += struct.pack(order + "HHI", tag, kind, units) + value.ljust(4, b"\0")
        else:
            head += struct.pack(order + "HHII", tag, kind, units, data_at + len(tail))
            tail += value + (b"\0" if len(value) % 2 else b"")
    return head + struct.pack(order + "I", next_ifd) + tail


def exif_block(rng: random.Random, orientation: int, thumbnail: bytes | None, order: str = "<") -> bytes:
    """APP1 Exif payload with IFD0, Exif, GPS and (optionally) IFD1 with a JPEG thumbnail, in either byte order (phones
    from one maker write big-endian, others little-endian)."""
    def text(value: str) -> bytes:
        return value.encode() + b"\0"

    def rational(*pairs: tuple[int, int]) -> bytes:
        return b"".join(struct.pack(order + "II", a, b) for a, b in pairs)

    def short(value: int) -> bytes:
        return struct.pack(order + "H", value)

    def long(value: int) -> bytes:
        return struct.pack(order + "I", value)

    lat, lon = rng.uniform(35, 60), rng.uniform(-10, 25)
    def dms(value: float) -> bytes:
        degrees = int(value); minutes = int((value - degrees) * 60); seconds = round(((value - degrees) * 60 - minutes) * 60 * 100)
        return rational((degrees, 1), (minutes, 1), (seconds, 100))

    taken = f"2031:{rng.randint(1, 12):02d}:{rng.randint(1, 28):02d} {rng.randint(7, 19):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
    exif_entries = [(0x9003, 2, text(taken)), (0x829A, 5, rational((1, rng.choice([60, 120, 250, 500])))),
                    (0x829D, 5, rational((rng.choice([18, 28, 40, 56]), 10))), (0x8827, 3, short(rng.choice([50, 100, 400, 1600]))),
                    (0x920A, 5, rational((rng.choice([26, 52, 77]), 10)))]
    gps_entries = [(0x0001, 2, b"N\0"), (0x0002, 5, dms(lat)), (0x0003, 2, b"E\0" if lon >= 0 else b"W\0"), (0x0004, 5, dms(abs(lon))),
                   (0x0006, 5, rational((rng.randint(0, 900), 1)))]
    make, model = rng.choice([("Pixelcraft", "PC-9 Pro"), ("Lumenor", "L12"), ("Fieldcam", "FC Mini"), ("Orchard", "Phone 15 Pro")])
    # Lay out: header(8) | IFD0 | Exif IFD | GPS IFD | IFD1 | thumbnail
    def build(exif_at: int, gps_at: int, ifd1_at: int, thumb_at: int) -> tuple[bytes, bytes, bytes, bytes]:
        ifd0 = _ifd([(0x010F, 2, text(make)), (0x0110, 2, text(model)), (0x0112, 3, short(orientation)),
                     (0x0131, 2, text(rng_software)), (0x8769, 4, long(exif_at)), (0x8825, 4, long(gps_at))],
                    8, ifd1_at if thumbnail else 0, order)
        exif = _ifd(exif_entries, exif_at, 0, order)
        gps = _ifd(gps_entries, gps_at, 0, order)
        ifd1 = _ifd([(0x0103, 3, short(6)), (0x0201, 4, long(thumb_at)), (0x0202, 4, long(len(thumbnail)))], ifd1_at, 0, order) if thumbnail else b""
        return ifd0, exif, gps, ifd1
    rng_software = rng.choice(["Field app 4.2", "17.4.1", "HDR+ 1.0.6", "Camera 2.3"])
    sizes = [len(part) for part in build(0, 0, 0, 0)]
    exif_at = 8 + sizes[0]; gps_at = exif_at + sizes[1]; ifd1_at = gps_at + sizes[2]; thumb_at = ifd1_at + sizes[3]
    parts = build(exif_at, gps_at, ifd1_at, thumb_at)
    header = b"II*\0" if order == "<" else b"MM\0*"
    return b"Exif\0\0" + header + long(8) + b"".join(parts) + (thumbnail or b"")


def jpeg_with_exif(image: Image.Image, rng: random.Random, orientation: int, progressive: bool, with_thumbnail: bool,
                   quality: int | None = None) -> bytes:
    thumb = None
    if with_thumbnail:
        small = image.copy()
        small.thumbnail((160, 120))
        buffer = io.BytesIO()
        small.save(buffer, "JPEG", quality=70)
        thumb = buffer.getvalue()
    order = rng.choice("<>")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality or rng.choice([82, 88, 92]), progressive=progressive, optimize=progressive,
               subsampling=rng.choice([0, 1, 2]), exif=exif_block(rng, orientation, thumb, order))
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

def ffmpeg(args: list[str], target: Path) -> Path:
    """Run ffmpeg into `target` with metadata stripped and bit-exact muxing."""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, "-threads", "2", "-map_metadata", "-1",
                    "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", str(target)], check=True, timeout=3600)
    return target


def videos(rng: random.Random, names: Names, tmp: Path, small: bool, big: bool) -> Iterator[tuple[str, Path]]:
    seconds = 4 if small else rng.choice([45, 60, 75])
    scene = rng.choice(["testsrc2=size=1280x720:rate=30", "smptehdbars=size=1280x720:rate=30",
                        "life=size=1280x720:rate=25:ratio=0.2:life_color=#2d7d46:death_color=#c83232"])
    tone = f"sine=frequency={rng.randint(220, 880)}:duration={seconds}"
    source = ["-f", "lavfi", "-i", scene, "-f", "lavfi", "-i", tone]
    short, half = str(max(3, seconds // 3)), str(max(3, seconds // 2))
    walk = ffmpeg(source + ["-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast", "-b:v", "400k", "-c:a", "aac", "-b:a", "64k",
                            "-movflags", "+faststart"], tmp / "a.mp4")
    trimmed = ffmpeg(["-ss", "1.3", "-i", str(walk), "-c", "copy"], tmp / "g.mp4")  # cut before the original moves into place
    yield names.video("mp4"), walk
    yield names.video("mp4"), ffmpeg(source + ["-t", str(seconds), "-vf", "scale=854:480", "-c:v", "libx264", "-preset", "veryfast", "-b:v", "250k",
                                               "-c:a", "aac", "-movflags", "+frag_keyframe+empty_moov+default_base_moof"], tmp / "b.mp4")
    ffmpeg(source + ["-t", short, "-c:v", "libx265", "-preset", "ultrafast", "-tag:v", "hvc1", "-b:v", "350k", "-c:a", "aac"], tmp / "c0.mov")
    yield names.video("mov"), ffmpeg(["-display_rotation", "90", "-i", str(tmp / "c0.mov"), "-c", "copy"], tmp / "c.mov")
    yield names.camera("webm"), ffmpeg(source + ["-t", str(seconds), "-vf", "scale=640:360", "-c:v", "libvpx-vp9", "-b:v", "200k",
                                                 "-deadline", "realtime", "-cpu-used", "8", "-c:a", "libopus", "-b:a", "48k"], tmp / "d.webm")
    yield names.video("mkv"), ffmpeg(source + ["-t", half, "-vf", "scale=960:540", "-c:v", "libx264", "-preset", "veryfast", "-b:v", "300k",
                                               "-c:a", "libopus", "-b:a", "48k"], tmp / "e.mkv")
    yield names.camera("avi"), ffmpeg(source + ["-t", str(min(8, seconds)), "-vf", "scale=320:240", "-c:v", "mjpeg", "-q:v", "6",
                                                "-c:a", "pcm_s16le", "-ar", "16000"], tmp / "f.avi")
    yield names.video("mp4"), trimmed
    # a phone's own 1080p recording: a busy, grainy picture, so the encoder spends its whole bitrate. At full size it is
    # just under the 64 MiB upload limit; a shipment takes it (under five minutes)
    clip_seconds, clip_rate = (3, 2000) if small else (47, 9500) if big else (12, 7000)
    yield names.video("mp4"), ffmpeg(["-f", "lavfi", "-i", f"testsrc2=size={'640x360' if small else '1920x1080'}:rate=30",
                                      "-f", "lavfi", "-i", f"anoisesrc=d={clip_seconds}:c=brown:a=0.06", "-t", str(clip_seconds),
                                      "-vf", "noise=alls=22:allf=t+u,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                                      "-b:v", f"{clip_rate}k", "-maxrate", f"{clip_rate}k", "-bufsize", f"{clip_rate * 2}k",
                                      "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"], tmp / "h.mp4")
    # a yard camera's export: hours of footage are cut to a few minutes, over the five a shipment takes
    camera_seconds = 20 if small else 380
    size, rate = ("320x240", 150) if small or not big else ("1280x720", 450)
    yield names.camera("mp4"), ffmpeg(["-f", "lavfi", "-i", f"life=size={size}:rate=12:ratio=0.1:life_color=#9a9a9a:death_color=#202020",
                                       "-t", str(camera_seconds), "-vf", "noise=alls=14:allf=t,format=yuv420p", "-c:v", "libx264",
                                       "-preset", "veryfast", "-b:v", f"{rate}k", "-maxrate", f"{rate}k", "-bufsize", f"{rate * 2}k",
                                       "-movflags", "+faststart"], tmp / "i.mp4")


def sounds(rng: random.Random, names: Names, tmp: Path, small: bool, big: bool) -> Iterator[tuple[str, Path]]:
    seconds = 4 if small else rng.choice([45, 60, 75])
    voice = ["-f", "lavfi", "-i", f"anoisesrc=d={seconds * 2}:c=pink:a=0.05", "-f", "lavfi",
             "-i", f"sine=frequency={rng.randint(150, 300)}:duration={seconds * 2}", "-filter_complex", "amix=inputs=2"]
    yield names.sound("mp3"), ffmpeg(voice + ["-c:a", "libmp3lame", "-q:a", "5"], tmp / "s1.mp3")
    yield names.sound("ogg"), ffmpeg(voice + ["-c:a", "libopus", "-b:a", "24k"], tmp / "s2.ogg")
    yield names.sound("wav"), ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={rng.randint(600, 1200)}:duration=6", "-ac", "2", "-ar", "22050"],
                                     tmp / "s3.wav")
    # a long voice memo recorded on a phone: a meeting, a walk round the warehouse
    memo = 6 if small else 1500 if big else 480
    speech = ["-f", "lavfi", "-i", f"anoisesrc=d={memo}:c=pink:a=0.03", "-f", "lavfi",
              "-i", f"sine=frequency={rng.randint(120, 260)}:duration={memo}", "-filter_complex", "amix=inputs=2,volume=2"]
    yield names.sound("m4a"), ffmpeg(speech + ["-ac", "1", "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart"], tmp / "s4.m4a")


# ------------------------------------------------------------------ main

def build(seed: int, small: bool, big: bool, tmp: Path) -> Iterator[tuple[str, bytes | Path]]:
    """Every file of a set as (manifest key, bytes or a finished file to move into place), one at a time."""
    rng = random.Random(seed)
    names = Names(random.Random(f"names:{seed}"))
    pages = (lambda many: 2 if small else many)
    yield names.scan(), scanned_pdf(rng, pages(rng.randint(6, 10)))
    yield f"pdf/Statement {MONTHS[rng.randrange(12)]} 2031.pdf", scanned_pdf(rng, pages(rng.randint(3, 5)))
    plain = None
    for kind in ("plain", "cid", "rotated", "two_column", "objstm", "rc4", "aes", "incremental", "broken_xref", "password"):
        data = text_pdf(rng, kind)
        name = names.invoice()
        plain = plain or (name, data)
        yield name, data
    yield f"pdf/{rng.choice(SUPPLIERS)} price list 2031.pdf", catalogue_pdf(rng, pages(rng.randint(120, 180)))
    yield f"pdf/Delivery documents {rng.randint(100, 999)}.pdf", mixed_pdf(rng)
    yield plain[0][:-4] + " (1).pdf", plain[1][: len(plain[1]) // 2]  # a download that stopped half way
    # a scanned bundle (a signed contract with its schedules) in colour at 200 dpi: tens of megabytes at full size
    yield names.scan(), scanned_pdf(rng, 2 if small else 64 if big else 10, dpi=200, colour=True)
    size = (lambda w, h: (w // 8, h // 8) if small else (w, h))
    for (w, h), orientation, progressive, thumb in (((4032, 3024), 6, False, True), ((6000, 4000), 1, True, False),
                                                    ((3000, 4000), 8, False, False), ((1600, 1200), 3, True, True)):
        yield names.photo(), jpeg_with_exif(photo(rng, *size(w, h)), rng, orientation, progressive, thumb)
    w, h = (5472, 3648) if big else (4000, 3000)  # a 20-megapixel camera's photo with its sensor's grain, several megabytes
    yield names.photo(), jpeg_with_exif(grain(photo(rng, *size(w, h)), rng, 9), rng, 1, False, False, quality=93)
    cmyk = io.BytesIO()
    photo(rng, *size(2400, 1600)).convert("CMYK").save(cmyk, "JPEG", quality=85)
    yield names.photo(), cmyk.getvalue()
    png = io.BytesIO()
    photo(rng, *size(2000, 1500)).convert("RGBA").save(png, "PNG")
    yield names.pick("photo", lambda r: f"Screenshot 2031-{r.randint(1, 12):02d}-{r.randint(1, 28):02d} at {r.randint(8, 18)}.{r.randint(10, 59)}.png"), \
        png.getvalue()
    yield names.pick("photo", lambda r: f"conveyor-{r.randint(1, 9)}.gif"), animated_gif(rng, 12 if small else rng.randint(80, 140), (320, 240))
    yield from videos(rng, names, tmp, small, big)
    yield from sounds(rng, names, tmp, small, big)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--big", action="store_true", help="the private set: the largest files at full size")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with tempfile.TemporaryDirectory(dir=args.out) as folder:
        for name, data in build(args.seed, args.small, args.big, Path(folder)):
            target = args.out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, Path):
                shutil.move(data, target)
            else:
                target.write_bytes(data)
            manifest[name] = {"bytes": target.stat().st_size, "sha256": sha256(target)}
            print(json.dumps({"made": name, "bytes": manifest[name]["bytes"]}), flush=True)
    (args.out / "manifest.json").write_text(json.dumps({"seed": args.seed, "small": args.small, "big": args.big, "files": manifest}, indent=1,
                                                       sort_keys=True, ensure_ascii=False))
    print(json.dumps({"files": len(manifest), "megabytes": round(sum(f["bytes"] for f in manifest.values()) / 1e6, 1)}))


if __name__ == "__main__":
    main()
