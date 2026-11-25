"""Files that arrive during a month of trading: supplier invoices as PDFs, photos, clips, voice notes and CSV imports.

A supplier invoice is made for the purchase order it bills: the supplier's own number, the order's
products with the quantities received and the prices agreed, and a total. The clerk's decisions in a
trading run depend on what the server reads from it, so the PDF is made the way different producers
make them: typed and plain, with object streams, RC4 or AES encryption (an empty password, or the
supplier's portal password), an incremental update, a damaged cross-reference table, over two pages,
or scanned; with the producer, metadata and PDF version of the software that wrote it. Each supplier
prints its own layout: a table the reader follows, one that puts the product code after its
description or a VAT column after the amount (lines it cannot read), one that leads with the
quantity. Some carry a supplier's mistake: an amount that does not add up, a total that differs, a
price that has gone up, more than was received.

Proof-of-delivery photos (JPEG with EXIF in either byte order: GPS, orientation, embedded thumbnails or
none; baseline and progressive), short clips and voice notes come from a pool made once per seed, with
two photos an integration sends as base64, one just under the 3,000,000-byte limit of a file inside
JSON and one over it, and customer lists for the CSV import: two of a few hundred rows (one with
mistakes) and a full export over the import's size limit. Nothing is made twice: a file that already
exists is kept, so a second recording reads the same bytes.

Needs a Python with PyMuPDF, Pillow and numpy, and ffmpeg on PATH (as scripts/make_media.py).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import re
import tempfile
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import numpy as np
from make_media import (
    FONT_DIR,
    SCAN_PRODUCERS,
    TYPED_PRODUCERS,
    ffmpeg,
    finish_pdf,
    grain,
    jpeg_with_exif,
    photo,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CONTAINERS = (
    "plain",
    "plain",
    "plain",
    "objstm",
    "rc4",
    "aes",
    "password",
    "incremental",
    "broken_xref",
    "two_page",
    "scanned",
)
STREETS = (
    "Quay Road",
    "Mill Lane",
    "Station Street",
    "Kanalweg",
    "Via Roma",
    "Harbour Row",
    "Mühlenweg",
    "Rue de la Gare",
)
CONTINENTAL = {
    "SUP-0003": True,
    "SUP-0004": True,
}  # suppliers that write 1.234,56 and "Rechnung"
# each supplier's system prints its own layout (and now and then the plain table, from a second system)
LAYOUTS = {
    "SUP-0001": "table",
    "SUP-0002": "dashed",
    "SUP-0003": "table",
    "SUP-0004": "vat_column",
    "SUP-0005": "code_after",
}
LABELS = ("Invoice No:", "Invoice number", "INVOICE #", "Bill No.", "Tax invoice")
TOTALS = ("Total", "Grand total", "Amount due", "Balance due", "TOTAL")
FILE_NAMES = {
    "SUP-0001": "Invoice_{ref}.pdf",
    "SUP-0002": "{ref}.pdf",
    "SUP-0003": "Rechnung_{ref}.pdf",
    "SUP-0004": "RE {ref}.pdf",
    "SUP-0005": "invoice-{ref}.pdf",
}


def money(cents: int, continental: bool) -> str:
    whole, part = divmod(cents, 100)
    text = f"{whole:,}"
    return (
        f"{text.replace(',', '.')},{part:02d}" if continental else f"{text}.{part:02d}"
    )


def written_date(iso: str, style: int) -> str:
    year, month, day = iso.split("-")
    return (
        iso,
        f"{day}/{month}/{year}",
        f"{day}.{month}.{year}",
        f"{int(day)} {(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])[int(month) - 1]} {year}",
    )[style]


def invoice_text(invoice: dict[str, Any]) -> list[str]:
    """The lines of a supplier invoice, laid out the way the supplier's own system prints them."""
    continental, layout = invoice["continental"], invoice.get("layout", "table")
    head = "Rechnung Nr." if continental else invoice.get("label", "Invoice No:")
    lines = [
        invoice["supplier_name"],
        f"{invoice['street_no']} {invoice['street']}",
        "",
    ]
    if (
        head == "Tax invoice"
    ):  # the number on a line of its own, under a heading the reader does not take for a label
        lines += ["Tax invoice", f"Number: {invoice['reference']}"]
    else:
        lines.append(f"{head} {invoice['reference']}")
    lines += [
        f"Date: {written_date(invoice['date'], invoice.get('date_style', 0))}",
        f"Your order: {invoice['purchase_order']}",
        "",
    ]
    for line in invoice["lines"]:
        unit, amount = (
            money(line["unit_cost"], continental),
            money(line["printed_amount"], continental),
        )
        if layout == "dashed":
            lines.append(
                f"{line['sku']} - {line['name'][:27]} - Qty {line['qty']} - Price {unit} - {amount}"
            )
        elif layout == "vat_column":
            lines.append(
                f"{line['sku']:<12}{line['name'][:24]:<25}{line['qty']:>5}{unit:>12}{amount:>14}{invoice['vat']:>5}%"
            )
        elif layout == "code_after":
            lines.append(
                f"{line['name'][:27]} ({line['sku']}){line['qty']:>6}{unit:>12}{amount:>14}"
            )
        elif layout == "qty_first":
            lines.append(
                f"{line['qty']:>4} x {line['sku']} {line['name'][:27]} @ {unit} = {amount}"
            )
        else:
            lines.append(
                f"{line['sku']:<12}{line['name'][:27]:<28}{line['qty']:>5}{unit:>12}{amount:>14}"
            )
    lines += [
        "",
        f"{invoice.get('total_label', 'Total'):<45}{money(invoice['printed_total'], continental):>26}",
        "",
        invoice["terms"],
    ]
    return lines


