"""How far inside its bands the game sits on every playtest (author tool, never packaged).

WS1 and WS9 (notes/PHASE1-PLAN.md) ask the reference to hold every band with its worst value at
least 15% of the band's width inside each edge. This reads what `qa run --json` found and the
playtests' expectations, and for every measured value with a band works out its margin:
- a band [lo, hi]: min(value - lo, hi - value) / (hi - lo);
- "at most hi" for a quantity whose floor, 0, is no limit (a time, a distance, a rate): the
  room below hi as a share of hi;
- "at least lo" for a share (1 is no limit): the room above lo as a share of 1 - lo;
- "at least lo" for an open-ended quantity (a count, a distance, a speed): (value - lo) / lo.
Values the rule itself pins to an edge (the camera's tilt limits, which CM-2 makes the camera's
stops) and a clock read in whole minutes are listed as such, not as margins.

Usage:
  python scripts/margin_sweep.py FOUND.json [--playtests DIR] [--min 0.15] [--json OUT]
  python scripts/margin_sweep.py REPORT.json --plays DIR [--min 0.15] [--json OUT]
FOUND.json is what `qa run --json` wrote; REPORT.json a grader report (tests/verify.py), with
the instances' play files in --plays (named after the instance, "/" as "."). Prints every
margin under --min and a summary; exit code 1 when one is under it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
PLAYTESTS = TASK / "common" / "kit" / "playtests"


def band(v: object, lo: object, hi: object) -> float | None:
    if not isinstance(v, (int, float)) or lo is None or hi is None or hi <= lo:
        return None
    return min(v - lo, hi - v) / (hi - lo)


def worst_of(v: object) -> object:
    """A value given per person ({id: value}) as its largest; anything else as it is."""
    if (
        isinstance(v, dict)
        and v
        and all(isinstance(x, (int, float)) for x in v.values())
    ):
        return max(v.values())
    return v


def upto(v: object, hi: object) -> float | None:
    """At most hi, for a quantity whose floor (0) is no limit: the room left below hi, as a
    share of hi (the band [0, hi], judged at its upper edge only). A value per person is
    judged by its largest."""
    v = worst_of(v)
    if not isinstance(v, (int, float)) or not isinstance(hi, (int, float)) or hi <= 0:
        return None
    return (hi - v) / hi


def share(v: object, lo: object) -> float | None:
    """At least lo, for a share up to 1 (1 is no limit): the band [lo, 1] at its lower edge."""
    if not isinstance(v, (int, float)) or not isinstance(lo, (int, float)) or lo >= 1.0:
        return None
    return (v - lo) / (1.0 - lo)


def atleast(v: object, lo: object) -> float | None:
    if not isinstance(v, (int, float)) or not isinstance(lo, (int, float)) or lo <= 0:
        return None
    return (v - lo) / lo


def pair(v: object) -> list:
    return list(v) if isinstance(v, list) and len(v) == 2 else []


def margins(
    check: str, a: dict, m: dict, others: tuple = ()
) -> list[tuple[str, object, float | None]]:
    """(what, value, margin) for one expectation's measured values; an empty list when the
    check has no band (counts that must be zero, exact values, yes-or-no answers). `others`
    are the args of the play's expectations of the same check: a one-sided pace measured over
    the same window as a banded one (IN-2's sprint over FT-1's) is judged in that band."""
    out: list[tuple[str, object, float | None]] = []

    def add(what: str, v: object, mg: float | None) -> None:
        out.append((what, v, mg))

    if check == "accel":
        add(
            "seconds",
            m.get("seconds"),
            band(m.get("seconds"), a.get("min_s"), a.get("max_s")),
        )
    elif check == "brake":
        if "min_ratio" in a:
            add(
                "ratio",
                m.get("ratio"),
                band(m.get("ratio"), a["min_ratio"], a["max_ratio"]),
            )
        else:
            add(
                "metres",
                m.get("metres"),
                band(m.get("metres"), a.get("min_m"), a.get("max_m")),
            )
    elif check == "turn_circle":
        add(
            "diameter_m",
            m.get("diameter_m"),
            band(m.get("diameter_m"), a.get("min_m"), a.get("max_m")),
        )
    elif check == "decel":
        add(
            "mps2",
            m.get("mps2"),
            band(m.get("mps2"), a.get("min_mps2"), a.get("max_mps2")),
        )
    elif check == "max_speed":
        add("top_kmh", m.get("top_kmh"), upto(m.get("top_kmh"), a.get("max_kmh")))
    elif check in ("get_in", "get_out"):
        add(
            "seconds",
            m.get("seconds"),
            band(m.get("seconds"), a.get("min_s"), a.get("max_s")),
        )
        key = "closest_to_door_m" if check == "get_in" else "from_door_m"
        add(key, m.get(key), upto(m.get(key), a.get("door_m")))
    elif check == "seated":
        add(
            "worst_hips_m",
            m.get("worst_hips_m"),
            upto(m.get("worst_hips_m"), a.get("hips_m")),
        )
        if "hands_m" in a and m.get("worst_hand_m") is not None:
            add(
                "worst_hand_m",
                m.get("worst_hand_m"),
                upto(m.get("worst_hand_m"), a["hands_m"]),
            )
    elif check in ("camera_frame", "camera_vehicle"):
        key = "head_distance_m" if check == "camera_frame" else "vehicle_distance_m"
        for k, v in enumerate(pair(m.get(key))):
            add(f"{key}[{k}]", v, band(v, a.get("min_m"), a.get("max_m")))
        add(
            "farthest_from_middle",
            m.get("farthest_from_middle"),
            upto(m.get("farthest_from_middle"), a.get("middle", 0.4)),
        )
    elif check == "ragdoll":
        add(
            "late_ticks",
            m.get("late_ticks"),
            upto(max(0, m.get("late_ticks") or 0), a.get("within_ticks", 12))
            if m.get("late_ticks") is not None
            else None,
        )
        add("limp_s", m.get("limp_s"), atleast(m.get("limp_s"), a.get("min_s", 1.0)))
        add(
            "deepest_below_m",
            m.get("deepest_below_m"),
            upto(max(0.0, m.get("deepest_below_m") or 0.0), a.get("below_m", 0.05)),
        )
        if m.get("hips_step_m") is not None:
            add(
                "hips_step_m",
                m.get("hips_step_m"),
                upto(m.get("hips_step_m"), a.get("step_m", 1.0)),
            )
    elif check == "free_fall":
        tol = float(a.get("tol", 0.2))
        add(
            "accel_mps2",
            m.get("accel_mps2"),
            band(m.get("accel_mps2"), 9.81 * (1 - tol), 9.81 * (1 + tol)),
        )
    elif check == "get_up":
        if m.get("seconds") is not None:
            add("seconds", m.get("seconds"), upto(m.get("seconds"), a.get("within_s")))
    elif check == "impact_damage":
        exp, b, af = m.get("expected"), m.get("damage_before"), m.get("damage_after")
        if all(isinstance(x, (int, float)) for x in (exp, b, af)) and exp > 0:
            tol = float(a.get("tol", 0.25))
            add(
                "damage_rise",
                round(af - b, 4),
                band(af - b, exp * (1 - tol), exp * (1 + tol)),
            )
    elif check == "part_off":
        add("seconds", m.get("seconds"), upto(m.get("seconds"), a.get("within_s")))
    elif check == "explosion":
        add(
            "seconds",
            m.get("seconds"),
            band(m.get("seconds"), a.get("min_s"), a.get("max_s")),
        )
    elif check == "blast":
        exp, loss = m.get("expected_loss"), m.get("loss")
        if isinstance(exp, (int, float)) and isinstance(loss, (int, float)) and exp > 0:
            tol = float(a.get("tol", 0.1))
            add("loss", loss, band(loss, exp * (1 - tol), exp * (1 + tol)))
        before, after = m.get("distance_m"), m.get("distance_after_m")
        if (
            isinstance(before, (int, float))
            and isinstance(after, (int, float))
            and a.get("push_m") is not None
        ):
            pushed = round(after - before, 4)
            add("pushed_m", pushed, atleast(pushed, a.get("push_m")))
    elif check == "pace":
        hi = a.get("max_mps")
        if hi is None:
            same = [
                o.get("max_mps")
                for o in others
                if (
                    o.get("from"),
                    o.get("to"),
                    o.get("kind"),
                    o.get("bone"),
                    o.get("min_mps"),
                )
                == (
                    a.get("from"),
                    a.get("to"),
                    a.get("kind"),
                    a.get("bone"),
                    a.get("min_mps"),
                )
                and o.get("max_mps") is not None
            ]
            hi = same[0] if same else None
        v = m.get("speed_mps")
        add(
            "speed_mps",
            v,
            band(v, a.get("min_mps"), hi)
            if hi is not None
            else atleast(v, a.get("min_mps")),
        )
    elif check == "feet":
        add(
            "alternation",
            m.get("alternation"),
            share(m.get("alternation"), a.get("min_alternation")),
        )
        add(
            "slide_p95_mps",
            m.get("slide_p95_mps"),
            upto(m.get("slide_p95_mps"), a.get("max_slide_mps")),
        )
    elif check == "look_rate":
        add(
            "rate_dps",
            m.get("rate_dps"),
            band(m.get("rate_dps"), a.get("min_dps"), a.get("max_dps")),
        )
    elif check == "camera_tilt":
        add("pitch_deg (the camera's stops, CM-2)", m.get("pitch_deg"), None)
    elif check == "moves_along_camera":
        add("off_deg", m.get("off_deg"), upto(m.get("off_deg"), a.get("within_deg")))
    elif check == "hips_ratio":
        add("ratio", m.get("ratio"), upto(m.get("ratio"), a.get("max_ratio")))
    elif check == "jump":
        add(
            "rise_m",
            m.get("rise_m"),
            band(m.get("rise_m"), a.get("min_rise_m"), a.get("max_rise_m")),
        )
        add(
            "airborne_s",
            m.get("airborne_s"),
            band(m.get("airborne_s"), a.get("min_air_s"), a.get("max_air_s")),
        )
    elif check == "climb":
        add(
            "on_top_after_s",
            m.get("on_top_after_s"),
            upto(m.get("on_top_after_s"), a.get("within_s")),
        )
        add(
            "hand_to_edge_m",
            m.get("hand_to_edge_m"),
            upto(m.get("hand_to_edge_m"), a.get("hand_m")),
        )
        add(
            "deepest_bone_m",
            m.get("deepest_bone_m"),
            upto(m.get("deepest_bone_m"), a.get("max_into_m")),
        )
    elif check == "vault":
        add(
            "over_after_s",
            m.get("over_after_s"),
            upto(m.get("over_after_s"), a.get("within_s")),
        )
        add(
            "hips_clearance_m",
            m.get("hips_clearance_m"),
            atleast(m.get("hips_clearance_m"), a.get("clear_m")),
        )
        add(
            "deepest_bone_m",
            m.get("deepest_bone_m"),
            upto(m.get("deepest_bone_m"), a.get("max_into_m")),
        )
    elif check == "camera_clear":
        add(
            "clear_share",
            m.get("clear_share"),
            share(m.get("clear_share"), a.get("min_share")),
        )
    elif check == "fall_damage":
        exp, b, af = (
            m.get("expected_loss"),
            m.get("health_before"),
            m.get("health_after"),
        )
        if (
            all(isinstance(x, (int, float)) for x in (exp, b, af))
            and exp > 0
            and af > 0
        ):
            tol = max(float(a.get("tol", 0.1)) * exp, 0.5)
            add("loss", b - af, band(b - af, exp - tol, exp + tol))
    elif check == "rays":
        add(
            "share",
            m.get("share"),
            share(m.get("share"), a.get("min_share"))
            if a.get("min_share", 1.0) < 1.0
            else None,
        )
    elif check == "drivers":
        add(
            "worst_hips_m",
            m.get("worst_hips_m"),
            upto(m.get("worst_hips_m"), a.get("hips_m")),
        )
    elif check == "density":
        for w in m.get("minutes") or []:
            add(
                f"vehicles@{w.get('from_tick')}",
                w.get("vehicles"),
                band(w.get("vehicles"), *a["vehicles"]),
            )
            add(
                f"people@{w.get('from_tick')}",
                w.get("people"),
                band(w.get("people"), *a["people"]),
            )
    elif check == "green_flow":
        entered = m.get("entered") or {}
        if entered:
            low = min(entered.values())
            add("fewest_entered", low, atleast(low, a.get("min_vehicles")))
    elif check == "lane_keeping":
        add(
            "offset_p95_m",
            m.get("offset_p95_m"),
            upto(m.get("offset_p95_m"), a.get("max_offset_m")),
        )
        add(
            "heading_share",
            m.get("heading_share"),
            share(m.get("heading_share"), a.get("min_share")),
        )
    elif check == "lane_speeds":
        add(
            "worst_share_of_limit",
            m.get("worst_share_of_limit"),
            upto(m.get("worst_share_of_limit"), a.get("share")),
        )
    elif check == "walkable":
        add(
            "walkable_share",
            m.get("walkable_share"),
            share(m.get("walkable_share"), a.get("min_share")),
        )
    elif check == "crosswalk_use":
        add(
            "on_bands_share",
            m.get("on_bands_share"),
            share(m.get("on_bands_share"), a.get("min_share")),
        )
    elif check == "vehicle_contacts":
        add(
            "per_vehicle_minute",
            m.get("per_vehicle_minute"),
            upto(m.get("per_vehicle_minute"), a.get("max_rate")),
        )
    elif check == "horn_clear":
        add(
            "out_after_s",
            m.get("out_after_s"),
            upto(m.get("out_after_s"), a.get("within_s")),
        )
    elif check == "stop_wait":
        add(
            "longest_wait_s",
            m.get("longest_wait_s"),
            upto(m.get("longest_wait_s"), a.get("max_s")),
        )
    elif check in ("state_value",) and ("min" in a or "max" in a):
        v = m.get("minutes", m.get("value"))
        if a.get("as") == "minutes":
            # a clock read in whole minutes: the band's ends are the rounding of the rule's
            add("clock (whole minutes)", v, None)
        else:
            add("value", v, band(v, a.get("min"), a.get("max")))
    elif check == "moved":
        if float(a.get("min_m") or 0.0) > 0.0:
            add("moved_m", m.get("moved_m"), atleast(m.get("moved_m"), a["min_m"]))
        if "max_m" in a:
            add("moved_m", m.get("moved_m"), upto(m.get("moved_m"), a["max_m"]))
    elif check == "entity_near":
        add(
            "distance_m", m.get("distance_m"), upto(m.get("distance_m"), a.get("max_m"))
        )
    # combat
    elif check == "fire_rate":
        r, tol = float(a["rate"]), float(a.get("tol", 0.05))
        add(
            "rate_per_s",
            m.get("rate_per_s"),
            band(m.get("rate_per_s"), r * (1 - tol), r * (1 + tol)),
        )
    elif check == "reload":
        r, tol = float(a["reload_s"]), float(a.get("tol", 0.1))
        add(
            "seconds",
            m.get("seconds"),
            band(m.get("seconds"), r * (1 - tol), r * (1 + tol)),
        )
    elif check == "aim_pose":
        add(
            "hand_from_shoulder_height_m",
            m.get("hand_from_shoulder_height_m"),
            upto(m.get("hand_from_shoulder_height_m"), a.get("hand_m", 0.25)),
        )
        add(
            "forearm_off_deg",
            m.get("forearm_off_deg"),
            upto(m.get("forearm_off_deg"), a.get("max_deg", 20.0)),
        )
    elif check == "lock_on":
        add(
            "aim_from_chest_m",
            m.get("aim_from_chest_m"),
            upto(m.get("aim_from_chest_m"), a.get("aim_m", 0.3)),
        )
        add(
            "farthest_from_middle",
            m.get("farthest_from_middle"),
            upto(m.get("farthest_from_middle"), a.get("middle", 0.3)),
        )
    elif check == "hit_rate":
        add("share", m.get("share"), share(m.get("share"), a.get("min_share")))
    elif check in ("cover_enter", "cover_hold"):
        if check == "cover_enter":
            add(
                "seconds",
                m.get("seconds"),
                upto(m.get("seconds"), a.get("within_s", 1.0)),
            )
        add(
            "from_box_m",
            m.get("from_box_m"),
            upto(m.get("from_box_m"), a.get("near_m", 0.6)),
        )
        add(
            "hips_ratio",
            m.get("hips_ratio"),
            upto(m.get("hips_ratio"), a.get("ratio", 0.75)),
        )
    elif check == "cover_leave":
        add("seconds", m.get("seconds"), upto(m.get("seconds"), a.get("within_s", 0.5)))
        add(
            "from_box_m",
            m.get("from_box_m"),
            atleast(m.get("from_box_m"), a.get("near_m", 0.6)),
        )
    elif check == "lean_out":
        add(
            "head_rise_m",
            m.get("head_rise_m"),
            atleast(m.get("head_rise_m"), a.get("rise_m", 0.3)),
        )
    elif check == "cover_cuts":
        add("ratio", m.get("ratio"), upto(m.get("ratio"), a.get("max_ratio", 0.4)))
    elif check == "turn_hostile":
        within = float(a.get("within_s", 2.0))
        for k, v in m.items():
            if isinstance(v, (int, float)):
                mg = (
                    band(v, 0.0, within)
                    if a.get("trigger") != "hit"
                    else upto(v, within)
                )
                add(f"entity {k} s", v, mg)
    elif check in ("flee_away", "retreat"):
        for k, v in m.items():
            add(f"entity {k} gain_m", v, atleast(v, a.get("min_m")))
    elif check == "reach_cover":
        n, got = m.get("hostile_enforcers"), m.get("in_cover")
        if n:
            add("share_in_cover", got / n, share(got / n, a.get("min_share", 0.5)))
    elif check == "gunshot_flee":
        for k, v in m.items():
            if isinstance(v, dict):
                add(
                    f"entity {k} mps",
                    v.get("mps"),
                    atleast(v.get("mps"), a.get("min_mps")),
                )
                add(
                    f"entity {k} gain_m",
                    v.get("gain_m"),
                    atleast(v.get("gain_m"), a.get("min_gain_m")),
                )
                add(
                    f"entity {k} growing",
                    v.get("growing"),
                    share(v.get("growing"), a.get("min_share")),
                )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("found", type=Path)
    ap.add_argument("--playtests", type=Path, default=PLAYTESTS)
    ap.add_argument("--min", type=float, default=0.15)
    ap.add_argument("--plays", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    found = json.loads(a.found.read_text())
    plays = {}
    if isinstance(found, dict):  # a grader report: its instances and their play files
        found = [
            {"playtest": i["name"], "expectations": i.get("checks") or []}
            for i in found.get("instances", [])
        ]
        for f in found:
            path = a.plays / (f["playtest"].replace("/", ".") + ".json")
            if path.is_file():
                d = json.loads(path.read_text())
                plays[f["playtest"]] = {e["id"]: e for e in d["expect"]}
    else:
        for path in sorted(a.playtests.glob("*.json")):
            d = json.loads(path.read_text())
            plays[d["name"]] = {e["id"]: e for e in d["expect"]}
    rows, low = [], []
    for f in found:
        exps = plays.get(f["playtest"], {})
        for o in f["expectations"]:
            e = exps.get(o["id"])
            if e is None or not o.get("measured"):
                continue
            others = tuple(
                x.get("args") or {}
                for x in exps.values()
                if x is not e and x.get("check") == e["check"]
            )
            for what, v, mg in margins(
                e["check"], e.get("args") or {}, o["measured"], others
            ):
                row = {"playtest": f["playtest"], "id": o["id"], "rule": o.get("rule"), "what": what,
                       "value": v, "margin": None if mg is None else round(mg, 3)}  # fmt: skip
                rows.append(row)
                if mg is not None and mg < a.min:
                    low.append(row)
    for r in low:
        print(
            f"{r['margin']:7.1%}  {r['playtest']}  {r['id']} ({r['rule']})  {r['what']} = {r['value']}"
        )
    banded = [r for r in rows if r["margin"] is not None]
    print(f"{len(banded)} banded values in {len({(r['playtest'], r['id']) for r in banded})} "
          f"expectations; {len(low)} under {a.min:.0%}; worst "
          f"{min((r['margin'] for r in banded), default=None)}")  # fmt: skip
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1))
    return 1 if low else 0


if __name__ == "__main__":
    sys.exit(main())
