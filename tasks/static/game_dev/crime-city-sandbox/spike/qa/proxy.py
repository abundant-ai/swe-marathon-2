#!/usr/bin/env python3
"""Network impairment proxy (design 3.6): one listening port per client, seeded impairment.

UDP (ENet): drop, delay, jitter, duplicate, reorder datagrams; Gilbert-Elliott burst loss.
TCP (WebSocket): latency and jitter with order kept; a "lost" segment stalls the stream for
200 ms * 2^k (k = consecutive losses), like a retransmission timeout.
A partition drops (UDP) or holds (TCP) everything for one client for a while.

usage: proxy.py CONFIG.json      (runs until duration_s, then writes stats_path)
config: {"transport": "udp"|"tcp", "server_port": P, "seed": 1, "duration_s": 60,
         "clients": [{"listen": P1, "profile": "P2"}, ...],
         "schedule": [{"at_s": 20, "client": 0, "partition_s": 3}, {"at_s": 30, "client": 1, "profile": "P3"}],
         "stats_path": "..."}
"""

import asyncio
import json
import random
import sys
import time
from pathlib import Path

PROFILES = {
    "P0": {
        "rtt_ms": 0,
        "jitter_ms": 0,
        "loss_up": 0.0,
        "loss_down": 0.0,
        "dup": 0.0,
        "reorder": 0.0,
        "burst": 0,
    },
    "P1": {
        "rtt_ms": 50,
        "jitter_ms": 10,
        "loss_up": 0.01,
        "loss_down": 0.01,
        "dup": 0.0,
        "reorder": 0.0,
        "burst": 0,
    },
    "P2": {
        "rtt_ms": 120,
        "jitter_ms": 30,
        "loss_up": 0.05,
        "loss_down": 0.05,
        "dup": 0.01,
        "reorder": 0.02,
        "burst": 0,
    },
    "P3": {
        "rtt_ms": 250,
        "jitter_ms": 60,
        "loss_up": 0.08,
        "loss_down": 0.02,
        "dup": 0.0,
        "reorder": 0.0,
        "burst": 4,
    },
}


class Impair:
    """One direction of one client."""

    def __init__(self, rng, profile, direction):
        self.rng = rng
        self.direction = direction
        self.set_profile(profile)
        self.bad = False
        self.partition_until = 0.0
        self.stats = {
            "in": 0,
            "out": 0,
            "dropped": 0,
            "dup": 0,
            "held_partition": 0,
            "stall_ms": 0.0,
            "bytes_in": 0,
        }

    def set_profile(self, name):
        self.name = name
        self.p = PROFILES[name]

    def lost(self):
        loss = self.p["loss_up"] if self.direction == "up" else self.p["loss_down"]
        if loss <= 0:
            return False
        if self.p["burst"]:
            # Gilbert-Elliott: bad state drops everything, mean burst length p["burst"]
            p_bg = 1.0 / self.p["burst"]
            p_gb = loss * p_bg / (1.0 - loss)
            if self.bad:
                self.bad = self.rng.random() >= p_bg
            else:
                self.bad = self.rng.random() < p_gb
            return self.bad
        return self.rng.random() < loss

    def delay(self):
        base = self.p["rtt_ms"] / 2.0
        j = self.p["jitter_ms"] / 2.0
        d = base + self.rng.uniform(-j, j)
        if self.p["reorder"] and self.rng.random() < self.p["reorder"]:
            d += self.p["jitter_ms"] + 5.0
        return max(0.0, d) / 1000.0

    def partitioned(self):
        return time.monotonic() < self.partition_until