def _typed(invoice: dict[str, Any], pages: int, rng: random.Random) -> fitz.Document:
    doc = fitz.open()
    text = invoice_text(invoice)
    split = len(text) if pages == 1 else 8 + len(invoice["lines"]) // 2
    fontname = rng.choice(["helv", "cour", "tiro"])
    for chunk in (text[:split], text[split:]) if pages == 2 else (text,):
        page = doc.new_page(width=595, height=842)
        y = 72
        for line in chunk:
            page.insert_text(
                (50, y), line, fontname=fontname, fontsize=rng.choice([8, 9])
            )
            y += 14
    return doc


def _scanned(invoice: dict[str, Any], rng: random.Random) -> bytes:
    """One image-only page: the typed invoice photographed by a scanner, slightly skewed, with speckle."""
    font = ImageFont.truetype(str(FONT_DIR / "Courier New.ttf"), 20)
    image = Image.new("L", (1240, 1754), 242 + rng.randint(-6, 6))
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(invoice_text(invoice)):
        draw.text(
            (80 + rng.randint(-2, 2), 110 + row * 30),
            line,
            fill=rng.randint(15, 60),
            font=font,
        )
    image = image.rotate(rng.uniform(-1.2, 1.2), resample=Image.BICUBIC, fillcolor=238)
    noise = np.random.default_rng(rng.randint(0, 2**31)).integers(
        0, 255, size=(image.height, image.width), dtype=np.uint8
    )
    pixels = np.array(image, dtype=np.uint8)
    pixels[noise < 2] = 40
    image = Image.fromarray(pixels).filter(ImageFilter.GaussianBlur(0.5))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=rng.randint(45, 65))
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buffer.getvalue())
    return finish_pdf(doc, rng, {"garbage": 3, "deflate": True}, SCAN_PRODUCERS)


