"""A month of trading in one workspace, through the public API, one unit per trading day.

Like the reference's own demo traffic (operations/demo.py), every call is an ordinary request and a
refused one is kept as it was answered; a run is the stream of requests a busy back office makes, not
a script that stops at the first sold-out product. On top of the demo's sales, buying, making and
one-off events, a run lasts a month and crosses its end, and files sit on the business path:

- every day: orders placed and confirmed, stock allocated, shipped, invoiced, paid and dispatched;
  some shipments get a proof-of-delivery photo or clip, read back as a thumbnail or described;
- every third day a purchase order to one of the five suppliers, received in full or in part;
  one to three days later the supplier's invoice arrives as a PDF (scripts/trading_media.py) and is
  read; the clerk books it, accepts its problems, unlocks it first, enters a scanned one by hand,
  or leaves a wrong one unbooked; on Fridays approved bills are paid;
- quotes, standing orders, kit builds, returns with damage photos and voice notes, a stock count, a
  recall and its close, weekly bank statements, the dunning list on Mondays, weekly production;
- on the month's last day the bank statement is reconciled, foreign balances revalued, receivables
  aged, statements read and late payers chased; on the first day of the next month the books are
  closed the way an accounts team does it: commissions paid out, the month's rebate settled, the
  reorder report turned into purchase orders, a planning run firmed, budget, income statement and
  trial balance read, and the period closed;
- a run ends with the reads of the stock ledger, journal, trial balance, receivables, stock and the
  integrity checks.

Runs start on different dates, so their month ends differ: March into April, the end of June (a
quarter and a half year), the year's end into January, and February of a leap year. Customers and
notes are written in many languages. Now and then an integration sends a photo as base64 inside
JSON (one under the limit for a file sent that way, one over it, and a body over the server's limit
for any JSON body), and the office imports a CRM's customer list: a dry run that finds mistakes, the
list put right, the whole list (over the row limit) and a full export (over the size limit). In a
run with a planned restart, the files uploaded before it are read again after it.
"""

from __future__ import annotations

import calendar
import datetime
import random
from collections.abc import Callable
from typing import Any

CUSTOMERS = ["C-0001", "C-0002", "C-0003", "C-0004", "C-0005", "C-0006", "C-0007"]
PRODUCTS = ["APL-GRN-10", "BTR-SLT-40", "FLR-WHT-25", "JCE-ORG-06", "MLK-WHL-12", "OIL-OLV-05", "SGR-WHT-25", "WTR-STL-24", "TOM-VIN-05",
            "BOX-CRD-50"]
CATALOGUE = {"SUP-0001": [("APL-GRN-10", 10), ("TOM-VIN-05", 5)], "SUP-0002": [("MLK-WHL-12", 20), ("BTR-SLT-40", 1)],
             "SUP-0003": [("FLR-WHT-25", 40), ("SGR-WHT-25", 40), ("OIL-OLV-05", 12)],
             "SUP-0004": [("BOX-CRD-50", 5), ("FLM-WRP-04", 8)], "SUP-0005": [("WTR-STL-24", 60), ("JCE-ORG-06", 30)]}
WAREHOUSE = {"SUP-0001": "COLD", "SUP-0002": "COLD", "SUP-0003": "MAIN", "SUP-0004": "MAIN", "SUP-0005": "EAST"}
JUICE = {"batch_size": 40, "yield_bp": 9500, "labour_cost": 3000, "shelf_days": 30,
         "ingredients": [{"sku": "WTR-STL-24", "qty": 5}, {"sku": "SGR-WHT-25", "qty": 1}],
         "steps": [{"centre": "MIX", "minutes": 200}, {"centre": "PACK", "minutes": 300}]}
CONTENT_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "mp4": "video/mp4", "mov": "video/quicktime", "m4a": "audio/mp4",
                 "mp3": "audio/mpeg", "ogg": "audio/ogg"}
