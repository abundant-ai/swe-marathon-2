"""Record the scenarios that need the reference running as a server: months of trading, one unit per trading day,
the web client's own screens after each month, and planned restarts in the middle of some months.

usage: record_live.py --runs N --seed S --media DIR --out FILE [--term K] [--kill K] [--screens M] [--days A B]
                      [--counts C] [--kits K] [--routines R]

The reference server (scripts/reference.py) runs as a process, the way the delivered server will: on a data
directory, with proxy sign-in, the settings the solution's `run` uses. Requests go out through the verifier's own
`exchange`, so they are sent byte for byte as they will be replayed. Every answer is recorded with the reference's
workspace id written as {ws}; the verifier puts the candidate's id back in the same places.

- Trading (scripts/trading.py): N runs of a month, each crossing the month's end. The supplier invoices and a pool
  of photos, clips and voice notes are written under DIR/trading (scripts/trading_media.py), made once, and sent as
  raw uploads named by `body_file`.
- Restarts: K runs stop the server with SIGTERM at the end of a day, K more with SIGKILL straight after a write was
  answered; the server starts again on the same data and the run goes on. The step is marked `restart`.
- Screens: after all runs, the web client (the reference's frontend, under vitest and jsdom) opens M of its screens
  in each run's workspace, through a proxy that notes every request it makes. Those requests are then recorded, the
  start-up calls first and the rest in a fixed order, as one unit per screen. A screen that calls the request log or
  the credentials list (answers that need not match) is left out, and so is one that calls nothing beyond start-up.
- Counts and kits: C stock counts and K kits, start to finish, each in a fresh workspace.
- Routines: R scenarios of each office routine (ROUTINES), each in a fresh workspace and one unit, for the documented
  calls the legacy streams never make or only ever see refused: the workspace's own summary and the service's health,
  readiness and API description; a user read, changed and brought back; the permission table; new price lists and
  suppliers; the promotions list; a saved report opened by its number; and a journal entry reversed, a carrier brought
  back, a supplier unblocked and a standing order resumed. Without months (--runs 0) nothing under DIR/trading is made
  or touched.

Needs a Python with PyMuPDF, Pillow and numpy, ffmpeg, and node with the frontend's packages (reference.py
installs them in the checkout).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import http.client
import json
import os
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "steps" / "01-rebuild-server" / "tests"))

import trading  # noqa: E402
import trading_media  # noqa: E402
from reference import checkout  # noqa: E402
from verifier.replay import NOT_JSON, TOO_LARGE, encode_query, exchange, inserted_body  # noqa: E402

ROLES = {"admin": "U-01", "sales": "U-02", "warehouse": "U-03", "finance": "U-04", "viewer": "U-05"}
WORKSPACE = re.compile(r"ws_[0-9a-f]{16}")
CONTAINERS = ("plain",) * 3 + ("objstm", "rc4", "aes", "password", "incremental", "broken_xref", "two_page", "two_page", "scanned")
MISTAKES = ("none",) * 14 + ("arithmetic", "arithmetic", "total", "price", "price", "more")
UNGRADED = ("/admin/requests", "/auth/credentials", "/auth/api-keys", "/metrics")
SCREENS = ("/", "/activity", "/sales/orders", "/sales/orders/{order}", "/sales/quotes", "/sales/quotes/{quote}", "/sales/standing-orders",
           "/sales/standing-orders/{standing}", "/sales/shipments", "/sales/shipments/{shipment}", "/sales/returns", "/customers",
           "/customers/{customer}", "/catalogue/products", "/catalogue/products/{product}", "/catalogue/price-lists",
           "/catalogue/price-lists/{price_list}", "/catalogue/promotions", "/catalogue/price-check", "/inventory/stock", "/inventory/lots/{lot}",
           "/inventory/moves", "/inventory/counts", "/inventory/counts/{count}", "/inventory/kits", "/inventory/warehouses", "/purchasing/orders",
           "/purchasing/orders/{po}", "/purchasing/receipts", "/purchasing/bills", "/purchasing/bills/{bill}", "/purchasing/suppliers",
           "/purchasing/suppliers/{supplier}", "/purchasing/reorder", "/production/work-orders", "/production/work-orders/{work}",
           "/production/recipes", "/production/recipes/{recipe}", "/production/capacity", "/production/recalls", "/production/recalls/{recall}",
           "/production/trace?lot={lot}", "/planning/plan", "/planning/runs", "/planning/policies", "/planning/classification", "/finance/invoices",
           "/finance/invoices/{invoice}", "/finance/payments", "/finance/credit-notes", "/finance/aging", "/finance/dunning", "/finance/commissions",
           "/finance/rebates", "/finance/rebates/{rebate}", "/finance/ledger", "/finance/journal", "/finance/statements", "/finance/budgets",
           "/finance/bank", "/finance/bank/{statement}", "/finance/fx", "/logistics/carriers", "/reports/query", "/reports/sales",
           "/reports/stock-valuation", "/reports/data", "/admin/users", "/admin/users/{user}", "/admin/permissions", "/admin/webhooks", "/admin/files",
           "/admin/files/{pdf}", "/admin/files/{picture}", "/admin/integrity", "/admin/clock")


SETTINGS = HERE.parent / "environment" / "stockwell.env"


def settings(data: Path) -> dict[str, str]:
    """The server's settings from environment/stockwell.env, the one file the sealed server, the recordings and the
    solution share (QA 12 F1: the sealed server once served the client as well, and answered six requests differently)."""
    pairs = (line.split("=", 1) for line in SETTINGS.read_text().splitlines() if line.strip())
    return {key: value.replace("{data}", str(data)) for key, value in pairs}


class Reference:
    """The reference server as a process on one data directory, stopped and started as an operator would."""

    def __init__(self, source: Path, python: str, data: Path) -> None:
        self.source, self.python, self.data = source, python, data
        self.proc: subprocess.Popen[bytes] | None = None
        self.port = 0

    def start(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.data.mkdir(parents=True, exist_ok=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(self.source), "PYTHONDONTWRITEBYTECODE": "1",
               **settings(self.data)}
        self.proc = subprocess.Popen([self.python, "-B", "-m", "stockwell", "serve", "--host", "127.0.0.1", "--port", str(self.port), "--workers", "1"],
                                     env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
                connection.request("GET", "/api/health")
                if connection.getresponse().status == 200:
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("the reference server did not start")

    def stop(self, how: str = "kill") -> None:
        if self.proc is None:
            return
        os.killpg(self.proc.pid, signal.SIGTERM if how == "term" else signal.SIGKILL)
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait()
        self.proc = None


class Run:
    """The steps and units of one recorded scenario, and the calls that record them."""

    def __init__(self, server: Reference, media: Path, scenario_id: str) -> None:
        self.server, self.media, self.id = server, media, scenario_id
        self.steps: list[dict[str, Any]] = []
        self.units: list[dict[str, str]] = []
        self.pending_kill = False
        self.files: dict[str, bytes] = {}
        self.connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=120)
        status, created = exchange(self.connection, "POST", "/api/workspaces", {}, None)
        self.workspace = created.get("id") if isinstance(created, dict) else None
        if status != 201 or not isinstance(self.workspace, str) or not WORKSPACE.fullmatch(self.workspace):
            raise RuntimeError(f"cannot create a workspace: {status} {created}")
        self.created = json.loads(json.dumps(created).replace(self.workspace, "{ws}"))  # kept as `created` when judge_creation is set
        self.judge_creation = False

    def begin(self, label: str, theme: str = "trading") -> None:
        self.units.append({"theme": theme, "label": label})

    def reconnect(self) -> None:
        self.connection.close()
        self.connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=120)

    def read(self, key: str) -> bytes:
        if key not in self.files:
            self.files[key] = (self.media / key).read_bytes()
        return self.files[key]

    def call(self, role: str, method: str, path: str, body: Any = None, query: dict[str, Any] | None = None, file: str | None = None,
             content_type: str | None = None, restart: str | None = None, scoped: bool = True, headers: dict[str, str] | None = None,
             insert: tuple[str, str, str] | None = None, size: int | None = None) -> tuple[int, Any]:
        """Send one request as `role` (or with `headers`), record it with its answer in the current unit, and return the answer.

        The body is JSON (`body`), a media file sent as it is (`file`), JSON with a media file put into one of its fields
        (`insert`: field, file, "base64" or "text"; the step names the file), or `size` zero bytes.
        """
        query = {key: str(value) for key, value in (query or {}).items()}
        sent = dict(headers) if headers is not None else {"x-user": ROLES[role]}
        if content_type:
            sent["content-type"] = content_type
        step: dict[str, Any] = {"method": method, "path": path, "query": query, "headers": sent}
        raw = None
        if file is not None:
            step["body_file"] = file
            raw = self.read(file)
        elif insert is not None:
            field, key, kind = insert
            step["body"], step["body_insert"] = body, {"field": field, "file": key, "as": kind}
            raw = inserted_body(step, self.read(key))
        elif size is not None:
            step["body_size"] = size
            raw = bytes(size)
        else:
            step["body"] = body
        if not scoped:
            step["scoped"] = False
        if "{ws}" in json.dumps(step):
            raise RuntimeError(f"a request names {{ws}}: {step}")
        target = (path if not scoped else f"/api/ws/{self.workspace}{path}") + encode_query(query)
        status, answer = exchange(self.connection, method, target, sent, body if raw is None else None, raw)
        if answer is NOT_JSON or answer is TOO_LARGE or status >= 500:
            raise RuntimeError(f"{self.id}: {method} {path} answered {status} {str(answer)[:200]}")
        step["status"] = status
        text = json.dumps(answer)
        if "{ws}" in text:  # the answer's own text holds {ws} (the API description's paths): kept as it is, compared so
            if self.workspace in text:
                raise RuntimeError(f"{self.id}: {method} {path} answered both the text {{ws}} and the workspace id")
            step["literal"], step["json"] = True, answer
        else:
            step["json"] = json.loads(text.replace(self.workspace, "{ws}"))
        step["unit"] = len(self.units) - 1
        if restart == "kill?":
            self.pending_kill, restart = True, None
        if self.pending_kill and method == "POST" and 200 <= status < 300:
            self.pending_kill, restart = False, "kill"
        self.steps.append(step)
        if restart:
            step["restart"] = restart
            self.connection.close()
            self.server.stop(restart)
            self.server.start()
            self.reconnect()
        return status, answer

    def scenario(self, theme: str = "trading", **extra: Any) -> dict[str, Any]:
        return {"id": self.id, "theme": theme, "units": self.units, "steps": self.steps, **extra}


def invoice_maker(media: Path, seed: int, run_id: str):
    """The supplier-invoice factory for one run: the PDF for a purchase order, made once under DIR/trading/invoices/<run>,
    named as the supplier's system (or the clerk's scanner) names it."""
    claimed: dict[str, str] = {}  # file name: the invoice it holds, so two invoices of a run never share a name

    def make(detail: dict[str, Any], supplier: dict[str, Any], names: dict[str, str], date: str) -> tuple[str, dict[str, Any], str]:
        rng = random.Random(f"invoice:{seed}:{run_id}:{detail['id']}")
        container, mistake = rng.choice(CONTAINERS), rng.choice(MISTAKES)
        invoice = trading_media.make_invoice(rng, detail, supplier, names, date, mistake)
        digest = hashlib.sha256(json.dumps([invoice, container], sort_keys=True).encode()).hexdigest()
        name, copy = trading_media.file_name(invoice, container), 1
        while claimed.get(name, digest) != digest:
            copy += 1
            name = f"{trading_media.file_name(invoice, container)[:-4]} ({copy}).pdf"
        claimed[name] = digest
        key = f"trading/invoices/{run_id}/{name}"
        path = media / key
        if invoice["lines"] and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(trading_media.invoice_pdf(invoice, container, random.Random(f"pdf:{seed}:{run_id}:{detail['id']}")))
        return key, invoice, container
    return make


# ------------------------------------------------------------------ counts and kits, start to finish

KIT_NAMES = ("Breakfast box", "Baker's starter kit", "Picnic hamper", "Office water pack", "Pantry bundle", "Juice and apples gift box",
             "Café counter refill", "Weekend market crate")
WAREHOUSES = ("MAIN", "COLD", "EAST")


def stock_of(run: Run, warehouse: str) -> list[dict[str, Any]]:
    status, stock = run.call("warehouse", "GET", "/stock", None, {"warehouse": warehouse})
    return [row for row in (stock or {}).get("items", []) if row.get("available", 0) > 0] if status == 200 else []


def count_workflow(run: Run, rng: random.Random) -> None:
    """A stock count from opening to posting: the warehouse counts some or all of a store, enters what it found (some
    lots short, now and then one far off, which finance must approve), posts it, and reads stock and its value."""
    if rng.random() < 0.25:  # someone without the right tries first
        run.call(rng.choice(["viewer", "sales"]), "POST", "/stock/counts", {"warehouse": rng.choice(WAREHOUSES)})
    warehouse = rng.choice(WAREHOUSES)
    rows = stock_of(run, warehouse) or stock_of(run, warehouse := "MAIN")
    skus = sorted(rng.sample([row["sku"] for row in rows], min(len(rows), rng.randint(1, 4)))) if rows and rng.random() < 0.6 else None
    status, count = run.call("warehouse", "POST", "/stock/counts", {"warehouse": warehouse, **({"skus": skus} if skus else {})})
    if status != 201:
        return
    if rng.random() < 0.2:
        run.call("warehouse", "POST", "/stock/counts", {"warehouse": warehouse})  # a second count of a store being counted
    lines = []
    for line in count["lines"]:
        found = line["expected"]
        roll = rng.random()
        if roll < 0.25:
            found = max(0, found - rng.randint(1, 3))
        elif roll < 0.3:
            found = found + rng.randint(1, 2)
        elif roll < 0.36:
            found = max(0, found - rng.randint(10, 40))  # a pallet that is not there
        lines.append({"lot": line["lot"], "counted": found})
    if not lines:
        run.call("warehouse", "POST", f"/stock/counts/{count['id']}/cancel")
        return
    cut = rng.randint(1, len(lines)) if len(lines) > 2 and rng.random() < 0.4 else len(lines)
    for batch in (lines[:cut], lines[cut:]):
        if batch:
            run.call("warehouse", "POST", f"/stock/counts/{count['id']}/lines", {"lines": batch})
    run.call("viewer", "GET", f"/stock/counts/{count['id']}")
    if rng.random() < 0.08:
        run.call("warehouse", "POST", f"/stock/counts/{count['id']}/cancel")
    else:
        status, posted = run.call("warehouse", "POST", f"/stock/counts/{count['id']}/post")
        if status == 200 and isinstance(posted, dict) and posted.get("status") not in ("posted", None):
            if rng.random() < 0.4:
                run.call("warehouse", "POST", f"/stock/counts/{count['id']}/approve")
            run.call("finance", "POST", f"/stock/counts/{count['id']}/approve")
    run.call("viewer", "GET", "/stock/counts", None, {"warehouse": warehouse})
    run.call("viewer", "GET", "/stock", None, {"warehouse": warehouse})
    run.call("finance", "GET", "/reports/stock-valuation")
    run.call("viewer", "GET", "/stock/moves", None, {"sort": "-seq", "limit": "20"})


def kit_workflow(run: Run, rng: random.Random, number: int) -> None:
    """A kit from definition to building: a new product, its bill of materials from what one store holds (a first
    attempt sometimes refused), builds (sometimes too many first), now and then sold or taken apart again."""
    warehouse = rng.choice(WAREHOUSES)
    rows = stock_of(run, warehouse)
    if len(rows) < 2:
        warehouse, rows = "MAIN", stock_of(run, "MAIN")
    sku = f"KIT-{rng.choice(['BRK', 'BAK', 'PIC', 'OFF', 'PAN', 'GFT', 'CAF', 'MKT'])}-{number % 100:02d}"
    run.call("admin", "POST", "/products", {"sku": sku, "name": rng.choice(KIT_NAMES), "category": rng.choice(["pantry", "beverages", "packaging"]),
                                            "base_price": rng.randint(20, 160) * 100, "weight_g": rng.randint(2, 30) * 1000})
    parts = rng.sample(rows, min(len(rows), rng.randint(2, 4)))
    components = [{"sku": row["sku"], "qty": rng.randint(1, 3)} for row in parts]
    if rng.random() < 0.25:  # a first try the server refuses: the kit in itself, an unknown product, or one component
        wrong = rng.choice([components + [{"sku": sku, "qty": 1}], components + [{"sku": "NOPE-0000", "qty": 1}], components[:1]])
        run.call("admin", "PUT", f"/kits/{sku}", {"components": wrong})
    status, _ = run.call("admin", "PUT", f"/kits/{sku}", {"components": components})
    if status != 200:
        return
    available = {row["sku"]: row["available"] for row in rows}
    most = min(available.get(part["sku"], 0) // part["qty"] for part in components)
    if most < 1 or rng.random() < 0.3:
        run.call("warehouse", "POST", f"/kits/{sku}/builds", {"warehouse": warehouse, "qty": most + rng.randint(1, 50)})
    if most >= 1:
        status, build = run.call("warehouse", "POST", f"/kits/{sku}/builds", {"warehouse": warehouse, "qty": rng.randint(1, min(most, 12))})
        if status == 201 and rng.random() < 0.35:
            status, order = run.call("sales", "POST", "/orders", {"customer": rng.choice(["C-0002", "C-0003", "C-0005"]),
                                                                    "lines": [{"sku": sku, "qty": rng.randint(1, 3)}]})
            if status == 201:
                run.call("sales", "POST", f"/orders/{order['id']}/confirm")
        if status in (200, 201) and isinstance(build, dict) and build.get("id") and rng.random() < 0.3:
            run.call("warehouse", "POST", f"/builds/{build['id']}/disassemble", {"qty": 1})
    run.call("viewer", "GET", "/kits")
    run.call("viewer", "GET", "/builds", None, {"sku": sku})
    run.call("viewer", "GET", "/stock", None, {"warehouse": warehouse})


# ------------------------------------------------------------------ office routines

# Documented calls the legacy streams never make, or only ever see refused, each in the routine it belongs to: one fresh
# workspace and one unit per scenario, like the counts and kits above, every answer the reference's own.
STAFF = ("Noor Berg", "Ivo Hale", "Mara Lindqvist", "Tomas Novak", "Lena Okafor", "Akio Sato", "Rui Santos", "Elif Kaya", "Jonas Brandt",
         "Priya Nair", "Sven Moreau", "Ines Kowalski", "Zofia Wrona", "Kwame Mensah")
STAFF_ROLES = ("sales", "warehouse", "finance", "viewer")
NO_USER = ("U-17", "U-42", "U-99")
NOT_ADMIN = ("sales", "warehouse", "finance", "viewer")
# products that keep no expiry date, and what a case weighs, for receipts, orders and parcels
STAPLES = {"FLR-WHT-25": 25200, "OIL-OLV-05": 4900, "SGR-WHT-25": 25100, "WTR-STL-24": 12700, "BOX-CRD-50": 8200, "FLM-WRP-04": 3100}
LIST_PRICES = {"APL-GRN-10": 2450, "TOM-VIN-05": 1890, "MLK-WHL-12": 1395, "BTR-SLT-40": 8900, "FLR-WHT-25": 1975, "OIL-OLV-05": 3650,
               "JCE-ORG-06": 1140, "WTR-STL-24": 720, "BOX-CRD-50": 2890, "FLM-WRP-04": 1999}
NEW_CUSTOMERS = (("Quay Bistro", "NORD"), ("Oak & Rye", "SUD"), ("Fennel Deli", "ISLE"), ("Hafen Kantine", "EXPORT"), ("Café Lumière", "SUD"),
                 ("Tidewater Inn", "NORD"))
NEW_SUPPLIERS = ("Fjord Fisheries", "Valle Verde Olive Co", "Northern Mills", "Kestrel Packaging", "Brightwater Springs", "Alpine Creamery",
                 "Sunfield Growers", "Harbour Paper Goods")
SUPPLIER_TERMS = ("COD", "NET15", "NET30", "NET45", "EOM10")
# queries staff save as reports; journal_lines and payments are closed to the sales and warehouse roles
REPORT_QUERIES = (
    ("Customers by tier", "select tier, count(*), sum(credit_limit) as lim, avg(exposure) from customers group by tier order by lim desc, tier"),
    ("Orders by status", "select status, count(*) from orders group by status having count(*) >= 1 order by count(*) desc, status"),
    ("Billing by tier", "select customer.tier, month(date) as m, sum(total) as billed, sum(balance), max(days_overdue) from invoices "
                        "group by customer.tier, month(date) order by 1, 2"),
    ("Stock value", "select sku.category as cat, warehouse, sum(value) as v, count(*) from lots where not expired group by sku.category, "
                    "warehouse having v > 500 order by v desc, cat, warehouse"),
    ("Buying by supplier", "select supplier.name, status, count(*), sum(amount), sum(received * unit_cost) from purchase_lines "
                           "group by supplier.name, status order by 1, 2"),
    ("Account totals", "select account, account.name, sum(debit), sum(credit), sum(amount) from journal_lines where kind != 'closing' "
                       "group by account, account.name order by account"),
    ("Takings by week", "select week(date), count(*), count(distinct customer), sum(amount), sum(unapplied) from payments group by week(date) "
                        "order by 1"),
    ("Freight by tier", 'select "order".customer.tier, count(*), sum(cost), sum(units), avg(coalesce(freight, 0)) from shipments '
                        'group by "order".customer.tier order by 2 desc, 1'),
)
# manual journal entries: what the money was, the account debited and the one credited (none of them a control account)
ENTRIES = (("Bank charges", "6000", "1000"), ("Owner pays in", "1000", "3000"), ("Owner drawing", "3000", "1000"),
           ("Freight paid at the door", "6300", "1000"), ("Sales tax paid over", "2200", "1000"), ("Delivery income booked as sales", "4000", "4100"))
CARRIERS = {"GEX": ("C-0002", "C-0003", "C-0004", "C-0005"), "IFY": ("C-0005",), "LOC": ("C-0002", "C-0004"), "NLN": ("C-0002", "C-0003", "C-0004")}
CARRIER_LIMIT = {"GEX": 70000, "IFY": 250000, "LOC": 30000, "NLN": 500000}


def day(offset: int) -> str:
    return (trading.DEMO_START + datetime.timedelta(days=offset)).isoformat()


def users_routine(run: Run, rng: random.Random, number: int) -> None:
    """The staff list: someone joins (an address already in use refused), is read by an admin, by themself and by a
    colleague, has their role, name or address changed (by someone not an admin, an admin's own role, a role or a name
    that is not one, an unknown user, refused), works under the new role, leaves for a while and comes back."""
    if rng.random() < 0.3:  # someone without the right tries first
        run.call(rng.choice(NOT_ADMIN), "POST", "/users", {"name": rng.choice(STAFF), "role": "viewer"})
    names = rng.sample(STAFF, 2)
    role = rng.choice(STAFF_ROLES)
    address = names[0].lower().replace(" ", ".") + "@stockwell.example"
    status, joined = run.call("admin", "POST", "/users", {"name": names[0], "role": role, "email": rng.choice([address, address.title()])})
    if status != 201:
        return
    user = joined["id"]
    if rng.random() < 0.5:  # a second newcomer, now and then given the first one's address
        run.call("admin", "POST", "/users", {"name": names[1], "role": rng.choice(STAFF_ROLES), **({"email": address} if rng.random() < 0.5 else {})})
    run.call("admin", "GET", f"/users/{user}")
    run.call(role, "GET", f"/users/{user}", headers={"x-user": user})
    run.call(rng.choice(NOT_ADMIN), "GET", f"/users/{user}")
    if rng.random() < 0.4:
        run.call("viewer", "GET", f"/users/{rng.choice(NO_USER)}")
    for _ in range(rng.randint(1, 3)):
        refused = rng.choice(("not_admin", "own_role", "invalid", "unknown", "field"))
        if refused == "not_admin":
            run.call(rng.choice(("sales", "warehouse", "viewer")), "PATCH", f"/users/{user}", {"role": "admin"})
        elif refused == "own_role":
            run.call("admin", "PATCH", "/users/U-01", {"role": rng.choice(STAFF_ROLES)})
        elif refused == "invalid":
            run.call("admin", "PATCH", f"/users/{user}", rng.choice(({"role": "owner"}, {"name": ""}, {"email": "not an address"}, {"name": 7})))
        elif refused == "unknown":
            run.call("admin", "PATCH", f"/users/{rng.choice(NO_USER)}", {"name": names[0]})
        else:
            run.call("admin", "PATCH", f"/users/{user}", {"phone": "+47 512 33 481"})
    role = rng.choice([other for other in STAFF_ROLES if other != role])
    change: dict[str, Any] = {"role": role}
    if rng.random() < 0.5:
        change["name"] = f"{names[0]}-{rng.choice(('Lind', 'Ross', 'Vale'))}"
    if rng.random() < 0.4:
        change["email"] = None if rng.random() < 0.5 else names[0].split()[0].lower() + "@branch.stockwell.example"
    run.call("admin", "PATCH", f"/users/{user}", change)
    if rng.random() < 0.3:
        run.call("admin", "PATCH", f"/users/{user}", {})
    order = {"customer": rng.choice(("C-0002", "C-0003", "C-0005")), "lines": [{"sku": rng.choice(tuple(STAPLES)), "qty": rng.randint(2, 20)}]}
    run.call(role, "POST", "/orders", order, headers={"x-user": user})  # what the new role may do
    run.call("admin", "POST", f"/users/{user}/deactivate")
    run.call(role, "GET", "/auth/me", headers={"x-user": user})
    if rng.random() < 0.4:
        run.call(rng.choice(NOT_ADMIN), "POST", f"/users/{user}/activate")
    if rng.random() < 0.3:
        run.call("admin", "POST", f"/users/{rng.choice(NO_USER)}/activate")
    run.call("admin", "POST", f"/users/{user}/activate")
    if rng.random() < 0.3:
        run.call("admin", "POST", f"/users/{user}/activate")  # already back: nothing changes
    run.call(role, "GET", "/auth/me", headers={"x-user": user})
    run.call(rng.choice(tuple(ROLES)), "GET", "/auth/permissions")
    run.call("viewer", "GET", "/users", None, rng.choice(({}, {"sort": "-id"}, {"sort": "name", "limit": "3"}, {"q": names[0].split()[0].lower()})))
    run.call("admin", "GET", f"/users/{user}")
    run.call("viewer", "GET", "/activity", None, {"kind": "user"})


def workspace_routine(run: Run, rng: random.Random, number: int) -> None:
    """The workspace's own page through a day: a monitor checks the service, staff open the summary (no user, an unknown
    one, or a workspace that is not there, refused), the company takes on customers, products, stock, orders and staff
    and moves its calendar on, and the summary follows; in every fourth an integration reads the API description. The
    answer the workspace was created with, the same summary, is judged too (`created`)."""
    run.judge_creation = True
    run.call("viewer", "GET", "/api/health", scoped=False, headers={})
    run.call("viewer", "GET", "/api/ready", scoped=False, headers={})
    if number % 4 == 1:  # every fourth scenario, from the first
        run.call("viewer", "GET", "/api/openapi.json", scoped=False, headers={})
    run.call(rng.choice(tuple(ROLES)), "GET", "")
    if rng.random() < 0.3:
        run.call("viewer", "GET", "", headers=rng.choice(({}, {"x-user": rng.choice(NO_USER)})))
    if rng.random() < 0.25:  # a till still pointed at a branch that was closed, or a mistyped id
        run.call("viewer", "GET", f"/api/ws/{rng.choice(('closed-branch-7', 'ws-0000'))}", scoped=False)
    actions = rng.sample(("customer", "product", "receipt", "order", "user", "clock"), rng.randint(2, 4))
    if rng.random() < 0.3:
        actions.insert(rng.randint(0, len(actions)), "refused")
    for turn, action in enumerate(actions, start=1):
        if action == "customer":
            name, region = rng.choice(NEW_CUSTOMERS)
            run.call("admin", "POST", "/customers", {"name": name, "region": region})
        elif action == "product":
            sku = f"NEW-{rng.choice(('TEA', 'RCE', 'SLT', 'CUP'))}-{turn:02d}"
            run.call("admin", "POST", "/products", {"sku": sku, "name": rng.choice(("Green tea 100 bags", "Basmati rice 10 kg", "Sea salt 1 kg",
                                                                                  "Paper cups 1000")),
                                                   "category": rng.choice(("pantry", "beverages", "packaging")), "base_price": rng.randint(8, 90) * 100,
                                                   "weight_g": rng.randint(1, 20) * 500})
        elif action == "receipt":
            sku = rng.choice(tuple(STAPLES))
            run.call("warehouse", "POST", "/stock/receipts", {"sku": sku, "warehouse": rng.choice(("MAIN", "EAST")), "qty": rng.randint(5, 60),
                                                              "unit_cost": round(LIST_PRICES.get(sku, 2000) * rng.uniform(0.5, 0.7))})
        elif action == "order":
            status, placed = run.call("sales", "POST", "/orders", {"customer": rng.choice(("C-0002", "C-0004")),
                                                                    "lines": [{"sku": rng.choice(("WTR-STL-24", "FLR-WHT-25")), "qty": rng.randint(2, 12)}]})
            if status == 201 and rng.random() < 0.6:
                status, _ = run.call("sales", "POST", f"/orders/{placed['id']}/confirm")
                status, shipped = run.call("warehouse", "POST", f"/orders/{placed['id']}/shipments") if status == 200 else (0, None)
                if status == 201 and (shipped or {}).get("items"):
                    run.call("finance", "POST", f"/shipments/{shipped['items'][0]['id']}/invoice")
        elif action == "user":
            run.call("admin", "POST", "/users", {"name": rng.choice(STAFF), "role": rng.choice(STAFF_ROLES)})
        elif action == "clock":
            run.call("admin", "POST", "/clock/advance", {"days": rng.randint(1, 10)})
        else:
            run.call(rng.choice(("viewer", "warehouse")), "POST", "/customers", {"name": rng.choice(NEW_CUSTOMERS)[0], "region": "NORD"})
        if rng.random() < 0.5:
            run.call(rng.choice(tuple(ROLES)), "GET", "")
    run.call(rng.choice(tuple(ROLES)), "GET", "")


def price_list_routine(run: Run, rng: random.Random, number: int) -> None:
    """A price list from draft to till: finance reads the lists, drafts one for a customer (a draft with a mistake, or
    from someone without the right, refused), reads it back, puts the customer on it, and the price check follows the
    list once its first day comes; now and then its entries are replaced and the check follows again."""
    if rng.random() < 0.3:
        run.call(rng.choice(("sales", "warehouse", "viewer")), "POST", "/price-lists", {"name": "Hotel list", "entries": []})
    run.call("viewer", "GET", "/price-lists", None, rng.choice(({}, {"sort": "name"}, {"sort": "-id", "limit": "2"}, {"q": "list"})))
    customer, name = rng.choice((("C-0002", "Linden autumn list"), ("C-0003", "Castello contract"), ("C-0004", "Hotel list"),
                                 ("C-0005", "Isle wholesale"), ("C-0007", "Export list")))
    skus = sorted(rng.sample(sorted(LIST_PRICES), rng.randint(2, 5)))
    entries = [{"sku": sku, "price": round(LIST_PRICES[sku] * rng.uniform(0.84, 0.96))} for sku in skus]
    if rng.random() < 0.5:
        entries.append({"sku": skus[0], "min_qty": rng.choice((6, 12, 24)), "price": round(entries[0]["price"] * 0.95)})
    body: dict[str, Any] = {"name": name, "entries": entries}
    opens = 0
    if rng.random() < 0.5:
        opens = rng.randint(2, 9)
        body.update(valid_from=day(opens), valid_to=day(opens + rng.randint(30, 90)))
    if rng.random() < 0.45:
        mistake = rng.choice(("sku", "price", "repeat", "dates"))
        wrong = dict(body, entries=[dict(entry) for entry in entries])
        if mistake == "sku":
            wrong["entries"][0]["sku"] = "NOPE-0001"
        elif mistake == "price":
            wrong["entries"][-1]["price"] = -rng.randint(1, 500)
        elif mistake == "repeat":
            wrong["entries"].append(dict(entries[0], price=entries[0]["price"] - 10))
        else:
            wrong.update(valid_from=day(20), valid_to=day(5))
        run.call("finance", "POST", "/price-lists", wrong)
    status, made = run.call(rng.choice(("finance", "admin")), "POST", "/price-lists", body)
    if status != 201:
        return
    run.call("viewer", "GET", f"/price-lists/{made['id']}")
    run.call("sales", "GET", "/price-lists", None, rng.choice(({"q": name.split()[0].lower()}, {"sort": "-id", "limit": "2"}, {})))
    status, current = run.call("finance", "GET", f"/customers/{customer}")
    run.call("finance", "PATCH", f"/customers/{customer}", {"price_list": made["id"], "version": current["version"]})
    sku, qty = rng.choice(skus), rng.choice((1, 6, 12, 30))
    run.call("viewer", "GET", "/prices/quote", None, {"customer": customer, "sku": sku, "qty": str(qty)})
    if opens:
        run.call("admin", "POST", "/clock/advance", {"days": opens + rng.randint(0, 3)})
        run.call("viewer", "GET", "/prices/quote", None, {"customer": customer, "sku": sku, "qty": str(qty)})
    if rng.random() < 0.4:
        run.call("finance", "PUT", f"/price-lists/{made['id']}/entries",
                 {"entries": [dict(entry, price=entry["price"] - rng.randint(5, 60)) for entry in entries]})
        run.call("viewer", "GET", "/prices/quote", None, {"customer": customer, "sku": sku, "qty": str(qty)})
    run.call("viewer", "GET", "/price-lists", None, {"sort": "-id", "limit": "3"})


def promotion_routine(run: Run, rng: random.Random, number: int) -> None:
    """The promotions calendar: marketing reads what runs, adds a promotion or two (a mistake, or someone without the
    right, refused), ends one early (twice refused), and the list, filtered by kind, by whether a promotion still runs
    and by name, follows; a price check shows the effect, and so does the calendar moving on."""
    run.call("viewer", "GET", "/promotions", None, rng.choice(({}, {"active": "true"}, {"kind": "threshold"}, {"sort": "-priority"})))
    if rng.random() < 0.3:
        run.call(rng.choice(("sales", "warehouse", "viewer")), "POST", "/promotions",
                 {"name": "Weekend deal", "kind": "amount", "sku": "OIL-OLV-05", "value": 150, "starts": day(1), "ends": day(3)})
    made = []
    for _ in range(rng.randint(1, 2)):
        kind, sku, starts = rng.choice(("percent", "amount", "bundle", "threshold")), rng.choice(sorted(LIST_PRICES)), rng.randint(0, 6)
        body: dict[str, Any] = {"name": f"{rng.choice(('Spring', 'Market', 'Trade', 'Weekday'))} {kind} {len(made) + 1}", "kind": kind,
                                "starts": day(starts), "ends": day(starts + rng.randint(5, 40))}
        if kind == "percent":
            body.update(value=rng.choice((500, 750, 1000, 1500)), **({"sku": sku} if rng.random() < 0.5 else {"category": rng.choice(("dairy", "pantry",
                                                                                                                                       "beverages"))}))
        elif kind == "amount":
            body.update(value=rng.randint(5, 40) * 10, sku=sku)
        elif kind == "bundle":
            body.update(sku=sku, buy=rng.choice((6, 10, 12)), free=rng.choice((1, 2)))
        else:
            body.update(threshold=rng.choice((60000, 150000)), value=rng.choice((250, 500, 900)))
        if rng.random() < 0.4:
            body["tiers"] = rng.sample(["retail", "trade", "key"], rng.randint(1, 2))
        if rng.random() < 0.4:
            body.update(stackable=rng.random() < 0.5, priority=rng.randint(5, 90))
        if rng.random() < 0.3:  # a mistake first: a percentage past the limit, or an end before the start
            run.call("finance", "POST", "/promotions", dict(body, **({"value": 20000} if kind == "percent" else {"ends": day(starts - 1)})))
        status, promotion = run.call(rng.choice(("finance", "admin")), "POST", "/promotions", body)
        if status == 201:
            made.append(promotion)
    ending = rng.choice([promotion["id"] for promotion in made] + ["PR-001", "PR-002", "PR-004", "PR-007"])
    run.call("finance", "POST", f"/promotions/{ending}/end")
    if rng.random() < 0.4:
        run.call("finance", "POST", f"/promotions/{ending}/end")
    run.call("viewer", "GET", "/promotions", None, {"active": "false"})
    run.call("viewer", "GET", "/promotions", None, {"kind": rng.choice([promotion["kind"] for promotion in made] or ["percent"])})
    sku = next((promotion["sku"] for promotion in made if promotion.get("sku")), rng.choice(sorted(LIST_PRICES)))
    run.call("viewer", "GET", "/prices/quote", None, {"customer": rng.choice(trading.CUSTOMERS), "sku": sku, "qty": str(rng.choice((1, 6, 12)))})
    if rng.random() < 0.5:
        run.call("admin", "POST", "/clock/advance", {"days": rng.randint(5, 30)})
        run.call("viewer", "GET", "/promotions", None, {"active": "true"})
    run.call("viewer", "GET", "/promotions", None, rng.choice(({"q": "basket"}, {"sort": "starts"}, {"limit": "3", "offset": "2"}, {"sort": "-id"})))


def supplier_routine(run: Run, rng: random.Random, number: int) -> None:
    """A new supplier, from the first call to an order: finance adds them (a name in use, an unknown region, a lead time
    too long, or someone without the right, refused), sets their prices and a buyer drafts an order; a dispute blocks
    them and ordering stops, then they are unblocked (by someone without the right, or twice, refused) and the order goes."""
    name, region = rng.choice(NEW_SUPPLIERS), rng.choice(("NORD", "SUD", "ISLE", "EXPORT"))
    if rng.random() < 0.3:
        run.call(rng.choice(("sales", "warehouse", "viewer")), "POST", "/suppliers", {"name": name, "region": region})
    if rng.random() < 0.4:
        run.call("finance", "POST", "/suppliers", rng.choice(({"name": "Orchard Cooperative", "region": region}, {"name": name, "region": "MARS"},
                                                              {"name": name, "region": region, "lead_days": 200},
                                                              {"name": name, "region": region, "terms": "NET90"})))
    body: dict[str, Any] = {"name": name, "region": region}
    if rng.random() < 0.7:
        body.update(terms=rng.choice(SUPPLIER_TERMS), lead_days=rng.randint(1, 14))
    status, supplier = run.call(rng.choice(("finance", "admin")), "POST", "/suppliers", body)
    if status != 201:
        return
    sid = supplier["id"]
    run.call(rng.choice(tuple(ROLES)), "GET", f"/suppliers/{sid}")
    skus = rng.sample(sorted(STAPLES), rng.randint(1, 3))
    prices = [{"sku": sku, "cost": round(LIST_PRICES.get(sku, 2000) * rng.uniform(0.5, 0.7)), "pack": rng.choice((1, 6, 12))} for sku in skus]
    run.call("finance", "PUT", f"/suppliers/{sid}/prices", {"prices": prices})
    lines = [{"sku": skus[0], "qty": rng.randint(2, 10) * prices[0]["pack"]}]
    status, order = run.call("warehouse", "POST", "/purchase-orders", {"supplier": sid, "warehouse": rng.choice(("MAIN", "EAST", "COLD")), "lines": lines})
    run.call(rng.choice(("finance", "admin")), "POST", f"/suppliers/{sid}/block")
    run.call("warehouse", "POST", "/purchase-orders", {"supplier": sid, "warehouse": "MAIN", "lines": lines})
    if status == 201:
        run.call("warehouse", "POST", f"/purchase-orders/{order['id']}/submit")
    if rng.random() < 0.4:
        run.call(rng.choice(("sales", "warehouse", "viewer")), "POST", f"/suppliers/{sid}/unblock")
    run.call(rng.choice(("finance", "admin")), "POST", f"/suppliers/{sid}/unblock")
    if rng.random() < 0.3:
        run.call("finance", "POST", f"/suppliers/{sid}/unblock")
    if status == 201:
        run.call("warehouse", "POST", f"/purchase-orders/{order['id']}/submit")
    run.call("viewer", "GET", "/suppliers", None, rng.choice(({"region": region}, {"status": "active"}, {"sort": "-lead_days"}, {"q": name.split()[0]})))
    run.call("viewer", "GET", "/purchase-orders", None, {"supplier": sid})


def saved_report_routine(run: Run, rng: random.Random, number: int) -> None:
    """Reports staff keep: someone saves a query for everyone or for themself (a viewer, or a name in use, refused);
    colleagues open it by its number (another's private one is not theirs to see; an admin sees all), run it with
    their own role's access and open it again to see it ran; the owner deletes it in the end (no one else may)."""
    owner = rng.choice(("sales", "warehouse", "finance", "admin"))
    readable = [query for query in REPORT_QUERIES if owner not in ("sales", "warehouse") or not any(table in query[1] for table in
                                                                                                    ("journal_lines", "payments"))]
    name, query = rng.choice(readable)
    shared = rng.random() < 0.6
    if rng.random() < 0.3:
        run.call("viewer", "POST", "/reports/saved", {"name": name, "query": query, "shared": True})
    status, report = run.call(owner, "POST", "/reports/saved", {"name": name, "query": query, "shared": shared})
    if status != 201:
        return
    rid = report["id"]
    if rng.random() < 0.3:
        run.call(owner, "POST", "/reports/saved", {"name": name, "query": rng.choice(readable)[1], "shared": not shared})
    run.call(owner, "GET", f"/reports/saved/{rid}")
    colleague = rng.choice([role for role in ROLES if role != owner])
    run.call(colleague, "GET", f"/reports/saved/{rid}")
    run.call(colleague, "POST", f"/reports/saved/{rid}/run")
    run.call(owner, "POST", f"/reports/saved/{rid}/run")
    if rng.random() < 0.5:
        run.call("admin", "POST", "/clock/advance", {"days": rng.randint(1, 6)})
        run.call(owner, "POST", f"/reports/saved/{rid}/run")
    run.call(rng.choice((owner, "admin")), "GET", f"/reports/saved/{rid}")
    if rng.random() < 0.4:
        run.call("viewer", "GET", f"/reports/saved/RPT-{rng.randint(40, 99):04d}")
    if rng.random() < 0.4:
        run.call(rng.choice([role for role in ("sales", "warehouse", "finance") if role != owner]), "DELETE", f"/reports/saved/{rid}")
    run.call(rng.choice((owner, "admin")), "DELETE", f"/reports/saved/{rid}")
    run.call(owner, "GET", f"/reports/saved/{rid}")
    run.call("viewer", "GET", "/reports/saved")


def journal_routine(run: Run, rng: random.Random, number: int) -> None:
    """Correcting the books: finance posts a manual entry, finds it wrong and reverses it, then posts it again right;
    reversing it twice, reversing an entry the system made or one that does not exist, or someone without the right,
    is refused; the journal, the account and the trial balance show what happened."""
    memo, debit, credit = rng.choice(ENTRIES)
    amount = rng.randint(5, 900) * 50
    if rng.random() < 0.3:
        run.call(rng.choice(("sales", "warehouse")), "POST", "/ledger/journal",
                 {"memo": memo, "lines": [{"account": debit, "debit": amount}, {"account": credit, "credit": amount}]})
    poster = rng.choice(("finance", "admin"))
    if rng.random() < 0.5:
        run.call("admin", "POST", "/clock/advance", {"days": rng.randint(1, 5)})
    status, entry = run.call(poster, "POST", "/ledger/journal", {"memo": memo, "lines": [{"account": debit, "debit": amount},
                                                                                         {"account": credit, "credit": amount}]})
    if status != 201:
        return
    if rng.random() < 0.4:
        run.call(rng.choice(("sales", "warehouse", "viewer")), "POST", f"/ledger/journal/{entry['id']}/reverse")
    run.call(rng.choice(("finance", "admin")), "POST", f"/ledger/journal/{entry['id']}/reverse")
    if rng.random() < 0.4:
        run.call("finance", "POST", f"/ledger/journal/{entry['id']}/reverse")
    if rng.random() < 0.3:
        run.call("finance", "POST", "/ledger/journal/JE-000001/reverse")  # the opening entry the system made
    if rng.random() < 0.3:
        run.call("finance", "POST", f"/ledger/journal/JE-{rng.randint(400, 999):06d}/reverse")
    right = rng.randint(5, 900) * 50
    run.call(poster, "POST", "/ledger/journal", {"memo": memo, "lines": [{"account": debit, "debit": right}, {"account": credit, "credit": right}]})
    run.call("viewer", "GET", "/ledger/journal", None, rng.choice(({"kind": "manual"}, {"account": debit}, {"sort": "-id", "limit": "5"})))
    run.call("viewer", "GET", "/ledger/accounts")
    run.call("finance", "GET", "/reports/trial-balance")


def carrier_routine(run: Run, rng: random.Random, number: int) -> None:
    """A carrier taken off and brought back: a shipment is packed, an admin retires its carrier and the dispatch desk
    is refused it; the carrier is brought back (by someone without the right, an unknown carrier, or one already in
    use, refused), quoted, and the shipment goes out with it."""
    code = rng.choice(sorted(CARRIERS))
    customer = rng.choice(CARRIERS[code])
    sku = rng.choice(("WTR-STL-24", "FLR-WHT-25", "OIL-OLV-05"))
    qty = rng.randint(1, 6)
    run.call("viewer", "GET", "/carriers")
    status, placed = run.call("sales", "POST", "/orders", {"customer": customer, "lines": [{"sku": sku, "qty": qty}]})
    shipment = None
    if status == 201:
        status, _ = run.call("sales", "POST", f"/orders/{placed['id']}/confirm")
        if status == 200:
            status, shipped = run.call("warehouse", "POST", f"/orders/{placed['id']}/shipments")
            shipment = shipped["items"][0]["id"] if status == 201 and shipped.get("items") else None
    weight = STAPLES[sku] * qty
    parcels = [{"weight_g": min(weight - taken, CARRIER_LIMIT[code])} for taken in range(0, weight, CARRIER_LIMIT[code])]
    run.call("admin", "POST", f"/carriers/{code}/retire")
    run.call("viewer", "GET", "/carriers")
    if shipment:
        run.call("warehouse", "POST", f"/shipments/{shipment}/dispatch", {"carrier": code, "parcels": parcels})
    if rng.random() < 0.4:
        run.call(rng.choice(NOT_ADMIN), "POST", f"/carriers/{code}/activate")
    if rng.random() < 0.3:
        run.call("admin", "POST", f"/carriers/{rng.choice(('DHL', 'XXX', 'loc'))}/activate")
    run.call("admin", "POST", f"/carriers/{code}/activate")
    if rng.random() < 0.4:
        run.call("admin", "POST", f"/carriers/{code}/activate")
    run.call("viewer", "GET", f"/carriers/{code}/quote", None, {"weights_g": ",".join(str(parcel["weight_g"]) for parcel in parcels)})
    if shipment:
        run.call("warehouse", "POST", f"/shipments/{shipment}/dispatch", {"carrier": code, "parcels": parcels})
        run.call("viewer", "GET", f"/shipments/{shipment}")
    run.call("viewer", "GET", "/reports/carriers")


def standing_routine(run: Run, rng: random.Random, number: int) -> None:
    """A standing order put on hold and taken up again: sales sets one up, pauses it while the customer is closed and
    resumes it (one already running, one cancelled, or someone without the right, refused); as the calendar moves the
    runs follow, none while it was paused."""
    customer = rng.choice(("C-0002", "C-0003", "C-0004", "C-0005"))
    lines = [{"sku": sku, "qty": rng.randint(2, 30)} for sku in sorted(rng.sample(("WTR-STL-24", "FLR-WHT-25", "OIL-OLV-05", "SGR-WHT-25"),
                                                                                  rng.randint(1, 2)))]
    every, start = rng.choice((7, 7, 14, 21)), rng.randint(2, 8)
    status, order = run.call(rng.choice(("sales", "admin")), "POST", "/standing-orders",
                             {"customer": customer, "every_days": every, "lines": lines, "start": day(start), "auto_confirm": rng.random() < 0.4})
    if status != 201:
        return
    oid = order["id"]
    if rng.random() < 0.3:
        run.call("sales", "POST", f"/standing-orders/{oid}/resume")  # it runs already
    run.call("sales", "POST", f"/standing-orders/{oid}/pause")
    run.call("admin", "POST", "/clock/advance", {"days": start + rng.randint(1, 2 * every)})
    if rng.random() < 0.4:
        run.call(rng.choice(("warehouse", "finance", "viewer")), "POST", f"/standing-orders/{oid}/resume")
    run.call(rng.choice(("sales", "admin")), "POST", f"/standing-orders/{oid}/resume")
    if rng.random() < 0.3:
        run.call("sales", "POST", f"/standing-orders/{oid}/resume")
    run.call("admin", "POST", "/clock/advance", {"days": every + rng.randint(0, every)})
    run.call("viewer", "GET", f"/standing-orders/{oid}")
    if rng.random() < 0.3:
        run.call("sales", "POST", f"/standing-orders/{oid}/cancel")
        run.call("sales", "POST", f"/standing-orders/{oid}/resume")
    run.call("viewer", "GET", "/orders", None, {"customer": customer})


# theme, scenario maker: each theme gets `routines` scenarios, in this order
ROUTINES = (("users", users_routine), ("workspace", workspace_routine), ("price-lists", price_list_routine), ("promotions", promotion_routine),
            ("suppliers", supplier_routine), ("saved-reports", saved_report_routine), ("journal-reversals", journal_routine),
            ("carriers", carrier_routine), ("standing-orders", standing_routine))


def workflows(server: Reference, media: Path, seed: int, counts: int, kits: int, routines: int = 0) -> list[dict[str, Any]]:
    """Scenarios of the counts and kits themes that reach their main workflow, then `routines` scenarios of each office
    routine; one fresh workspace each, one unit each. Every theme draws from its own random stream, so a recording with
    routines holds, before them, exactly what one without them holds."""
    made = []
    for theme, total in (("counts", counts), ("kits", kits)):
        for number in range(1, total + 1):
            rng = random.Random(f"{theme}:{seed}:{number}")
            run = Run(server, media, f"{theme[0].upper()}{number:05d}")
            run.begin(theme, theme=theme)
            count_workflow(run, rng) if theme == "counts" else kit_workflow(run, rng, number)
            run.connection.close()
            made.append({"id": run.id, "theme": theme, "steps": [{key: value for key, value in step.items() if key != "unit"} for step in run.steps]})
    for theme, routine in ROUTINES:
        for number in range(1, routines + 1):
            rng = random.Random(f"{theme}:{seed}:{number}")
            run = Run(server, media, f"R{len(made) - counts - kits + 1:05d}")
            run.begin(theme, theme=theme)
            routine(run, rng, number)
            run.connection.close()
            made.append({"id": run.id, "theme": theme, "steps": [{key: value for key, value in step.items() if key != "unit"} for step in run.steps],
                         **({"created": run.created} if run.judge_creation else {})})
    return made


# ------------------------------------------------------------------ the client's screens

class Capture(ThreadingHTTPServer):
    """A proxy in front of the reference that notes every request the client makes, by screen."""

    daemon_threads = True

    def __init__(self, upstream: int) -> None:
        self.upstream, self.lock, self.label, self.seen = upstream, threading.Lock(), None, []
        super().__init__(("127.0.0.1", 0), CaptureHandler)


class CaptureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: Any) -> None:
        pass

    def forward(self) -> None:
        server: Capture = self.server  # type: ignore[assignment]
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        parts = urlsplit(self.path)
        if parts.path == "/__screen__":
            with server.lock:
                server.label = dict(parse_qsl(parts.query))
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        kept = {key.lower(): value for key, value in self.headers.items() if key.lower() in ("x-user", "accept", "content-type", "idempotency-key")}
        upstream = http.client.HTTPConnection("127.0.0.1", server.upstream, timeout=120)
        upstream.request(self.command, self.path, body=body or None, headers=kept)
        response = upstream.getresponse()
        data = response.read()
        with server.lock:
            server.seen.append({"label": server.label, "method": self.command, "path": parts.path,
                                "query": parse_qsl(parts.query, keep_blank_values=True), "headers": kept, "body": body.decode() if body else None})
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = forward