def invoice_pdf(invoice: dict[str, Any], container: str, rng: random.Random) -> bytes:
    """The PDF a supplier sends for `invoice`, made the way `container` names (see CONTAINERS)."""
    if container == "scanned":
        return _scanned(invoice, rng)
    doc = _typed(invoice, 2 if container == "two_page" else 1, rng)
    options: dict[str, Any] = {"garbage": 3, "deflate": True}
    if container == "objstm":
        options["use_objstms"] = 1
    if container in ("rc4", "aes", "password"):
        options["encryption"] = (
            fitz.PDF_ENCRYPT_RC4_128 if container == "rc4" else fitz.PDF_ENCRYPT_AES_128
        )
        options["owner_pw"] = f"owner-{rng.randint(1000, 9999)}"
        options["user_pw"] = invoice["password"] if container == "password" else ""
        options["permissions"] = fitz.PDF_PERM_PRINT
    data = finish_pdf(doc, rng, options, TYPED_PRODUCERS, container)
    if container == "incremental":
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invoice.pdf"
            path.write_bytes(data)
            again = fitz.open(path)
            again[0].insert_text(
                (50, 800),
                f"Received {invoice['date']} - goods checked",
                fontname="helv",
                fontsize=8,
            )
            again.saveIncr()
            again.close()
            data = path.read_bytes()
    if container == "broken_xref":
        start = data.rfind(b"\nxref")
        table, rest = data[start:].split(b"trailer", 1)
        moved = re.sub(
            rb"(\d{10}) (\d{5}) n",
            lambda m: b"%010d %s n" % (int(m.group(1)) + 9, m.group(2)),
            table,
        )
        data = data[:start] + moved + b"trailer" + rest
    return data


def file_name(invoice: dict[str, Any], container: str) -> str:
    """What the supplier's system, or the clerk's scanner, names the file."""
    if container == "scanned":
        return (
            f"scan_{invoice['date'].replace('-', '')}_{invoice['reference'][-4:]}.pdf"
        )
    return FILE_NAMES.get(invoice["supplier"], "{ref}.pdf").format(
        ref=invoice["reference"]
    )


def make_invoice(
    rng: random.Random,
    purchase_order: dict[str, Any],
    supplier: dict[str, Any],
    names: dict[str, str],
    date: str,
    mistake: str,
) -> dict[str, Any]:
    """What the supplier bills for a received purchase order; `mistake` is "none", "arithmetic", "total", "price" or "more"."""
    continental = CONTINENTAL.get(supplier["id"], False)
    prefix = {
        "SUP-0001": "OC",
        "SUP-0002": "DU",
        "SUP-0003": "MDG",
        "SUP-0004": "PL",
        "SUP-0005": "AB",
    }.get(supplier["id"], "INV")
    lines = []
    for line in purchase_order["lines"]:
        qty = line["received"] - line.get("billed", 0)
        if qty <= 0:
            continue
        unit = line["unit_cost"]
        lines.append(
            {
                "n": line["n"],
                "sku": line["sku"],
                "name": names.get(line["sku"], line["sku"]),
                "qty": qty,
                "unit_cost": unit,
                "printed_amount": qty * unit,
            }
        )
    if lines and mistake == "price":
        line = rng.choice(lines)
        line["unit_cost"] += rng.choice([5, 10, 25, 40])
        line["printed_amount"] = line["qty"] * line["unit_cost"]
    if lines and mistake == "more":
        line = rng.choice(lines)
        line["qty"] += rng.randint(1, 3)
        line["printed_amount"] = line["qty"] * line["unit_cost"]
    if lines and mistake == "arithmetic":
        rng.choice(lines)["printed_amount"] += rng.choice([-100, 1, 9, 90, 1000])
    goods = sum(line["printed_amount"] for line in lines)
    total = goods + (rng.choice([350, 1200, 2500]) if mistake == "total" else 0)
    layout = (
        LAYOUTS.get(supplier["id"], "table")
        if rng.random() < 0.8
        else rng.choice(("table", "table", "qty_first"))
    )
    return {
        "supplier": supplier["id"],
        "supplier_name": supplier["name"],
        "continental": continental,
        "reference": f"{prefix}-{date[2:4]}{rng.randint(10000, 99999)}",
        "date": date,
        "purchase_order": purchase_order["id"],
        "street": rng.choice(STREETS),
        "street_no": rng.randint(2, 240),
        "lines": lines,
        "printed_total": total,
        "terms": rng.choice(
            [
                "Payment within 30 days.",
                "Zahlbar innerhalb 14 Tagen.",
                "Net 45 days from invoice date.",
                "Paiement à 30 jours fin de mois.",
            ]
        ),
        "password": f"{prefix.lower()}-portal-{rng.randint(100, 999)}",
        "layout": layout,
        "label": rng.choice(LABELS) if rng.random() < 0.3 else "Invoice No:",
        "total_label": rng.choice(TOTALS),
        "date_style": rng.randrange(4),
        "vat": rng.choice([7, 19, 20]),
    }