DEMO_START = datetime.date(2031, 3, 3)  # a fresh workspace's first day
# where runs start: each crosses a month's end and reaches the next month's first day within 30 days
STARTS = (DEMO_START, datetime.date(2031, 6, 2), datetime.date(2031, 12, 3), datetime.date(2032, 2, 1))
NOTES = ("Lieferung bis 10 Uhr – Hintereingang", "Livrer avant midi, quai n°2", "Consegna al piano terra, citofono «Rossi»", "请在上午送货",
         "Proszę dzwonić przed dostawą – tel. 512 334 812", "Entregar na portaria — Sr. João", "Ring the bell twice", "午前中にお届けください",
         "Leverans via lastkaj, fråga efter Åsa", "Teslimat öncesi arayın: Gökçe", "Без предварительного звонка не привозить", "")
# names typed for uploads stay within Latin-1: the server names a file it sends back in a header, and answers 500 for a name
# with a letter outside it (a fault of the sealed server the corpus does not exercise; notes and customer names carry the rest)
FILE_LABELS = ("Lieferschein Müller", "Photo réception", "Recepción almacén", "Leverans Åhléns", "Livraison côté cour", "Entrega São João")
MAX_JSON_BODY = 6_000_000  # the largest JSON body the server reads

Call = Callable[..., tuple[int, Any]]