class UdpClient:
    def __init__(self, proxy, idx, listen, profile):
        self.proxy, self.idx, self.listen = proxy, idx, listen
        rng = random.Random(f"{proxy.seed}-{idx}")
        self.up = Impair(random.Random(rng.random()), profile, "up")
        self.down = Impair(random.Random(rng.random()), profile, "down")
        self.client_addr = None
        self.front = None  # transport facing the client
        self.back = None  # transport facing the server

    async def start(self):
        loop = asyncio.get_running_loop()
        me = self

        class Front(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                me.client_addr = addr
                me.forward(data, me.up, lambda d: me.back.sendto(d))

        class Back(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                if me.client_addr is not None:
                    me.forward(
                        data, me.down, lambda d: me.front.sendto(d, me.client_addr)
                    )

        self.front, _ = await loop.create_datagram_endpoint(
            Front, local_addr=("127.0.0.1", self.listen)
        )
        self.back, _ = await loop.create_datagram_endpoint(
            Back, remote_addr=("127.0.0.1", self.proxy.server_port)
        )

    def forward(self, data, imp, send):
        imp.stats["in"] += 1
        imp.stats["bytes_in"] += len(data)
        if imp.partitioned():
            imp.stats["held_partition"] += 1
            return
        if imp.lost():
            imp.stats["dropped"] += 1
            return
        loop = asyncio.get_running_loop()
        copies = 1
        if imp.p["dup"] and imp.rng.random() < imp.p["dup"]:
            copies = 2
            imp.stats["dup"] += 1
        for _ in range(copies):
            d = imp.delay()
            imp.stats["out"] += 1
            if d <= 0:
                send(data)
            else:
                loop.call_later(d, send, data)


class TcpClient:
    def __init__(self, proxy, idx, listen, profile):
        self.proxy, self.idx, self.listen = proxy, idx, listen
        rng = random.Random(f"{proxy.seed}-{idx}")
        self.up = Impair(random.Random(rng.random()), profile, "up")
        self.down = Impair(random.Random(rng.random()), profile, "down")

    async def start(self):
        await asyncio.start_server(self.handle, "127.0.0.1", self.listen)

    async def handle(self, creader, cwriter):
        sreader, swriter = await asyncio.open_connection(
            "127.0.0.1", self.proxy.server_port
        )
        await asyncio.gather(
            self.pump(creader, swriter, self.up), self.pump(sreader, cwriter, self.down)
        )

    async def pump(self, reader, writer, imp):
        queue = asyncio.Queue()
        state = {"last": 0.0, "k": 0}

        async def deliver():
            while True:
                due, data = await queue.get()
                if data is None:
                    writer.close()
                    return
                while imp.partitioned():
                    await asyncio.sleep(0.01)
                wait = due - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                writer.write(data)
                await writer.drain()
                imp.stats["out"] += 1

        task = asyncio.create_task(deliver())
        while True:
            data = await reader.read(65536)
            if not data:
                await queue.put((0.0, None))
                break
            imp.stats["in"] += 1
            imp.stats["bytes_in"] += len(data)
            due = time.monotonic() + imp.delay()
            if imp.lost():
                state["k"] += 1
                stall = 0.2 * (2 ** (state["k"] - 1))
                imp.stats["dropped"] += 1
                imp.stats["stall_ms"] += stall * 1000.0
                due += stall
            else:
                state["k"] = 0
            due = max(due, state["last"])  # TCP keeps order
            state["last"] = due
            await queue.put((due, data))
        await task


class Proxy:
    def __init__(self, cfg):
        self.cfg = cfg
        self.seed = cfg.get("seed", 1)
        self.server_port = cfg["server_port"]
        kind = UdpClient if cfg.get("transport", "udp") == "udp" else TcpClient
        self.clients = [
            kind(self, i, c["listen"], c.get("profile", "P0"))
            for i, c in enumerate(cfg["clients"])
        ]
        self.events = []

    async def run(self):
        for c in self.clients:
            await c.start()
        t0 = time.monotonic()
        print(
            json.dumps(
                {
                    "proxy": "ready",
                    "transport": self.cfg.get("transport", "udp"),
                    "ports": [c.listen for c in self.clients],
                }
            ),
            flush=True,
        )
        for ev in sorted(self.cfg.get("schedule", []), key=lambda e: e["at_s"]):
            await asyncio.sleep(max(0.0, t0 + ev["at_s"] - time.monotonic()))
            c = self.clients[ev["client"]]
            if "partition_s" in ev:
                until = time.monotonic() + ev["partition_s"]
                c.up.partition_until = until
                c.down.partition_until = until
            if "profile" in ev:
                c.up.set_profile(ev["profile"])
                c.down.set_profile(ev["profile"])
            self.events.append(
                {"t": round(time.monotonic() - t0, 3), "unix": time.time(), **ev}
            )
        await asyncio.sleep(
            max(0.0, t0 + self.cfg.get("duration_s", 60) - time.monotonic())
        )
        stats = {
            "transport": self.cfg.get("transport", "udp"),
            "events": self.events,
            "clients": [
                {
                    "listen": c.listen,
                    "profile": c.up.name,
                    "up": c.up.stats,
                    "down": c.down.stats,
                }
                for c in self.clients
            ],
        }
        if self.cfg.get("stats_path"):
            await asyncio.to_thread(
                Path(self.cfg["stats_path"]).write_text, json.dumps(stats, indent=1)
            )
        print(json.dumps({"proxy": "done"}), flush=True)


if __name__ == "__main__":
    asyncio.run(Proxy(json.loads(Path(sys.argv[1]).read_text())).run())