# ------------------------------------------------------------------ photos, clips, voice notes, imports

POOL_PHOTOS = (  # size, EXIF orientation, progressive, embedded thumbnail
    ((1600, 1200), 1, False, True),
    ((1200, 1600), 6, False, True),
    ((2048, 1536), 1, False, False),
    ((1536, 2048), 8, True, False),
    ((2016, 1512), 3, False, True),
    ((1280, 960), 1, True, True),
    ((1920, 1080), 1, False, True),
    ((1080, 1920), 6, False, False),
)
# photos an integration sends inside JSON as base64: (bytes at least, at most): one under the 3,000,000-byte limit, one over
SIZED = ((2_700_000, 2_950_000), (4_150_000, 4_400_000))
REGION_NAMES = ("NORD", "SUD", "ISLE", "EXPORT")
CUSTOMER_WORDS = (
    "Café Lumière",
    "Ölmühle Brandt",
    "Łódzka Piekarnia",
    "Café São Jorge",
    "Société des Eaux",
    "Bäckerei Grün",
    "Ristorante Mamma Rosa",
    "Hôtel du Lac",
    "Smørrebrød Hus",
    "Taverna Ελιά",
    "Tokyo Deli 東京",
    "Kebab Paşa",
    "Dulcería Peña",
    "Žabka Market",
    "Øresund Fisk",
    "Fromagerie Château",
    "Konditorei Süß",
    "Pierogarnia Śląska",
    "Bistro Noël",
    "Corner Shop",
)


def sized_photo(rng: random.Random, low: int, high: int) -> bytes:
    """A camera photo whose JPEG falls between `low` and `high` bytes: one scene, its grain searched for (by halves) until
    the file is that large."""
    scene, options = photo(rng, 4032, 3024), rng.random()
    weakest, strongest = 0.25, 64.0
    for _ in range(24):
        sigma = (weakest * strongest) ** 0.5
        data = jpeg_with_exif(
            grain(scene.copy(), random.Random(options), sigma),
            random.Random(options),
            1,
            False,
            True,
            quality=90,
        )
        if low <= len(data) <= high:
            return data
        weakest, strongest = (sigma, strongest) if len(data) < low else (weakest, sigma)
    raise RuntimeError(f"no photo between {low} and {high} bytes")