def look(server: Reference, workspace: str, path: str) -> Any:
    """A read that is not recorded: to find the records a screen will show."""
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=60)
    connection.request("GET", f"/api/ws/{workspace}{path}", headers={"X-User": "U-01"})
    return json.loads(connection.getresponse().read() or b"null")


def screen_urls(server: Reference, workspace: str, wanted: list[str]) -> list[str]:
    """The wanted screens of a workspace, with the records they show filled in as the client's own smoke test picks them."""
    def first(path: str, key: str = "id") -> str | None:
        items = (look(server, workspace, path) or {}).get("items") or []
        return str(items[0][key]) if items else None

    stock = (look(server, workspace, "/stock") or {}).get("items") or []
    ids = {"order": first("/orders?sort=-id"), "shipment": first("/shipments?sort=-id"), "quote": first("/quotes"),
           "standing": first("/standing-orders"), "customer": first("/customers"), "product": first("/products", "sku"),
           "price_list": first("/price-lists"), "lot": next((lot["id"] for row in stock for lot in row.get("lots", [])), None),
           "count": first("/stock/counts"), "po": first("/purchase-orders?sort=-id"), "bill": first("/supplier-bills"),
           "supplier": first("/suppliers"), "work": first("/work-orders"), "recipe": first("/recipes", "sku"), "recall": first("/recalls"),
           "invoice": first("/invoices?sort=-id"), "rebate": first("/rebates"), "statement": first("/bank/statements"), "user": first("/users"),
           "pdf": first("/files?type=pdf&sort=-id"), "picture": first("/files?type=jpeg&sort=-id")}
    urls = []
    for template in wanted:
        names = re.findall(r"\{(\w+)\}", template)
        if all(ids.get(name) for name in names):
            urls.append(template.format(**{name: ids[name] for name in names}))
    return urls


