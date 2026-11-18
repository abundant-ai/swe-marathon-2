"""Record the scenarios that need the reference running as a server: months of trading, one unit per trading day,
the web client's own screens after each month, and planned restarts in the middle of some months.

usage: record_live.py --runs N --seed S --media DIR --out FILE [--term K] [--kill K] [--screens M] [--days A B]

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

Needs a Python with PyMuPDF, Pillow and numpy, ffmpeg, and node with the frontend's packages (reference.py
installs them in the checkout).
"""

from __future__ import annotations

import argparse
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
from verifier.replay import NOT_JSON, TOO_LARGE, encode_query, exchange  # noqa: E402

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
               "STOCKWELL_AUTH_MODE": "proxy", "STOCKWELL_CREATE_SCHEMA": "true", "STOCKWELL_DATABASE_URL": f"sqlite:///{self.data}/stockwell.db",
               "STOCKWELL_DATA_DIR": str(self.data), "STOCKWELL_LOG_LEVEL": "WARNING", "STOCKWELL_ACCESS_LOG": "false",
               "STOCKWELL_REQUEST_LOG": "false", "STOCKWELL_METRICS_ENABLED": "false"}
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

    def begin(self, label: str, theme: str = "trading") -> None:
        self.units.append({"theme": theme, "label": label})

    def reconnect(self) -> None:
        self.connection.close()
        self.connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=120)

    def call(self, role: str, method: str, path: str, body: Any = None, query: dict[str, Any] | None = None, file: str | None = None,
             content_type: str | None = None, restart: str | None = None, scoped: bool = True,
             headers: dict[str, str] | None = None) -> tuple[int, Any]:
        """Send one request as `role` (or with `headers`), record it with its answer in the current unit, and return the answer."""
        query = {key: str(value) for key, value in (query or {}).items()}
        sent = dict(headers) if headers is not None else {"x-user": ROLES[role]}
        if content_type:
            sent["content-type"] = content_type
        step: dict[str, Any] = {"method": method, "path": path, "query": query, "headers": sent}
        raw = None
        if file is not None:
            step["body_file"] = file
            if file not in self.files:
                self.files[file] = (self.media / file).read_bytes()
            raw = self.files[file]
        else:
            step["body"] = body
        if not scoped:
            step["scoped"] = False
        if "{ws}" in json.dumps(step):
            raise RuntimeError(f"a request names {{ws}}: {step}")
        target = (path if not scoped else f"/api/ws/{self.workspace}{path}") + encode_query(query)
        status, answer = exchange(self.connection, method, target, sent, body if file is None else None, raw)
        if answer is NOT_JSON or answer is TOO_LARGE or status >= 500:
            raise RuntimeError(f"{self.id}: {method} {path} answered {status} {str(answer)[:200]}")
        step["status"] = status
        step["json"] = json.loads(json.dumps(answer).replace(self.workspace, "{ws}"))
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
    """The supplier-invoice factory for one run: the PDF for a purchase order, made once under DIR/trading/invoices."""
    def make(detail: dict[str, Any], supplier: dict[str, Any], names: dict[str, str], date: str) -> tuple[str, dict[str, Any], str]:
        rng = random.Random(f"invoice:{seed}:{run_id}:{detail['id']}")
        container, mistake = rng.choice(CONTAINERS), rng.choice(MISTAKES)
        invoice = trading_media.make_invoice(rng, detail, supplier, names, date, mistake)
        digest = hashlib.sha256(json.dumps([invoice, container], sort_keys=True).encode()).hexdigest()[:10]
        key = f"trading/invoices/{run_id}/{detail['id']}-{digest}.pdf"
        path = media / key
        if invoice["lines"] and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(trading_media.invoice_pdf(invoice, container, random.Random(f"pdf:{seed}:{run_id}:{detail['id']}")))
        return key, invoice, container
    return make


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

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--media", type=Path, required=True, help="the private media folder: the run's files go under trading/")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--term", type=int, default=0, help="runs with a SIGTERM restart at the end of a day")
    parser.add_argument("--kill", type=int, default=0, help="runs with a SIGKILL restart straight after an answered write")
    parser.add_argument("--screens", type=int, default=0, help="client screens opened after each run")
    parser.add_argument("--days", type=int, nargs=2, default=(30, 35), help="the shortest and longest run in days, from 2031-03-03: 30 reach April 1")
    args = parser.parse_args()
    reference = checkout()
    python = os.environ.get("STOCKWELL_PYTHON") or str(reference / "backend" / ".venv" / "bin" / "python")
    scratch = Path(os.environ.get("TMPDIR", "/tmp")) / f"stockwell-live-{os.getpid()}"
    shutil.rmtree(scratch, ignore_errors=True)
    server = Reference(reference / "backend" / "src", python, scratch / "data")
    server.start()
    started = time.time()
    try:
        pool = {kind: [f"trading/{key}" for key in keys] for kind, keys in trading_media.pool(args.seed, args.media / "trading" / "pool").items()}
        order = random.Random(f"order:{args.seed}")
        plans = ["term"] * args.term + ["kill"] * args.kill + [None] * (args.runs - args.term - args.kill)
        order.shuffle(plans)
        runs: list[Run] = []
        for number in range(1, args.runs + 1):
            rng = random.Random(f"trading:{args.seed}:{number}")
            days = rng.randint(*args.days)
            how = plans[number - 1]
            restart = (how, rng.randint(5, days - 4)) if how else None
            run = Run(server, args.media, f"T{number:05d}")
            month = trading.Month(run.call, run.begin, invoice_maker(args.media, args.seed, run.id), pool, rng, days, restart)
            month.run()
            run.days, run.restart = days, how
            runs.append(run)
            print(json.dumps({"run": run.id, "days": days, "restart": how, "steps": len(run.steps), "seconds": round(time.time() - started)}),
                  file=sys.stderr)
        if args.screens:
            eligible = list(SCREENS)
            random.Random(f"screens:{args.seed}").shuffle(eligible)
            plan, wanted = [], {}
            for index, run in enumerate(runs):
                picks = [eligible[(index * args.screens + k) % len(eligible)] for k in range(args.screens)]
                wanted[run.id] = screen_urls(server, run.workspace, picks)
                plan.append({"ws": run.workspace, "urls": wanted[run.id]})
            found = capture(server, reference / "frontend", plan, scratch)
            for run in runs:
                for url in wanted[run.id]:
                    requests = screen_requests(found.get((run.workspace, url), []), run.workspace)
                    if requests:
                        record_screens(run, url, requests)
        scenarios = [run.scenario(days=run.days, restart=run.restart) for run in runs]
    finally:
        server.stop("kill")
        shutil.rmtree(scratch, ignore_errors=True)
    # keep under DIR/trading only the files these months upload, so nothing unused is packaged with them
    used = {step["body_file"] for scenario in scenarios for step in scenario["steps"] if "body_file" in step}
    for path in sorted((args.media / "trading").rglob("*"), reverse=True):
        if path.is_file() and path.relative_to(args.media).as_posix() not in used:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    corpus = {"scenarios": scenarios, "recorded_with": {"runs": args.runs, "term": args.term, "kill": args.kill, "screens": args.screens,
                                                        "days": list(args.days)}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(corpus, sort_keys=True, separators=(",", ":")) + "\n")
    units = sum(len(s["units"]) for s in scenarios)
    screens = sum(1 for s in scenarios for unit in s["units"] if unit["theme"] == "screens")
    print(json.dumps({"runs": len(scenarios), "units": units, "days": units - screens, "screens": screens,
                      "requests": sum(len(s["steps"]) for s in scenarios), "seconds": round(time.time() - started)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
