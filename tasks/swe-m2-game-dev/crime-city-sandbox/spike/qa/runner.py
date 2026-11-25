#!/usr/bin/env python3
"""Run one scenario instance (template + seed) headless through the probe.

usage: runner.py SCENARIO.yaml --seed N --game PREPARED_GAME_DIR [--out DIR] [--arg k=v ...]
"""
import argparse
import gzip
import hashlib
import json
import math
import os
import random
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asserts  # noqa: E402
import bots  # noqa: E402
from harness import Session, ProbeError, memgate  # noqa: E402
from plan_geom import PlanGeom  # noqa: E402

TICK_HZ = 60


def expand_params(spec, seed, plan):
    rng = random.Random(seed)
    P = {"seed": seed}
    for name, s in (spec or {}).items():
        s = substitute(s, P)
        if not isinstance(s, dict):
            P[name] = s
        elif "choice" in s:
            P[name] = rng.choice(s["choice"])
        elif "uniform" in s:
            P[name] = rng.uniform(*s["uniform"])
        elif "randint" in s:
            P[name] = rng.randint(*s["randint"])
        elif "bernoulli" in s:
            P[name] = rng.random() < float(s["bernoulli"])
        elif s.get("pick") == "intersection":
            w = s.get("where", {})
            ids = [j["id"] for j in plan.junctions.values()
                   if j["signalised"] == w.get("signalised", j["signalised"])
                   and len(j["approaches"]) >= w.get("min_approaches", 0)]
            P[name] = rng.choice(sorted(ids))
        elif s.get("pick") == "approach_index":
            P[name] = rng.randrange(len(plan.junctions[s["of"]]["approaches"]))
        elif "const" in s:
            P[name] = s["const"]
        else:
            P[name] = s
    return P


def substitute(x, P):
    if isinstance(x, str) and x.startswith("$") and x[1:] in P:
        return P[x[1:]]
    if isinstance(x, list):
        return [substitute(v, P) for v in x]
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            out[k] = substitute(v, P)
        return out
    return x