def capture(server: Reference, frontend: Path, plan: list[dict[str, Any]], scratch: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Run the web client over the plan ({ws, urls} entries) and return the requests it made, by (workspace, url)."""
    proxy = Capture(server.port)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    test = frontend / "src" / "test" / "zz_capture_screens.test.tsx"
    plan_file = scratch / "screens-plan.json"
    plan_file.write_text(json.dumps(plan))
    shutil.copy(HERE / "capture_screens.test.tsx", test)
    try:
        done = subprocess.run([str(frontend / "node_modules" / ".bin" / "vitest"), "run", str(test.relative_to(frontend))], cwd=frontend,
                              env=dict(os.environ, CAPTURE_URL=f"http://127.0.0.1:{proxy.server_address[1]}", CAPTURE_PLAN=str(plan_file)),
                              capture_output=True, text=True, timeout=7200)
        if done.returncode != 0:
            raise RuntimeError(f"the client did not run: {done.stdout[-1500:]} {done.stderr[-1500:]}")
    finally:
        test.unlink(missing_ok=True)
        proxy.shutdown()
    found: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for request in proxy.seen:
        if request["label"]:
            found.setdefault((request["label"]["ws"], request["label"]["url"]), []).append(request)
    return found


def screen_requests(requests: list[dict[str, Any]], workspace: str) -> list[dict[str, Any]] | None:
    """A screen's requests in recording order (start-up calls first, then the rest sorted, each once); None to leave it out."""
    unique, keys = [], set()
    for request in requests:
        key = (request["method"], request["path"], tuple(request["query"]), request["body"])
        if key not in keys:
            keys.add(key)
            unique.append(request)
    if any(request["path"].endswith(UNGRADED) or request["method"] != "GET" for request in unique):
        return None
    prefix = f"/api/ws/{workspace}"
    startup = [r for r in unique if r["path"] in ("/api/version", f"{prefix}/auth/me")]
    rest = sorted((r for r in unique if r not in startup), key=lambda r: (r["path"], r["query"]))
    if not rest or any(not r["path"].startswith(prefix) and r["path"] != "/api/version" for r in unique):
        return None
    return sorted(startup, key=lambda r: r["path"] != "/api/version") + rest


def record_screens(run: Run, url: str, requests: list[dict[str, Any]]) -> None:
    run.reconnect()  # the server may have been restarted (on another port) since the run was recorded
    run.begin(url, theme="screens")
    prefix = f"/api/ws/{run.workspace}"
    for request in requests:
        scoped = request["path"].startswith(prefix)
        headers = {key: value for key, value in request["headers"].items() if key in ("x-user", "accept")}
        run.call("viewer", request["method"], request["path"][len(prefix):] if scoped else request["path"], None, dict(request["query"]),
                 scoped=scoped, headers=headers)


# ------------------------------------------------------------------ main

def answers(server: Reference, workspace: str, requests: list[dict[str, Any]]) -> list[Any]:
    """What a workspace answers to a screen's requests, ids written as {ws}; not recorded."""
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=120)
    out = []
    for request in requests:
        path = request["path"].replace(request["workspace"], workspace)
        headers = {key: value for key, value in request["headers"].items() if key in ("x-user", "accept")}
        status, answer = exchange(connection, request["method"], path + encode_query(dict(request["query"])), headers, None)
        out.append([status, json.loads(json.dumps(answer).replace(workspace, "{ws}"))])
    connection.close()
    return out