def customers_csv(
    rng: random.Random,
    rows: int,
    mistakes: int = 0,
    fixer: random.Random | None = None,
    at_least: int = 0,
) -> str:
    """A CRM's export of customers, names in many scripts: `rows` rows, or as many as reach `at_least` bytes; `mistakes` of
    them (chosen by `fixer`, so the same rows can be written again without them) break the import's rules."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        [
            "name",
            "tier",
            "region",
            "terms",
            "credit_limit",
            "price_list",
            "preferred_warehouse",
            "min_shelf_days",
        ]
    )
    broken = (
        set((fixer or random.Random(0)).sample(range(rows), mistakes))
        if mistakes
        else set()
    )
    number = 0
    while number < rows or out.tell() < at_least:
        tier = rng.choice(["retail", "retail", "trade", "key"])
        row = [
            f"{rng.choice(CUSTOMER_WORDS)} {rng.randint(1, 999)}",
            tier,
            rng.choice(REGION_NAMES),
            rng.choice(["COD", "NET15", "NET30", "NET45", "EOM10"]),
            str(rng.choice([0, 50_000, 250_000, 1_000_000])),
            {"retail": "", "trade": "PL-TRADE", "key": "PL-KEY"}[tier],
            rng.choice(["", "", "MAIN", "COLD", "EAST"]),
            str(rng.choice([0, 0, 3, 7])),
        ]
        if number in broken:
            column = (fixer or rng).choice([1, 2, 3, 4])
            row[column] = {1: "wholesale", 2: "MOON", 3: "NET90", 4: "lots"}[column]
        writer.writerow(row)
        number += 1
    return out.getvalue()


def pool(
    seed: int,
    folder: Path,
    photos: int = 16,
    clips: int = 3,
    notes: int = 3,
    extras: bool = True,
) -> dict[str, list[str]]:
    """Make (once) the photos, clips, voice notes, base64 photos and imports of a trading pool under `folder`; their keys,
    relative to folder's parent.

    Each file has its own random stream, so a file made earlier and kept changes nothing else.
    """
    made: dict[str, list[str]] = {
        "photo": [],
        "clip": [],
        "note": [],
        "sized": [],
        "import": [],
    }
    for number in range(1, photos + 1):
        rng = random.Random(f"pool:{seed}:photo:{number}")
        size, orientation, progressive, thumb = POOL_PHOTOS[
            (number - 1) % len(POOL_PHOTOS)
        ]
        name = f"IMG_{rng.randint(1000, 9999)}{number:02d}.jpg"
        path = folder / "photo" / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                jpeg_with_exif(photo(rng, *size), rng, orientation, progressive, thumb)
            )
        made["photo"].append(f"{folder.name}/photo/{name}")
    for number in range(1, clips + 1):
        rng = random.Random(f"pool:{seed}:clip:{number}")
        name = f"VID_2031{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}_{rng.randint(80000, 175959)}.{('mp4', 'mov', 'mp4')[(number - 1) % 3]}"
        path = folder / "clip" / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            seconds = rng.randint(4, 7)
            source = [
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=640x360:rate=25",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={rng.randint(200, 900)}:duration={seconds}",
            ]
            extra = [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-b:v",
                "300k",
                "-c:a",
                "aac",
                "-b:a",
                "48k",
            ]
            ffmpeg(
                source
                + ["-t", str(seconds), *extra]
                + (["-movflags", "+faststart"] if name.endswith(".mp4") else []),
                path,
            )
        made["clip"].append(f"{folder.name}/clip/{name}")
    for number in range(1, notes + 1):
        rng = random.Random(f"pool:{seed}:note:{number}")
        extension = ("m4a", "mp3", "ogg")[(number - 1) % 3]
        name = {
            "m4a": f"Voice Memo {rng.randint(1, 99)}.m4a",
            "mp3": f"AUD-2031{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}-WA{number:04d}.mp3",
            "ogg": f"PTT-2031{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}-WA{number:04d}.ogg",
        }[extension]
        path = folder / "note" / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            seconds = rng.randint(5, 12)
            source = [
                "-f",
                "lavfi",
                "-i",
                f"anoisesrc=d={seconds}:c=pink:a=0.04",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={rng.randint(140, 320)}:duration={seconds}",
                "-filter_complex",
                "amix=inputs=2",
            ]
            codec = {
                "m4a": ["-c:a", "aac", "-b:a", "48k"],
                "mp3": ["-c:a", "libmp3lame", "-q:a", "6"],
                "ogg": ["-c:a", "libopus", "-b:a", "24k"],
            }
            ffmpeg(source + codec[extension], path)
        made["note"].append(f"{folder.name}/note/{name}")
    if not extras:
        return made
    for number, (low, high) in enumerate(SIZED, start=1):
        rng = random.Random(f"pool:{seed}:sized:{number}")
        name = f"PXL_2031{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}_{rng.randint(80000000, 175959999)}.jpg"
        path = folder / "sized" / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(sized_photo(rng, low, high))
        made["sized"].append(f"{folder.name}/sized/{name}")
    # a CRM export near the 500-row limit with three mistakes, the same rows put right, the whole list (over the row limit)
    # and a full export with history (over the 400,000-byte limit, still under the 6 MB a JSON body may have)
    for name, rows, mistakes, at_least in (
        ("customers-crm-export.csv", 480, 3, 0),
        ("customers-crm-export-fixed.csv", 480, 0, 0),
        ("customers-all.csv", 620, 0, 0),
        ("customers-full-export.csv", 0, 0, 5_400_000),
    ):
        path = folder / "import" / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            rows_rng = random.Random(
                f"pool:{seed}:import:{'crm' if 'crm' in name else name}"
            )
            path.write_text(
                customers_csv(
                    rows_rng,
                    rows,
                    mistakes,
                    random.Random(f"pool:{seed}:mistakes"),
                    at_least,
                ),
                encoding="utf-8",
            )
        made["import"].append(f"{folder.name}/import/{name}")
    return made


def examples(seed: int, out: Path) -> list[str]:
    """A few files of each kind for the samples the candidate gets: invoices for made-up orders, and a small pool."""
    names = {
        "FLR-WHT-25": "Wheat flour 25 kg",
        "OIL-OLV-05": "Olive oil 5 l",
        "MLK-WHL-12": "Whole milk 12 x 1 l",
        "BOX-CRD-50": "Cardboard boxes, 50 pack",
        "WTR-STL-24": "Still water 24 x 0.5 l",
        "APL-GRN-10": "Green apples 10 kg",
    }
    suppliers = [
        {"id": "SUP-0003", "name": "Meridian Dry Goods"},
        {"id": "SUP-0002", "name": "Dairy Union"},
        {"id": "SUP-0004", "name": "Packline"},
        {"id": "SUP-0005", "name": "Aqua Bottlers"},
        {"id": "SUP-0001", "name": "Orchard Cooperative"},
    ]
    made = []
    for number, (container, mistake) in enumerate(
        (
            ("plain", "none"),
            ("objstm", "arithmetic"),
            ("scanned", "none"),
            ("password", "none"),
            ("two_page", "total"),
            ("incremental", "price"),
            ("plain", "none"),
            ("aes", "none"),
        ),
        start=1,
    ):
        rng = random.Random(f"examples:{seed}:{number}")
        supplier = suppliers[number % len(suppliers)]
        skus = rng.sample(sorted(names), rng.randint(2, 4))
        order = {
            "id": f"PO-{rng.randint(100, 999):06d}",
            "lines": [
                {
                    "n": n,
                    "sku": sku,
                    "received": rng.randint(4, 60),
                    "billed": 0,
                    "unit_cost": rng.randint(300, 9000),
                }
                for n, sku in enumerate(skus, start=1)
            ],
        }
        invoice = make_invoice(
            rng,
            order,
            supplier,
            names,
            f"2030-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            mistake,
        )
        path = out / "supplier-invoices" / file_name(invoice, container)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(invoice_pdf(invoice, container, rng))
        made.append(str(path.relative_to(out)))
    for keys in pool(
        seed, out / "deliveries", photos=8, clips=1, notes=1, extras=False
    ).values():
        made += keys
    return made


def manifest(folder: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(folder).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--examples",
        type=Path,
        required=True,
        help="the visible media folder: adds a few files of each kind",
    )
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps({"made": examples(args.seed, args.examples)}, indent=1))


if __name__ == "__main__":
    main()