class Run:
    def __init__(self, scenario, seed, game_dir, out_dir, extra_args=(), plan_path=None, save_trace=True,
                 log_path=None):
        self.sc = scenario
        self.seed = seed
        self.plan = PlanGeom(plan_path or os.path.join(game_dir, "design/plan/downtown_block.json"))
        self.P = expand_params(scenario.get("params"), seed, self.plan)
        self.frames = []
        self.marks = {}
        self.facts = {}
        self.held = {}
        self.observe = {"census": True, "state": True}
        self.rate_ticks = 6
        self.watches = []
        self.pending_queries = []
        self.out_dir = out_dir
        self.save_trace = save_trace
        args = ["--role=solo", f"--seed={seed}"] + list(extra_args) + list(scenario.get("game_args", []))
        self.t_wall0 = time.time()
        self.s = Session(game_dir, args, log_path=log_path)
        self.frames.append(self.s.frame)

    # ---------------------------------------------------------------- plumbing
    def _inputs(self, actions):
        out = []
        for a, v in actions.items():
            v = round(float(v), 4)
            if self.held.get(a, 0.0) != v:
                out.append([0, a, v])
                self.held[a] = v
        return out

    def advance(self, ticks, actions=None, dev=(), extra_observe=None):
        obs = dict(self.observe)
        if extra_observe:
            obs.update(extra_observe)
        if "bones_player" in obs:
            pid = self.player_id()
            obs["bones"] = {"ids": [pid], "names": obs["bones_player"]}
        q = self.pending_queries
        self.pending_queries = []
        fr = self.s.step(ticks, self._inputs(actions or {}), dev, obs, q)
        self.frames.append(fr)
        if "q" in fr:
            for k, v in fr["q"].items():
                self.facts.setdefault("queries", {})[k] = v
        self._run_watches(fr)
        return fr

    def player_id(self):
        for e in self.frames[-1].get("census", []):
            if e["k"] == "player":
                return e["id"]
        return None

    def _run_watches(self, fr):
        for w in self.watches:
            if w.get("done"):
                continue
            if w["kind"] == "stop_line":
                pl = bots.player_of(fr)
                car = bots.car_of(fr)
                if car is None:
                    continue
                s, lat = self.plan.stop_line_side(w["approach"], car["p"][0], car["p"][2])
                prev = w.get("prev")
                w["prev"] = s
                if prev is not None and prev < 0 <= s and -0.5 <= lat <= self.plan.approaches[w["approach"]]["half_w"] + 0.5:
                    w["done"] = True
                    self.marks[w["mark"]] = fr["t"]
                    # witness line of sight right away (next observation)
                    for e in fr.get("census", []):
                        if e["k"] == "npc" and e["f"] == "police":
                            self.pending_queries.append({"id": f"los_{e['id']}", "type": "los", "a": e["id"],
                                                         "b": car["id"], "a_up": 1.65, "b_up": 0.8})

    # ---------------------------------------------------------------- steps
    def run(self):
        P = self.P
        setup = substitute(self.sc.get("setup", []), P)
        dev = []
        for item in setup:
            item = dict(item)
            when = item.pop("when", True)
            if not when:
                continue
            (cmd, args), = item.items()
            dev.append([cmd, args or {}])
        fr = self.advance(1, {}, dev)
        self.facts["setup_results"] = fr.get("dev", [])
        self.marks["setup_end"] = fr["t"]
        for w in substitute(self.sc.get("watches", []), P):
            w = dict(w)
            if w["kind"] == "stop_line":
                w["approach"] = self.plan.junctions[w["junction"]]["approaches"][int(w["approach_index"])]["id"]
            self.watches.append(w)
        for step in substitute(self.sc.get("script", []), P):
            (kind, arg), = step.items()
            self.do(kind, arg)
        return self.finish()

    def do(self, kind, a):
        if kind == "observe":
            a = dict(a)
            self.rate_ticks = max(1, int(round(TICK_HZ / float(a.pop("rate_hz", 10)))))
            self.observe.update(a)
        elif kind == "mark":
            self.marks[a] = self.frames[-1]["t"]
        elif kind == "dev":
            fr = self.advance(1, {}, [[c, args] for c, args in a])
            self.facts.setdefault("dev_results", []).append(fr.get("dev", []))
        elif kind == "wait_s":
            n = int(round(float(a) * TICK_HZ))
            while n > 0:
                k = min(n, self.rate_ticks)
                self.advance(k)
                n -= k
        elif kind == "wait_until":
            self._wait_until(a)
        elif kind == "query":
            self.pending_queries.extend(a)
            self.advance(1)
        elif kind == "plan_probe":
            self._plan_probe(a or {})
        elif kind == "same_start":
            self._same_start(a or {})
        elif kind.startswith("bot."):
            self._bot(kind[4:], a)
        else:
            raise ValueError(f"unknown step {kind}")

    def _plan_probe(self, a):
        """Ray probes against the plan: lane centrelines, sidewalks, parcel roofs, POIs."""
        step = float(a.get("step_m", 10.0))
        cl = self.plan.centreline_points(step)
        sw = self.plan.sidewalk_ring_points(step)
        pc = self.plan.parcel_centres()
        pois = [(p["p"][0], p["p"][2], p["p"][1], p["id"]) for p in self.plan.pois.values()]
        self.pending_queries += [
            {"id": "centrelines", "type": "down", "points": [[x, z] for x, z, _, _ in cl], "y0": 80, "y1": -5},
            {"id": "sidewalks", "type": "down", "points": [[x, z] for x, z, _, _ in sw], "y0": 80, "y1": -5},
            {"id": "parcels", "type": "down", "points": [[x, z] for x, z, _, _ in pc], "y0": 120, "y1": -5},
            {"id": "pois", "type": "down", "points": [[x, z] for x, z, _, _ in pois], "y0": 0.6, "y1": -5},
        ]
        self.facts["plan_expect"] = {"centrelines": [[e, lid] for _, _, e, lid in cl],
                                     "sidewalks": [[e, sid] for _, _, e, sid in sw],
                                     "parcels": [[top, p["id"], p["zoning"], p["height_range_m"], p["base_m"]] for _, _, top, p in pc],
                                     "pois": [[e, pid] for _, _, e, pid in pois]}
        self.advance(1)

    def _same_start(self, a):
        """world.reset twice with the same seed, once with another: compare the tick-0 census."""
        def snap(seed):
            fr = self.advance(1, {}, [["world.reset", {"seed": seed, "density": a.get("density", 1.0)}]])
            return sorted((e["id"], e["k"], e["a"], tuple(round(x, 4) for x in e["p"]))
                          for e in fr["census"] if e["k"] in ("npc", "vehicle", "player"))
        s1 = snap(self.seed)
        self.advance(30)
        s2 = snap(self.seed)
        s3 = snap(self.seed + 1)
        diff = sum(1 for x, y in zip(s1, s2) if x != y) + abs(len(s1) - len(s2))
        self.facts["same_start"] = {"n": len(s1), "same_seed_diffs": diff, "other_seed_same": s1 == s3,
                                    "reset_ms": [d["res"].get("ms") for d in self.frames[-1].get("dev", [])]}

    def _wait_until(self, a):
        max_t = self.frames[-1]["t"] + float(a.get("max_s", 60)) * TICK_HZ
        prev_state = None
        while self.frames[-1]["t"] < max_t:
            fr = self.advance(min(self.rate_ticks, 3))
            if "signal" in a:
                j, k = a["signal"]
                apid = self.plan.junctions[j]["approaches"][int(k)]["id"]
                st = None
                for e in fr.get("census", []):
                    if e["k"] == "signal" and e.get("st") and apid in e["st"]:
                        st = e["st"][apid]
                if "becomes" in a and prev_state is not None and prev_state != a["becomes"] and st == a["becomes"]:
                    self.marks[a.get("mark", "until")] = fr["t"]
                    return True
                if "is" in a and st == a["is"]:
                    return True
                prev_state = st
            if "wanted_at_least" in a:
                if int((fr.get("state") or {}).get("wanted", 0)) >= int(a["wanted_at_least"]):
                    return True
        self.facts.setdefault("timeouts", []).append(a)
        return False

    def _bot(self, name, a):
        control = int(a.get("control_ticks", 3))
        if name == "drive_through":
            j = self.plan.junctions[a["junction"]]
            apid = j["approaches"][int(a["approach_index"])]["id"]
            ap = self.plan.approaches[apid]
            lane = None
            for ln in self.plan.lanes.values():
                if ln["approach"] == apid and ln["id"].endswith(str(a.get("lane_index", 1))):
                    lane = ln
            bot = bots.DriveLine(lane["p0"], ap["t"], lane["length"] + 2 * j["stop_line_m"] + float(a.get("beyond_m", 90)),
                                 float(a.get("speed_kmh", 40)) / 3.6, stop=True, facts=self.facts, name="drive")
        elif name == "brake_test":
            h = math.radians(float(a.get("heading_deg", 90)))
            bot = bots.BrakeTest((math.sin(h), -math.cos(h)), float(a.get("v_kmh", 60)) / 3.6, self.facts,
                                 a.get("prefix", "dry"))
            control = 1
        elif name == "turn_circle":
            bot = bots.TurnCircle(float(a.get("speed_kmh", 8)) / 3.6, float(a.get("s", 14)), self.facts)
        elif name == "top_speed":
            h = math.radians(float(a.get("heading_deg", 90)))
            bot = bots.TopSpeed((math.sin(h), -math.cos(h)), float(a.get("max_s", 50)), self.facts)
            control = 6
        elif name == "walk":
            # compass heading -> camera yaw (the game's camera yaw grows to the left)
            bot = bots.Walk(-math.radians(float(a.get("heading_deg", 0))), a.get("gait", "walk"), float(a.get("s", 5)))
            control = int(a.get("control_ticks", 2))
        else:
            raise ValueError(f"unknown bot {name}")
        max_t = self.frames[-1]["t"] + float(a.get("max_s", 120)) * TICK_HZ
        mark = a.get("mark")
        if mark:
            self.marks[mark + "_start"] = self.frames[-1]["t"]
        done = False
        while not done and self.frames[-1]["t"] < max_t:
            act, done = bot(self.frames[-1])
            self.advance(control, act)
        if mark:
            self.marks[mark + "_end"] = self.frames[-1]["t"]
        # release what the bot held
        self.advance(1, {k: 0.0 for k in self.held})

    # ---------------------------------------------------------------- end
    def finish(self):
        wall = time.time() - self.t_wall0
        rc = self.s.close()
        # entity ids are unique within one world: the trace starts at the setup's world.reset
        t0 = self.marks.get("setup_end", 0)
        trace = asserts.Trace([f for f in self.frames if f["t"] >= t0], self.plan, self.P, self.marks, self.facts)
        when_env = {"P": self.P, **self.P}
        results = asserts.evaluate(self.sc.get("assert", []), trace, when_env)
        s, gated = asserts.score(results)
        h = hashlib.sha256()
        for f in self.frames:
            h.update(json.dumps(f.get("census", []), sort_keys=True).encode())
        sim_s = (self.frames[-1]["t"] - self.frames[0]["t"]) / TICK_HZ
        res = {"template": self.sc["template"], "family": self.sc.get("family"), "seed": self.seed,
               "params": {k: v for k, v in self.P.items()}, "score": round(s, 4), "gate_failed": gated,
               "assertions": results, "marks": self.marks,
               "facts": {k: v for k, v in self.facts.items() if k != "queries"},
               "sim_s": sim_s, "wall_s": round(wall, 2), "speedup": round(sim_s / max(wall, 1e-6), 2),
               "frames": len(self.frames), "trace_sha256": h.hexdigest(), "exit_code": rc,
               "rtt_ms_median": round(1000 * sorted(self.s.rtt)[len(self.s.rtt) // 2], 3) if self.s.rtt else None,
               "hello": self.s.hello}
        if self.out_dir:
            os.makedirs(self.out_dir, exist_ok=True)
            tag = f"{self.sc['template']}_s{self.seed}"
            with open(os.path.join(self.out_dir, tag + ".json"), "w") as f:
                json.dump(res, f, indent=1, default=str)
            if self.save_trace:
                with gzip.open(os.path.join(self.out_dir, tag + ".trace.jsonl.gz"), "wt") as f:
                    for fr in self.frames:
                        f.write(json.dumps(fr) + "\n")
        return res


def load_scenario(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--arg", action="append", default=[])
    ap.add_argument("--no-trace", action="store_true")
    ap.add_argument("--mem-floor", type=int, default=30)
    a = ap.parse_args()
    memgate(a.mem_floor)
    sc = load_scenario(a.scenario)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    r = Run(sc, a.seed, a.game, a.out, ["--" + x for x in a.arg], save_trace=not a.no_trace,
            log_path=os.path.join(a.out, f"{sc['template']}_s{a.seed}.log") if a.out else None)
    res = r.run()
    short = {k: res[k] for k in ("template", "seed", "score", "gate_failed", "sim_s", "wall_s", "speedup", "frames",
                                 "rtt_ms_median")}
    print(json.dumps(short))
    for x in res["assertions"]:
        print(f"  {x['id']:<18} {x['kind']:<12} applies={x.get('applies')} pass={x.get('pass')} "
              f"{json.dumps(x.get('measured', {}), default=str)[:160]} {x.get('error', '')}")
    print("  facts:", json.dumps({k: v for k, v in res["facts"].items() if k not in ("setup_results", "dev_results")},
                                 default=str)[:600])


if __name__ == "__main__":
    main()