def fresh_workspace(server: Reference, days: int) -> str:
    """A new workspace with its calendar moved `days` forward: the demo company as it stands on a run's last day, untouched."""
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=120)
    _, created = exchange(connection, "POST", "/api/workspaces", {}, None)
    while days > 0:
        exchange(connection, "POST", f"/api/ws/{created['id']}/clock/advance", {"x-user": ROLES["admin"]}, {"days": min(120, days)})
        days -= min(120, days)
    connection.close()
    return created["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--media", type=Path, required=True, help="the private media folder: the run's files go under trading/")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--term", type=int, default=0, help="runs with a SIGTERM restart at the end of a day")
    parser.add_argument("--kill", type=int, default=0, help="runs with a SIGKILL restart straight after an answered write")
    parser.add_argument("--screens", type=int, default=0, help="client screens opened after each run")
    parser.add_argument("--days", type=int, nargs=2, default=(30, 35), help="the shortest and longest run in days: 30 reach the next month")
    parser.add_argument("--counts", type=int, default=0, help="stock counts, opened to posted, each in a fresh workspace")
    parser.add_argument("--kits", type=int, default=0, help="kits, defined to built, each in a fresh workspace")
    parser.add_argument("--routines", type=int, default=0, help="scenarios of each office routine (ROUTINES), each in a fresh workspace")
    args = parser.parse_args()
    reference = checkout()
    python = os.environ.get("STOCKWELL_PYTHON") or str(reference / "backend" / ".venv" / "bin" / "python")
    scratch = Path(os.environ.get("TMPDIR", "/tmp")) / f"stockwell-live-{os.getpid()}"
    shutil.rmtree(scratch, ignore_errors=True)
    server = Reference(reference / "backend" / "src", python, scratch / "data")
    server.start()
    started = time.time()
    try:
        # the month's photos, clips and notes, made only when there are months: without them nothing under DIR/trading is
        # made or touched, so recording routines alone (record_scenarios.py --append) leaves the media folder as it is
        pool = ({kind: [f"trading/{key}" for key in keys] for kind, keys in trading_media.pool(args.seed, args.media / "trading" / "pool").items()}
                if args.runs else {})
        order = random.Random(f"order:{args.seed}")
        plans = ["term"] * args.term + ["kill"] * args.kill + [None] * (args.runs - args.term - args.kill)
        order.shuffle(plans)
        starts = [trading.STARTS[number % len(trading.STARTS)] for number in range(args.runs)]
        order.shuffle(starts)
        runs: list[Run] = []
        for number in range(1, args.runs + 1):
            rng = random.Random(f"trading:{args.seed}:{number}")
            days = rng.randint(*args.days)
            how = plans[number - 1]
            restart = (how, rng.randint(5, days - 4)) if how else None
            run = Run(server, args.media, f"T{number:05d}")
            month = trading.Month(run.call, run.begin, invoice_maker(args.media, args.seed, run.id), pool, rng, days, restart, starts[number - 1])
            month.run()
            run.days, run.restart, run.start, run.last = days, how, starts[number - 1].isoformat(), month.today
            runs.append(run)
            print(json.dumps({"run": run.id, "start": run.start, "days": days, "restart": how, "steps": len(run.steps),
                              "seconds": round(time.time() - started)}), file=sys.stderr)
        if args.screens:
            # each run opens its share of the client's screens, with spares: a screen that shows nothing the month changed
            # (it answers as a fresh workspace on the same day does) is left out and the next one taken (QA 05 S1)
            spare = args.screens // 2 + 2
            eligible = list(SCREENS)
            random.Random(f"screens:{args.seed}").shuffle(eligible)
            plan, wanted = [], {}
            for index, run in enumerate(runs):
                picks = [eligible[(index * (args.screens + spare) + k) % len(eligible)] for k in range(args.screens + spare)]
                wanted[run.id] = screen_urls(server, run.workspace, picks)
                plan.append({"ws": run.workspace, "urls": wanted[run.id]})
            found = capture(server, reference / "frontend", plan, scratch)
            static = 0
            for run in runs:
                fresh, kept = fresh_workspace(server, (run.last - trading.DEMO_START).days), 0
                for url in wanted[run.id]:
                    requests = screen_requests(found.get((run.workspace, url), []), run.workspace)
                    if not requests or kept == args.screens:
                        continue
                    for request in requests:
                        request["workspace"] = run.workspace
                    if answers(server, run.workspace, requests) == answers(server, fresh, requests):
                        static += 1
                        continue
                    record_screens(run, url, requests)
                    kept += 1
            print(json.dumps({"screens left out as unchanged by the month": static}), file=sys.stderr)
        made = workflows(server, args.media, args.seed, args.counts, args.kits, args.routines)
        scenarios = [run.scenario(days=run.days, restart=run.restart, start=run.start) for run in runs] + made
    finally:
        server.stop("kill")
        shutil.rmtree(scratch, ignore_errors=True)
    # keep under DIR/trading only the files these months upload, so nothing unused is packaged with them
    used = {step.get("body_file") or step["body_insert"]["file"] for scenario in scenarios for step in scenario["steps"]
            if "body_file" in step or "body_insert" in step}
    for path in sorted((args.media / "trading").rglob("*"), reverse=True) if args.runs else ():
        if path.is_file() and path.relative_to(args.media).as_posix() not in used:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    corpus = {"scenarios": scenarios, "recorded_with": {"runs": args.runs, "term": args.term, "kill": args.kill, "screens": args.screens,
                                                        "days": list(args.days), "counts": args.counts, "kits": args.kits,
                                                        "routines": args.routines}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(corpus, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    months = [s for s in scenarios if s.get("units")]
    units = sum(len(s["units"]) for s in months)
    screens = sum(1 for s in months for unit in s["units"] if unit["theme"] == "screens")
    print(json.dumps({"runs": len(months), "units": units, "days": units - screens, "screens": screens, "workflows": len(made),
                      "requests": sum(len(s["steps"]) for s in scenarios), "seconds": round(time.time() - started)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
