"""Assertion helpers: Python-hosted expressions over a recorded trace (design 3.4).

Each assertion's `expr` is evaluated with these helpers in scope. Helpers record what they
measured through `measure(...)`, so every assertion reports its values, not only pass/fail.
"""
import math
import statistics
from types import SimpleNamespace

TICK_HZ = 60.0


class Trace:
    def __init__(self, frames, plan, params, marks, facts):
        self.frames = frames
        self.plan = plan
        self.P = params
        self.M = marks
        self.S = facts
        self._index = []
        for f in frames:
            self._index.append({e["id"]: e for e in f.get("census", [])})
        self.player_id = None
        for f in frames:
            for e in f.get("census", []):
                if e["k"] == "player":
                    self.player_id = e["id"]
            if self.player_id is not None:
                break

    def ent(self, i, eid):
        return self._index[i].get(eid)

    def window(self, after=None, before=None):
        for i, f in enumerate(self.frames):
            if after is not None and f["t"] < after:
                continue
            if before is not None and f["t"] > before:
                break
            yield i, f


def make_env(trace, record):
    T = trace
    P = SimpleNamespace(**trace.P)

    def measure(name, value):
        record.setdefault("measured", {})[name] = value
        return value

    def sec(ticks):
        return None if ticks is None else ticks / TICK_HZ

    def player(i):
        return T.ent(i, T.player_id)

    def player_vehicle(i):
        p = player(i)
        if p is None or p.get("veh") is None:
            return None
        return T.ent(i, p["veh"])

    def wanted(i):
        st = T.frames[i].get("state") or {}
        return int(st.get("wanted", 0))

    def dist(a, b):
        return math.hypot(a["p"][0] - b["p"][0], a["p"][2] - b["p"][2])

    def eventually(pred, within_s, after_tick):
        if after_tick is None:
            return None
        for i, f in T.window(after_tick, after_tick + within_s * TICK_HZ):
            if pred(i):
                measure("delay_s", round((f["t"] - after_tick) / TICK_HZ, 3))
                return f["t"]
        measure("delay_s", None)
        return None

    def always(pred, after_tick=None, before_tick=None):
        for i, f in T.window(after_tick, before_tick):
            if not pred(i):
                measure("first_violation_t", f["t"])
                return False
        return True

    def q(values, p):
        if not values:
            return None
        v = sorted(values)
        k = min(len(v) - 1, max(0, int(math.ceil(p * len(v))) - 1))
        return v[k]

    def median(values):
        return statistics.median(values) if values else None

    def in_band(x, lo, hi):
        return x is not None and lo <= x <= hi

    def signal_state(i, approach_id):
        jid = approach_id.split("<")[0]
        for e in T.frames[i].get("census", []):
            if e["k"] == "signal" and e.get("st") and approach_id in e["st"]:
                return e["st"][approach_id]
        return None

    def crossings(entity_filter, approach_id, after_tick=None):
        """Ticks at which matching entities cross the approach's stop line (centre point),
        with the signal state seen in the previous and current frames."""
        out = []
        prev = {}
        for i, f in T.window(after_tick):
            for e in f.get("census", []):
                if not entity_filter(e):
                    continue
                s, lat = T.plan.stop_line_side(approach_id, e["p"][0], e["p"][2])
                hw = T.plan.approaches[approach_id]["half_w"]
                if e["id"] in prev:
                    s0, lat0, i0 = prev[e["id"]]
                    if s0 < 0 <= s and -0.5 <= lat <= hw + 0.5:
                        out.append({"id": e["id"], "t": f["t"], "state": signal_state(i, approach_id),
                                    "state_prev": signal_state(i0, approach_id)})
                prev[e["id"]] = (s, lat, i)
        return out

    def first_seen():
        seen = {}
        for i, f in enumerate(T.frames):
            for e in f.get("census", []):
                if e["id"] not in seen:
                    seen[e["id"]] = (i, e)
        return seen

    def max_speed_between_frames(eid, after_tick=None):
        prev = None
        vmax = 0.0
        for i, f in T.window(after_tick):
            e = T.ent(i, eid)
            if e is None:
                prev = None
                continue
            if prev is not None:
                dt = (f["t"] - prev[0]) / TICK_HZ
                if dt > 0:
                    vmax = max(vmax, math.hypot(e["p"][0] - prev[1][0], e["p"][2] - prev[1][2]) / dt)
            prev = (f["t"], e["p"])
        return vmax

    def approach_id(j, k):
        return T.plan.junctions[j]["approaches"][int(k)]["id"]

    def player_vehicle_id():
        for i, f in enumerate(T.frames):
            p = player(i)
            if p is not None and p.get("veh") is not None:
                return p["veh"]
        return None

    def frame_at(tick):
        best = None
        for i, f in enumerate(T.frames):
            if f["t"] <= tick:
                best = i
        return best

    def hud_wanted(i):
        return (T.frames[i].get("hud") or {}).get("hud_wanted")

    def speeds(eid, after_tick=None, before_tick=None):
        out = []
        prev = None
        for i, f in T.window(after_tick, before_tick):
            e = T.ent(i, eid)
            if e is None:
                prev = None
                continue
            if prev is not None and f["t"] > prev[0]:
                dt = (f["t"] - prev[0]) / TICK_HZ
                out.append(math.hypot(e["p"][0] - prev[1][0], e["p"][2] - prev[1][2]) / dt)
            prev = (f["t"], e["p"])
        return out

    def junction_entries(j, entity_filter, after_tick=None):
        out = []
        for a in T.plan.junctions[j]["approaches"]:
            for c in crossings(entity_filter, a["id"], after_tick):
                fb = frame_at(c["t"] - 30)
                c["ap"] = a["id"]
                c["state_before"] = signal_state(fb, a["id"]) if fb is not None else None
                out.append(c)
        return out

    def state_runs(ap, state, after_tick=None):
        runs, cur, start = [], None, None
        for i, f in T.window(after_tick):
            st = signal_state(i, ap)
            if st != cur:
                if cur == state and start is not None:
                    runs.append((f["t"] - start) / TICK_HZ)
                cur, start = st, f["t"]
        return runs[1:] if runs and after_tick is not None else runs

    def lane_offsets(entity_filter, after_tick=None, min_speed=2.0):
        out = []
        for i, f in T.window(after_tick):
            for e in f.get("census", []):
                if not entity_filter(e) or "v" not in e:
                    continue
                vx, vz = e["v"][0], e["v"][2]
                sp = math.hypot(vx, vz)
                if sp < min_speed or T.plan.in_junction_box(e["p"][0], e["p"][2]):
                    continue
                r = T.plan.lane_offset(e["p"][0], e["p"][2], (vx / sp, vz / sp))
                r_any = T.plan.lane_offset(e["p"][0], e["p"][2])
                if r is not None:
                    out.append((abs(r[0]), True))
                elif r_any is not None:
                    out.append((abs(r_any[0]), False))
        return out

    def impacts(entity_filter, after_tick=None, dv=2.2):
        n, veh_min = 0, 0.0
        prev = {}
        for i, f in T.window(after_tick):
            for e in f.get("census", []):
                if not entity_filter(e) or "v" not in e:
                    continue
                if e["id"] in prev:
                    t0, v0 = prev[e["id"]]
                    dvv = math.hypot(e["v"][0] - v0[0], e["v"][2] - v0[2])
                    if dvv > dv * (f["t"] - t0) / 6.0:
                        n += 1
                    veh_min += (f["t"] - t0) / TICK_HZ / 60.0
                prev[e["id"]] = (f["t"], e["v"])
        return n, veh_min

    def walkable_frac(entity_filter, after_tick=None):
        ok = tot = 0
        for i, f in T.window(after_tick):
            for e in f.get("census", []):
                if entity_filter(e):
                    tot += 1
                    ok += 1 if T.plan.on_sidewalk(e["p"][0], e["p"][2]) else 0
        return ok / tot if tot else None

    def gait(eid, t0, t1, skip_s=1.5):
        """Speed, cadence, alternation and planted-foot slide from bone poses (needs bones)."""
        rows = []
        for i, f in T.window(t0 + skip_s * TICK_HZ, t1):
            b = (f.get("bones") or {}).get(str(eid))
            e = T.ent(i, eid)
            if not b or e is None or "LeftToes" not in b:
                continue
            # contact point: the toe bone (ball of the foot), which is on the ground in heel-toe
            # walking and in forefoot running alike
            rows.append((f["t"], e["p"], b["LeftToes"], b["RightToes"]))
        if len(rows) < 10:
            return None
        sp = []
        for a, b2 in zip(rows, rows[1:]):
            dt = (b2[0] - a[0]) / TICK_HZ
            sp.append(math.hypot(b2[1][0] - a[1][0], b2[1][2] - a[1][2]) / dt)
        res = {"speed": statistics.median(sp)}
        touch, slides = [], []
        for side, col in (("L", 2), ("R", 3)):
            ys = [r[col][1] for r in rows]
            floor = min(ys) + 0.04
            # contact intervals: runs of frames with the toe near the ground; slide is measured on
            # the middle 60% of each interval so touch-down and lift-off frames do not count
            runs, cur = [], []
            for r in rows:
                if r[col][1] <= floor:
                    cur.append(r)
                elif cur:
                    runs.append(cur)
                    cur = []
            if cur:
                runs.append(cur)
            for run in runs:
                if run is not runs[0] or rows[0][col][1] > floor:
                    touch.append((run[0][0], side))
                n = len(run)
                mid = run[int(n * 0.2):max(int(n * 0.2) + 2, int(math.ceil(n * 0.8)))]
                for a, b2 in zip(mid, mid[1:]):
                    dt = (b2[0] - a[0]) / TICK_HZ
                    slides.append(math.hypot(b2[col][0] - a[col][0], b2[col][2] - a[col][2]) / dt)
        touch.sort()
        dur = (rows[-1][0] - rows[0][0]) / TICK_HZ
        res["cadence_hz"] = len(touch) / dur if dur > 0 else 0
        alt = [1 if x[1] != y[1] else 0 for x, y in zip(touch, touch[1:])]
        res["alternation"] = sum(alt) / len(alt) if alt else 0
        res["slide_q95"] = q(slides, 0.95) if slides else None
        res["touchdowns"] = len(touch)
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()}

    env = {k: v for k, v in locals().items() if callable(v)}
    env.update({"T": T, "P": P, "M": T.M, "S": T.S, "G": T.plan, "math": math, "len": len, "min": min,
                "max": max, "abs": abs, "all": all, "any": any, "sum": sum, "sorted": sorted, "round": round,
                "zip": zip, "set": set, "str": str, "float": float, "int": int, "list": list, "dict": dict,
                "range": range, "enumerate": enumerate, "isinstance": isinstance, "tuple": tuple,
                "None": None, "True": True, "False": False})
    return env