def content_type(name: str) -> str:
    return CONTENT_TYPES.get(name.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def ok(status: int, payload: Any) -> Any:
    return payload if status < 300 and isinstance(payload, dict) else None


class Month:
    """One run. `call(role, method, path, body=None, query=None, file=None, restart=None)` records a request and returns
    (status, answer); `begin(label)` starts the next unit; `invoice_file(purchase_order, supplier, names, date)` makes the
    supplier's PDF and returns its media key with what it says; `pool` holds media keys of photos, clips and voice notes."""

    def __init__(self, call: Call, begin: Callable[[str], None], invoice_file: Callable[..., tuple[str, dict[str, Any], str]],
                 pool: dict[str, list[str]], rng: random.Random, days: int, restart: tuple[str, int] | None = None,
                 start: datetime.date = DEMO_START) -> None:
        self.call, self.begin, self.invoice_file, self.pool, self.rng = call, begin, invoice_file, pool, rng
        self.days, self.restart, self.start = days, restart, start
        self.today = DEMO_START
        self.stored: list[tuple[str, str]] = []  # files uploaded so far: (id, kind)
        self.shipments: list[str] = []
        integration_day = rng.randint(3, days - 4)
        self.integration_day = integration_day if pool.get("sized") else None
        self.import_day = rng.randint(2, days - 5) if pool.get("import") and rng.random() < 0.4 else None
        self.open_orders: list[str] = []
        self.arriving: dict[int, list[str]] = {}
        self.bills: dict[str, str] = {}  # booked or entered supplier bills not yet paid, with their status
        self.invoices: list[dict[str, Any]] = []
        self.bank_through = ""  # the last statement's last day
        self.bank_closing = 0
        self.supplier_turn = 0
        self.kill_armed = False

    def arm(self, extra: dict[str, Any]) -> None:
        """On the day of a SIGKILL restart, count down to a write drawn at random: the recorder kills the server after the
        first write from there that is answered 2xx (an order, a shipment, a payment, an upload: whatever comes), or after
        the day's last request when the day has fewer writes."""
        if self.kill_armed and "restart" not in extra:
            self.kill_countdown -= 1
            if self.kill_countdown <= 0:
                extra["restart"] = "kill?"
                self.kill_armed = False

    def do(self, role: str, method: str, path: str, body: Any = None, query: dict[str, str] | None = None, **extra: Any) -> Any:
        if method == "POST":
            self.arm(extra)
        return ok(*self.call(role, method, path, body, query, **extra))

    # ------------------------------------------------------------------ the run

    def run(self) -> None:
        self.begin("day 1")
        left = (self.start - DEMO_START).days
        while left > 0:  # the calendar moves at most 120 days a request
            status, moved = self.call("admin", "POST", "/clock/advance", {"days": min(120, left)})
            left -= min(120, left)
            if isinstance(moved, dict) and moved.get("today"):
                self.today = datetime.date.fromisoformat(moved["today"])
        self.setup()
        for day in range(self.days):
            if day:
                self.begin(f"day {day + 1}")
            self.trade(day)
        self.final_reads()

    def setup(self) -> None:
        self.do("admin", "PUT", "/recipes/JCE-ORG-06", JUICE)
        self.do("admin", "PUT", "/kits/BOX-CRD-50", {"components": [{"sku": "FLM-WRP-04", "qty": 2}, {"sku": "WTR-STL-24", "qty": 1}]})
        self.do("finance", "POST", "/fx/rates", {"currency": "USD", "rate": self.rng.choice([905_100, 921_700, 934_400])})
        self.do("finance", "PUT", "/fx/customers/C-0006", {"currency": "USD"})
        first = self.start.replace(day=1)
        following = (first + datetime.timedelta(days=32)).replace(day=1)
        for month in (first.isoformat()[:7], following.isoformat()[:7]):
            for account, amount in (("4000", 2_500_000), ("5000", 1_600_000), ("6000", 250_000)):
                self.do("finance", "PUT", "/budgets", {"account": account, "month": month, "amount": amount + self.rng.randint(-20, 20) * 10_000})
        self.do("admin", "POST", "/webhooks", {"url": "https://hooks.example.com/stockwell", "secret": f"month-{self.rng.randint(100, 999)}",
                                               "events": ["order.*", "invoice.*"]})
        last = following - datetime.timedelta(days=1)
        rebate = self.do("finance", "POST", "/rebates", {"customer": "C-0003", "period_start": first.isoformat(), "period_end": last.isoformat(),
                                                         "tiers": [{"threshold": 10_000, "rate_bp": 100}, {"threshold": 50_000, "rate_bp": 250}]})
        self.rebate = rebate["id"] if rebate else None
        for customer, every in (("C-0004", 7), (self.rng.choice(["C-0002", "C-0003", "C-0006"]), self.rng.choice([5, 10, 14]))):
            self.do("sales", "POST", "/standing-orders", {"customer": customer, "every_days": every, "start": (self.start + datetime.timedelta(days=2)).isoformat(),
                                                          "auto_confirm": True,
                                                          "lines": [{"sku": sku, "qty": self.rng.randint(2, 8)} for sku in self.rng.sample(PRODUCTS[:8], 2)]})
        status, products = self.call("viewer", "GET", "/products", None, {"limit": "100"})
        self.weights = {row["sku"]: row["weight_g"] for row in (products or {}).get("items", [])}
        self.names = {row["sku"]: row["name"] for row in (products or {}).get("items", [])}
        self.perishable = {row["sku"] for row in (products or {}).get("items", []) if row.get("perishable")}
        status, customers = self.call("viewer", "GET", "/customers", None, {"limit": "100"})
        self.regions = {row["id"]: row["region"] for row in (customers or {}).get("items", [])}
        status, carriers = self.call("viewer", "GET", "/carriers")
        self.carriers = [row for row in (carriers or {}).get("items", []) if row["active"]]
        status, suppliers = self.call("viewer", "GET", "/suppliers", None, {"limit": "100"})
        self.suppliers = {row["id"]: row for row in (suppliers or {}).get("items", [])}

    def trade(self, day: int) -> None:
        rng = self.rng
        if self.restart == ("kill", day):
            self.kill_armed, self.kill_countdown = True, rng.randint(1, 15)
        if self.restart and day == self.restart[1] + 1:
            self.read_again()
        if self.today.weekday() == 0:
            self.call("finance", "GET", "/dunning", None, {"sort": "-level", "limit": "50"})
        self.sell()
        self.fulfil()
        if day % 3 == 0:
            self.buy()
        for purchase_order in self.arriving.pop(day, []):
            self.supplier_invoice(purchase_order)
        if day % 7 == 1:
            work = self.do("warehouse", "POST", "/work-orders", {"sku": "JCE-ORG-06", "batches": rng.choice([1, 2]), "warehouse": "MAIN"})
            if work and self.do("warehouse", "POST", f"/work-orders/{work['id']}/start"):
                self.do("warehouse", "POST", f"/work-orders/{work['id']}/complete", {"good_qty": rng.randint(30, 40) * work.get("batches", 1)})
        if day in (4, 18):
            self.do("sales", "POST", "/quotes", {"customer": rng.choice(["C-0002", "C-0005"]), "lines": [{"sku": "MLK-WHL-12", "qty": rng.choice([12, 24])}]})
            self.do("warehouse", "POST", "/kits/BOX-CRD-50/builds", {"warehouse": "MAIN", "qty": rng.randint(2, 5)})
        if day in (9, 21):
            self.give_back()
        if day == self.integration_day:
            self.integration()
        if day == self.import_day:
            self.import_customers()
        if day == 12:
            count = self.do("warehouse", "POST", "/stock/counts", {"warehouse": "MAIN", "skus": ["FLR-WHT-25", "OIL-OLV-05"]})
            if count:
                self.do("warehouse", "POST", f"/stock/counts/{count['id']}/lines",
                        {"lines": [{"lot": line["lot"], "counted": max(0, line["expected"] - rng.choice([0, 0, 1, 2]))} for line in count["lines"]]})
                self.do("warehouse", "POST", f"/stock/counts/{count['id']}/post")
        if day == 16:
            recall = self.do("warehouse", "POST", "/recalls", {"lot": "LOT-00002", "reason": "Supplier reported contamination"})
            self.recall = recall["id"] if recall else None
        if day == 19 and getattr(self, "recall", None):
            self.do("warehouse", "POST", f"/recalls/{self.recall}/close", {"disposition": rng.choice(["scrap", "release"])})
        if self.today.weekday() == 4:
            self.pay_bills()
            self.bank_statement()
        if self.today.day == calendar.monthrange(self.today.year, self.today.month)[1]:
            self.month_end()
        if self.today.day == 1 and day:
            self.close_month()
        restart = "term" if self.restart == ("term", day) else "kill?" if self.kill_armed else None
        self.kill_armed = False
        status, moved = self.call("admin", "POST", "/clock/advance", {"days": 1}, **({"restart": restart} if restart else {}))
        if isinstance(moved, dict) and moved.get("today"):
            self.today = datetime.date.fromisoformat(moved["today"])

    # ------------------------------------------------------------------ selling

    def sell(self) -> None:
        rng = self.rng
        for _ in range(rng.randint(2, 4)):
            lines = [{"sku": sku, "qty": rng.randint(1, 12)} for sku in rng.sample(PRODUCTS, rng.randint(1, 3))]
            body: dict[str, Any] = {"customer": rng.choice(CUSTOMERS), "lines": lines}
            if rng.random() < 0.2:
                body["notes"] = rng.choice(NOTES)
            order = self.do("sales", "POST", "/orders", body)
            if order and rng.random() < 0.85 and self.do("sales", "POST", f"/orders/{order['id']}/confirm"):
                self.open_orders.append(order["id"])

    def parcels(self, shipment: dict[str, Any]) -> dict[str, Any] | None:
        goods = sum(self.weights.get(line["sku"], 0) * line["qty"] for line in shipment["lines"])
        carrier = next((row for row in self.carriers if self.regions.get(shipment["customer"]) in row["regions"]), None)
        if carrier is None or goods <= 0:
            return None
        limit, parcels = carrier["max_parcel_g"], []
        while goods > 0:
            parcels.append({"weight_g": min(limit, goods + 500)})
            goods -= limit
        return {"carrier": carrier["code"], "parcels": parcels}

    def fulfil(self) -> None:
        rng = self.rng
        for order_id in list(self.open_orders):
            order = ok(*self.call("viewer", "GET", f"/orders/{order_id}"))
            if not order or order.get("status") not in ("confirmed", "partially_shipped"):
                self.open_orders.remove(order_id)
                continue
            if not any(line["allocated"] for line in order["lines"]):
                continue
            shipped = self.do("warehouse", "POST", f"/orders/{order_id}/shipments")
            for shipment in (shipped or {}).get("items", []):
                self.shipments.append(shipment["id"])
                invoice = self.do("finance", "POST", f"/shipments/{shipment['id']}/invoice")
                if invoice and invoice.get("total", 0) > 0:
                    self.invoices.append(invoice)
                    if rng.random() < 0.55 and invoice.get("balance", 0) > 0:
                        self.do("finance", "POST", "/payments", {"customer": invoice["customer"], "amount": invoice["balance"],
                                                                 "method": rng.choice(["bank", "card"]), "invoices": [invoice["id"]]})
                dispatch = self.parcels(shipment) if rng.random() < 0.6 else None
                if dispatch and self.do("warehouse", "POST", f"/shipments/{shipment['id']}/dispatch", dispatch) and rng.random() < 0.3:
                    self.proof_of_delivery(shipment["id"])

    def proof_of_delivery(self, shipment: str) -> None:
        rng = self.rng
        key = rng.choice(self.pool["clip"]) if rng.random() < 0.15 else rng.choice(self.pool["photo"])
        name = f"{rng.choice(FILE_LABELS)} {self.today.isoformat()}.{key.rsplit('.', 1)[1]}" if rng.random() < 0.2 else None
        stored = self.upload("warehouse", key, f"shipment:{shipment}", name)
        if not stored:
            return
        if key.endswith((".mp4", ".mov")):
            self.call("viewer", "GET", f"/files/{stored['id']}/media")
            return
        self.call(rng.choice(["viewer", "sales"]), "GET", f"/files/{stored['id']}/thumbnail", None,
                  rng.choice([{}, {"box": "48"}, {"box": "200"}]))
        if rng.random() < 0.35:
            self.call("viewer", "GET", f"/files/{stored['id']}/image")

    def give_back(self) -> None:
        rng = self.rng
        status, listing = self.call("viewer", "GET", "/invoices", None, {"sort": "-id", "limit": "3"})
        items = (listing or {}).get("items", []) if isinstance(listing, dict) else []
        if not items:
            return
        invoice = rng.choice(items)
        lines = [line for line in invoice.get("lines", []) if line["qty"] - line.get("returned", 0) >= 1]
        if not lines:
            return
        line = rng.choice(lines)
        ret = self.do("sales", "POST", "/returns", {"invoice": invoice["id"], "lines": [{"n": line["n"], "qty": 1,
                                                                                         "reason": rng.choice(["defective", "wrong_item", "changed_mind"])}]})
        if not ret:
            return
        stored = self.upload("warehouse", rng.choice(self.pool["photo"]), f"return:{ret['id']}")
        if stored:
            self.call("viewer", "GET", f"/files/{stored['id']}/thumbnail", None, {"box": "96"})
        if rng.random() < 0.5:
            note = self.upload("warehouse", rng.choice(self.pool["note"]), f"return:{ret['id']}")
            if note:
                self.call("viewer", "GET", f"/files/{note['id']}/media")
        self.do("warehouse", "POST", f"/returns/{ret['id']}/receive")

    # ------------------------------------------------------------------ buying

    def buy(self) -> None:
        rng = self.rng
        supplier = sorted(CATALOGUE)[self.supplier_turn % len(CATALOGUE)]
        self.supplier_turn += 1
        lines = [{"sku": sku, "qty": pack * rng.randint(1, 3)} for sku, pack in rng.sample(CATALOGUE[supplier], rng.randint(1, len(CATALOGUE[supplier])))]
        po = self.do("warehouse", "POST", "/purchase-orders", {"supplier": supplier, "warehouse": WAREHOUSE[supplier], "lines": lines})
        submitted = po and self.do("warehouse", "POST", f"/purchase-orders/{po['id']}/submit")
        if not submitted:
            return
        if submitted.get("status") == "submitted":
            self.do("finance", "POST", f"/purchase-orders/{po['id']}/approve")
        if rng.random() < 0.85:
            receipt = []
            for n, line in enumerate(lines, start=1):
                qty = line["qty"] if rng.random() < 0.8 else max(1, line["qty"] // 2)
                received = {"n": n, "qty": qty, "damaged": rng.choice([0, 0, 0, 1]) if qty > 1 else 0}
                if line["sku"] in self.perishable:
                    received["expiry"] = (self.today + datetime.timedelta(days=rng.randint(8, 40))).isoformat()
                receipt.append(received)
            if self.do("warehouse", "POST", f"/purchase-orders/{po['id']}/receipts", {"lines": receipt}):
                self.arriving.setdefault(self.day_index() + rng.randint(1, 3), []).append(po["id"])

    def day_index(self) -> int:
        return (self.today - self.start).days

    def supplier_invoice(self, purchase_order: str) -> None:
        """The supplier's PDF arrives: attach it to the order, read it, and book it or not as a clerk would."""
        rng = self.rng
        detail = ok(*self.call("finance", "GET", f"/purchase-orders/{purchase_order}"))
        if not detail:
            return
        supplier = self.suppliers.get(detail["supplier"], {"id": detail["supplier"], "name": detail["supplier"]})
        key, invoice, container = self.invoice_file(detail, supplier, self.names, self.today.isoformat())
        if not invoice["lines"]:
            return
        stored = self.upload("finance", key, f"purchase_order:{purchase_order}")
        if not stored:
            return
        path = f"/files/{stored['id']}"
        if rng.random() < 0.3:
            self.call("viewer", "GET", f"{path}/pdf")
        status, reading = self.call("finance", "GET", f"{path}/supplier-invoice")
        if container == "password":
            self.do("finance", "POST", f"{path}/unlock", {"password": invoice["password"]})
            status, reading = self.call("finance", "GET", f"{path}/supplier-invoice")
        if not isinstance(reading, dict) or status != 200:
            return
        codes = {problem["code"] for problem in reading.get("problems", [])}
        if not codes:
            booked = self.do("finance", "POST", f"{path}/supplier-invoice")
        elif codes <= {"arithmetic", "total_differs"}:
            booked = self.do("finance", "POST", f"{path}/supplier-invoice", {"accept_problems": True})
        elif "scanned" in codes or codes & {"no_reference", "no_lines", "unreadable_line", "repeated_product"}:
            # a scan, or a layout the reader cannot follow: the clerk reads the page and types the bill in
            self.call("finance", "GET", f"{path}/pages/1")
            bill = self.do("finance", "POST", "/supplier-bills", {"purchase_order": purchase_order, "reference": invoice["reference"],
                                                                  "lines": [{"n": line["n"], "qty": line["qty"], "unit_cost": line["unit_cost"]}
                                                                            for line in invoice["lines"]]})
            booked = {"bill": bill} if bill else None
        else:
            booked = None  # billed for more than arrived: disputed with the supplier, left unbooked
            self.call("finance", "GET", "/supplier-bills", None, {"purchase_order": purchase_order})
        if booked and isinstance(booked.get("bill"), dict):
            self.bills[booked["bill"]["id"]] = booked["bill"].get("status", "")

    def pay_bills(self) -> None:
        """Fridays: release the bills held for a difference, then pay most of those that are approved."""
        for bill, status in sorted(self.bills.items()):
            if status == "on_hold":
                approved = self.do("finance", "POST", f"/supplier-bills/{bill}/approve")
                status = self.bills[bill] = approved.get("status", status) if approved else status
            if status == "approved" and self.rng.random() < 0.7 and self.do("finance", "POST", f"/supplier-bills/{bill}/pay", {"amount": None}):
                del self.bills[bill]

    def bank_statement(self) -> None:
        """The bank's statement since the last one, opening where the last closed: the bank's charges are booked first, so
        every line of the statement has its entry in the book, is matched, and the statement is reconciled."""
        charges = self.rng.choice([250, 350, 900])
        self.do("finance", "POST", "/ledger/journal", {"memo": f"Bank charges to {self.today.isoformat()}",
                                                       "lines": [{"account": "6000", "debit": charges}, {"account": "1000", "credit": charges}]})
        book = ok(*self.call("finance", "GET", "/bank/book"))
        items = [item for item in (book or {}).get("items", []) if item.get("line") is None and item.get("amount") and item["date"] > self.bank_through]
        if not items:
            return
        lines = [{"date": item["date"], "amount": item["amount"], "reference": (item.get("reference") or "")[:40], "description": item["memo"][:60]}
                 for item in items]
        closing = self.bank_closing + sum(line["amount"] for line in lines)
        statement = self.do("finance", "POST", "/bank/statements", {"opening": self.bank_closing, "closing": closing, "lines": lines})
        if statement:
            self.bank_through, self.bank_closing = self.today.isoformat(), closing
            self.do("finance", "POST", f"/bank/statements/{statement['id']}/match")
            self.do("finance", "POST", f"/bank/statements/{statement['id']}/reconcile")

    # ------------------------------------------------------------------ month end

    def month_end(self) -> None:
        """The month's last day: the bank reconciled, foreign balances revalued, receivables aged and chased."""
        rng = self.rng
        last = self.today.isoformat()
        self.bank_statement()
        self.do("finance", "POST", "/fx/revaluations")
        self.call("finance", "GET", "/reports/aging", None, {"as_of": last})
        for customer in rng.sample(CUSTOMERS, 3):
            self.call("finance", "GET", f"/customers/{customer}/statement")
        self.call("finance", "GET", f"/customers/{rng.choice(CUSTOMERS)}/statement/document")
        self.call("finance", "GET", "/reports/dunning")
        listing = ok(*self.call("finance", "GET", "/invoices", None, {"status": "open", "sort": "due", "limit": "20"})) or {}
        unpaid = [invoice for invoice in listing.get("items", []) if invoice.get("balance", 0) > 0 and invoice["customer"] != "C-0001"]
        for invoice in rng.sample(unpaid, min(len(unpaid), rng.randint(2, 5))):
            self.do("finance", "POST", "/payments", {"customer": invoice["customer"], "amount": invoice["balance"], "method": "bank",
                                                     "reference": f"REM-{rng.randint(1000, 9999)}", "invoices": [invoice["id"]]})

    def close_month(self) -> None:
        """The first day of the next month: commissions and the month's rebate settled, stock reordered and planned, the
        month's reports read and its books closed."""
        rng = self.rng
        last = (self.today - datetime.timedelta(days=1)).isoformat()
        first = last[:8] + "01"
        reps = ok(*self.call("finance", "GET", "/reps")) or {}
        for rep in sorted({row["rep"] for row in reps.get("items", []) if row.get("rep")})[:3]:
            self.do("finance", "POST", "/commissions/payouts", {"rep": rep, "through": last})
        if getattr(self, "rebate", None):
            self.do("finance", "POST", f"/rebates/{self.rebate}/settle")
        reorder = ok(*self.call("warehouse", "GET", "/reports/reorder")) or {}
        wanted: dict[str, list[dict[str, Any]]] = {}
        for row in reorder.get("items", [])[:6]:
            suggestion = row.get("suggestion") or {}
            if suggestion.get("supplier") and suggestion.get("qty", 0) > 0:
                wanted.setdefault(suggestion["supplier"], []).append({"sku": row["sku"], "qty": suggestion["qty"]})
        for supplier, lines in sorted(wanted.items()):
            po = self.do("warehouse", "POST", "/purchase-orders", {"supplier": supplier, "warehouse": WAREHOUSE.get(supplier, "MAIN"), "lines": lines,
                                                                   "notes": rng.choice(["Month-end reorder", "Nachbestellung Monatsende",
                                                                                        "Réassort de fin de mois", "Zamówienie uzupełniające"])})
            if po:
                self.do("warehouse", "POST", f"/purchase-orders/{po['id']}/submit")
        plan = self.do("warehouse", "POST", "/planning/runs", {"weeks": rng.choice([4, 6])})
        if plan and plan.get("orders"):
            chosen = [order["id"] for order in plan["orders"][: rng.randint(1, 3)] if order.get("status") == "planned"]
            if chosen:
                self.do("warehouse", "POST", f"/planning/runs/{plan['id']}/firm", {"orders": chosen})
        self.call("finance", "GET", "/reports/budget", None, {"month": last[:7]})
        self.call("finance", "GET", "/reports/income-statement", None, {"from": first, "to": last})
        self.call("finance", "GET", "/reports/trial-balance", None, {"as_of": last})
        self.do("finance", "POST", "/ledger/periods/close", {"through": last})
        self.call("finance", "GET", "/ledger/periods")

    def final_reads(self) -> None:
        for role, path, query in (("viewer", "/stock/moves", {"sort": "-seq", "limit": "100"}), ("viewer", "/ledger/journal", {"sort": "-id", "limit": "50"}),
                                  ("viewer", "/reports/trial-balance", {}), ("viewer", "/reports/aging", {}), ("viewer", "/stock", {}),
                                  ("admin", "/admin/integrity", {})):
            self.call(role, "GET", path, None, query)

    # ------------------------------------------------------------------ files

    def upload(self, role: str, key: str, attach_to: str | None, name: str | None = None) -> Any:
        """Upload a pool file as the raw body, under its own name or the one the user typed."""
        name = name or key.rsplit("/", 1)[-1]
        query = {"name": name, **({"attach_to": attach_to} if attach_to else {})}
        extra: dict[str, Any] = {}
        self.arm(extra)
        stored = ok(*self.call(role, "POST", "/files/upload", None, query, file=key, content_type=content_type(key), **extra))
        if stored:
            self.stored.append((stored["id"], stored.get("type", "")))
        return stored

    def read_again(self) -> None:
        """The day after a planned restart: files uploaded before it are opened again, their facts and their bytes."""
        rng = self.rng
        for file_id, kind in rng.sample(self.stored, min(3, len(self.stored))):
            self.call("viewer", "GET", f"/files/{file_id}")
            if kind == "pdf":
                self.call("finance", "GET", f"/files/{file_id}/supplier-invoice")
            elif kind in ("jpeg", "png", "gif"):
                self.call("viewer", "GET", f"/files/{file_id}/thumbnail", None, {"box": rng.choice(["64", "160"])})
            else:
                self.call("viewer", "GET", f"/files/{file_id}/media")
            self.call("viewer", "GET", f"/files/{file_id}/content")

    def integration(self) -> None:
        """A driver's app sends a photo as base64 inside JSON: one under the limit for a file sent that way, one over it, and
        then a body over the limit for any JSON body (sent as that many bytes; the server refuses it from its length)."""
        rng = self.rng
        fits, too_big = self.pool["sized"]
        target = {"attach_to": f"shipment:{self.shipments[-1]}"} if self.shipments else {}
        stored = ok(*self.call("warehouse", "POST", "/files", {"name": fits.rsplit("/", 1)[1], **target}, insert=("content", fits, "base64"),
                               content_type="application/json"))
        if stored:
            self.stored.append((stored["id"], stored.get("type", "")))
            self.call("viewer", "GET", f"/files/{stored['id']}/thumbnail", None, {"box": "96"})
        self.call("warehouse", "POST", "/files", {"name": too_big.rsplit("/", 1)[1], **target}, insert=("content", too_big, "base64"),
                  content_type="application/json")
        self.call("warehouse", "POST", "/files", size=MAX_JSON_BODY + rng.choice([1, 4096, 250_000]), content_type="application/json")

    def import_customers(self) -> None:
        """A CRM's customer list: a dry run finds three mistakes, the list put right goes in, and the office tries the whole
        list (over the row limit) or a full export with its history (over the size limit)."""
        rng = self.rng
        first, fixed, everyone, export = self.pool["import"]
        self.call("admin", "POST", "/imports/customers", {"dry_run": True}, insert=("csv", first, "text"), content_type="application/json")
        self.call("admin", "POST", "/imports/customers", {"dry_run": False}, insert=("csv", fixed, "text"), content_type="application/json")
        self.call("admin", "POST", "/imports/customers", {"dry_run": True}, insert=("csv", rng.choice([everyone, export]), "text"),
                  content_type="application/json")
        self.call("viewer", "GET", "/customers", None, {"sort": "-id", "limit": "25"})