def evaluate(assertions, trace, when_env):
    results = []
    for a in assertions:
        rec = {"id": a["id"], "kind": a.get("kind", "check"), "w": float(a.get("w", 0.0))}
        when = a.get("when")
        if when is not None and not bool(eval(str(when), dict(when_env, __builtins__={}))):
            rec["applies"] = False
            results.append(rec)
            continue
        rec["applies"] = True
        env = make_env(trace, rec)
        env["__builtins__"] = {}
        try:
            # env is the globals dict, so lambdas inside the expression see the helpers
            v = eval(a["expr"], env)
            rec["pass"] = bool(v)
            rec.setdefault("measured", {})["value"] = v if isinstance(v, (int, float, str, bool)) or v is None else str(v)
        except Exception as ex:  # an assertion that cannot be evaluated fails
            rec["pass"] = False
            rec["error"] = f"{type(ex).__name__}: {ex}"
        results.append(rec)
    return results


def score(results):
    gate_fail = any(r.get("applies") and r["kind"] in ("precondition", "consistency") and not r.get("pass")
                    for r in results)
    checks = [r for r in results if r.get("applies") and r["kind"] == "check"]
    wsum = sum(r["w"] for r in checks)
    if gate_fail or wsum <= 0:
        return 0.0, gate_fail
    return sum(r["w"] for r in checks if r.get("pass")) / wsum, gate_fail
