"""Check that no release instance repeats its playtest's parameters (author tool; never packaged).

A release instance is drawn from a template that has a shipped playtest of the same name: the
instance's name without its last "/<tag>" (make_instances.py names instances that way). An
instance REPEATS its playtest when any of these holds:

1. variation: a variation the instance uses is one the playtest uses. A play uses the
   variation of its --variation=N argument (1 when it has none, GDD chapter 17) and the
   "variation" of each of its world.reset commands; values that are not whole numbers
   (malformed on purpose) are ignored.
2. place: a point where the instance puts something lies within 1.0 m, measured
   horizontally, of a point where the playtest puts something. Those points are the "at"
   of player.spawn, npc.spawn, vehicle.spawn and prop.spawn commands: a point [x, y, z] as
   it is, an anchor resolved against the plan the play runs on (the plan folder named by the
   instance's manifest entry, else the shipped plans; the map of --map=, else downtown).
   Values that are not places ("player", malformed or unresolvable anchors) are ignored.
3. leads: the playtest's player.spawn commands name leads ("lead") and the instance's
   player.spawn commands name exactly the same leads in the same order.
4. size: a prop.spawn of the instance has the kind of a prop.spawn of the playtest and a
   height (size[1]) within 0.01 m of that one's; a prop without a size has its kind's
   default, so two such props of one kind count as the same height.
5. watch: an expectation of the instance whose args name a reset_step (the signal checks)
   starts its watch, its "from" mark, as many ticks after the start of that reset step
   (within one tick) as an expectation of the playtest with the same check does. Ticks
   count 1 per dev or query step and N per run step; with a wait_for between the reset and
   the mark the count is unknown and matches nothing.
6. steps: the instance's steps are exactly the playtest's.
7. models: the playtest spawns vehicles and the instance's vehicle.spawn commands name the
   same models in the same order (the whole list of "model" values, one per command).
   (A vehicle placed within 1.0 m of one of the playtest's is rule 2.)
8. speeds: a speed the instance drives at lies within 0.5 km/h of one the playtest drives
   at. The speeds a play drives at are the "kmh" of its cruise steps and the "min_kmh" of
   its wait_for entity steps, except 60, 40 and 8 km/h: the design document fixes those for
   its checks (VH-1's 0-60 km/h and braking from 60, IN-2's handbrake from 40, VH-1's
   turning circle at 8), so every instance of a handling playtest uses them.
9. stand-offs: the playtest stands the player beside a parked vehicle and the instance does
   so on the same sides and at the same ends, in the same order. A player.spawn stands
   beside a parked vehicle when its point lies within 4.0 m (horizontally) of the most
   recent vehicle.spawn whose driver is "none" (or not given); its side is left or right of
   that vehicle's centre line and its end ahead of or behind its centre, along the
   vehicle's heading (the command's "heading", else its anchor's, else 0).
10. damage: a vehicle.spawn of the instance has a "damage" within 0.005 of the "damage" of
    a vehicle.spawn of the playtest (damages above 0 only).

Instances whose name has no shipped playtest (release-only templates, such as the plan
swap) are listed as such and not compared.

Usage:
  python scripts/check_disjoint.py --manifest FILE [--playtests DIR] [--plans DIR] [--json FILE]

It prints one line per instance. Exit code 0 when no instance repeats its playtest, 1 when
one does, 2 when an input cannot be read.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))

from qakit.plan import AnchorError, Plan

PLACING = ("player.spawn", "npc.spawn", "vehicle.spawn", "prop.spawn")
NEAR_M = 1.0
SAME_HEIGHT_M = 0.01
SAME_TICKS = 1
DEFAULT_VARIATION = 1  # GDD chapter 17: --variation defaults to 1
SAME_KMH = 0.5
# VH-1's 0-60 km/h and braking from 60, IN-2's handbrake from 40, VH-1's circle at 8
FIXED_KMH = (60.0, 40.0, 8.0)
BESIDE_M = 4.0
SAME_DAMAGE = 0.005


def commands(play: dict) -> list[tuple[int, str, dict]]:
    """(step index, command, args) of every DevConsole command of a play, in order."""
    out = []
    for i, step in enumerate(play.get("steps", [])):
        for cmd in step.get("dev", []) if isinstance(step, dict) else []:
            if (
                isinstance(cmd, list)
                and len(cmd) == 2
                and isinstance(cmd[0], str)
                and isinstance(cmd[1], dict)
            ):
                out.append((i, cmd[0], cmd[1]))
    return out


def whole(value: object) -> int | None:
    """An int for a whole number (12 or 12.0), else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    return int(value)


def arg_value(play: dict, flag: str) -> str | None:
    """The value of --flag=VALUE in a play's args, or None."""
    for a in play.get("args", []):
        if isinstance(a, str) and a.startswith(f"--{flag}="):
            return a.split("=", 1)[1]
    return None


def variations(play: dict) -> set[int]:
    """Every variation a play uses (rule 1)."""
    out = set()
    flag = arg_value(play, "variation")
    if flag is None:
        out.add(DEFAULT_VARIATION)
    else:
        try:
            out.add(int(flag))
        except ValueError:
            pass
    for _, cmd, args in commands(play):
        if cmd == "world.reset" and whole(args.get("variation")) is not None:
            out.add(whole(args["variation"]))
    return out


def spot(at: object, plan: Plan | None) -> tuple[float, float, float | None] | None:
    """(x, z, the anchor's heading or None) of an "at" value: a point [x, y, z] as it is, an
    anchor resolved against the plan; None for anything else ("player", malformed or
    unresolvable anchors, or an anchor without a plan)."""
    if (
        isinstance(at, list)
        and len(at) == 3
        and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in at)
    ):
        return float(at[0]), float(at[2]), None
    if isinstance(at, dict) and plan is not None:
        try:
            pl = plan.resolve(at)
        except (AnchorError, KeyError, TypeError, ValueError, StopIteration):
            return None
        return pl.p[0], pl.p[2], pl.heading_deg
    return None


def places(play: dict, plan: Plan | None) -> list[tuple[float, float]]:
    """(x, z) of every point where a play puts something (rule 2)."""
    out = []
    for _, cmd, args in commands(play):
        if cmd not in PLACING or "at" not in args:
            continue
        s = spot(args["at"], plan)
        if s is not None:
            out.append((s[0], s[1]))
    return out


def models(play: dict) -> list[str]:
    """The model of every vehicle.spawn command, in order (rule 7)."""
    return [
        a["model"]
        for _, c, a in commands(play)
        if c == "vehicle.spawn" and isinstance(a.get("model"), str)
    ]


def speeds(play: dict) -> list[float]:
    """The speeds a play drives at (rule 8): the kmh of its cruise steps and the min_kmh of
    its wait_for entity steps, without FIXED_KMH."""
    out = []
    for step in play.get("steps", []):
        if not isinstance(step, dict) or len(step) != 1:
            continue
        ((kind, arg),) = step.items()
        v = None
        if kind == "cruise" and isinstance(arg, dict):
            v = arg.get("kmh")
        elif (
            kind == "wait_for"
            and isinstance(arg, dict)
            and isinstance(arg.get("entity"), dict)
        ):
            v = arg["entity"].get("min_kmh")
        if (
            isinstance(v, (int, float))
            and not isinstance(v, bool)
            and float(v) not in FIXED_KMH
        ):
            out.append(float(v))
    return out


def stand_offs(play: dict, plan: Plan | None) -> list[tuple[str, str]]:
    """(side, end) of every player.spawn standing beside a parked vehicle (rule 9)."""
    out = []
    parked = None  # (x, z, heading) of the most recent vehicle spawned without a driver
    for _, cmd, args in commands(play):
        if cmd not in ("vehicle.spawn", "player.spawn") or "at" not in args:
            continue
        s = spot(args["at"], plan)
        if s is None:
            continue
        if cmd == "vehicle.spawn":
            if args.get("driver", "none") == "none":
                h = args.get("heading", s[2] if s[2] is not None else 0.0)
                if isinstance(h, (int, float)) and not isinstance(h, bool):
                    parked = (s[0], s[1], float(h))
            continue
        if parked is None:
            continue
        dx, dz = s[0] - parked[0], s[1] - parked[1]
        if math.hypot(dx, dz) > BESIDE_M:
            continue
        h = math.radians(parked[2])
        ahead = dx * math.sin(h) - dz * math.cos(h)
        right = dx * math.cos(h) + dz * math.sin(h)
        out.append(
            ("right" if right > 0 else "left", "ahead" if ahead > 0 else "behind")
        )
    return out


def damages(play: dict) -> list[float]:
    """The damage of every vehicle.spawn that has one above 0 (rule 10)."""
    out = []
    for _, cmd, args in commands(play):
        d = args.get("damage")
        if (
            cmd == "vehicle.spawn"
            and isinstance(d, (int, float))
            and not isinstance(d, bool)
            and d > 0
        ):
            out.append(float(d))
    return out


def leads(play: dict) -> list[object]:
    """The leads a play's player.spawn commands name, in order (rule 3)."""
    return [
        a["lead"] for _, c, a in commands(play) if c == "player.spawn" and "lead" in a
    ]


def prop_heights(play: dict) -> list[tuple[str, float | None]]:
    """(kind, height or None for the kind's default size) of every prop.spawn (rule 4)."""
    out = []
    for _, cmd, args in commands(play):
        if cmd != "prop.spawn" or not isinstance(args.get("kind"), str):
            continue
        size = args.get("size")
        if size is None:
            out.append((args["kind"], None))
        elif (
            isinstance(size, list)
            and len(size) == 3
            and isinstance(size[1], (int, float))
            and not isinstance(size[1], bool)
        ):
            out.append((args["kind"], float(size[1])))
    return out


def tick_cost(step: object) -> int | None:
    """Ticks a step advances: 1 for dev and query, N for run, 0 for the rest, None for
    wait_for (unknown)."""
    if not isinstance(step, dict) or len(step) != 1:
        return 0
    ((kind, arg),) = step.items()
    if kind in ("dev", "query"):
        return 1
    if kind == "run":
        return int(arg) if whole(arg) is not None else None
    if kind == "wait_for":
        return None
    return 0


def watches(play: dict) -> list[tuple[str, int | None]]:
    """(check, ticks from the start of its reset step to its "from" mark) of every
    expectation that names a reset_step (rule 5)."""
    steps = play.get("steps", [])
    mark_at = {}  # a mark set twice names its later frame, as in a run's record
    for i, step in enumerate(steps):
        if isinstance(step, dict) and isinstance(step.get("mark"), str):
            mark_at[step["mark"]] = i
    out = []
    for e in play.get("expect", []):
        args = e.get("args") or {}
        reset, mark = whole(args.get("reset_step")), args.get("from")
        if reset is None or mark not in mark_at:
            continue
        ticks: int | None = 0
        for step in steps[reset : mark_at[mark]]:
            cost = tick_cost(step)
            ticks = None if cost is None or ticks is None else ticks + cost
        out.append((str(e.get("check")), ticks))
    return out


def repeats(
    inst: dict, test: dict, inst_plan: Plan | None, test_plan: Plan | None
) -> list[str]:
    """Why an instance repeats its playtest (rules 1-10); empty when it does not.

    Args:
        inst: The instance (a qa-play/1 object).
        test: The shipped playtest of the same name.
        inst_plan: The plan the instance runs on (for anchors), or None.
        test_plan: The plan the playtest runs on, or None.
    """
    why = []
    same = sorted(variations(inst) & variations(test))
    if same:
        why.append(f"variation {same[0]} as in the playtest")
    theirs = places(test, test_plan)
    for x, z in places(inst, inst_plan):
        near = [math.dist((x, z), q) for q in theirs]
        if near and min(near) < NEAR_M:
            why.append(
                f"a place at ({x:.2f}, {z:.2f}) is {min(near):.2f} m from one of the playtest's"
            )
            break
    if leads(test) and leads(inst) == leads(test):
        why.append("the same leads in the same order")
    props = prop_heights(test)
    for kind, h in prop_heights(inst):
        for k2, h2 in props:
            if kind == k2 and (
                (h is None and h2 is None)
                or (h is not None and h2 is not None and abs(h - h2) < SAME_HEIGHT_M)
            ):
                why.append(f"a {kind} as high as one of the playtest's ({h} m)")
                break
        else:
            continue
        break
    for check, ticks in watches(inst):
        for c2, t2 in watches(test):
            if (
                check == c2
                and ticks is not None
                and t2 is not None
                and abs(ticks - t2) <= SAME_TICKS
            ):
                why.append(
                    f"{check} starts watching {ticks} ticks after its reset, as the playtest does"
                )
                break
        else:
            continue
        break
    if inst.get("steps") == test.get("steps"):
        why.append("the same steps as the playtest")
    if models(test) and models(inst) == models(test):
        why.append("the same models in the same order")
    theirs_kmh = speeds(test)
    for v in speeds(inst):
        near_kmh = [abs(v - w) for w in theirs_kmh]
        if near_kmh and min(near_kmh) <= SAME_KMH:
            why.append(f"a speed of {v:g} km/h, as the playtest drives")
            break
    sides = stand_offs(test, test_plan)
    if sides and stand_offs(inst, inst_plan) == sides:
        why.append("the player stands on the same sides and ends of the parked vehicle")
    theirs_dmg = damages(test)
    for d in damages(inst):
        if any(abs(d - e) <= SAME_DAMAGE + 1e-9 for e in theirs_dmg):
            why.append(f"a vehicle at damage {d:g}, as in the playtest")
            break
    return why


def playtest_name(inst: dict) -> str:
    """The shipped playtest an instance comes from: its name less the last "/<tag>"."""
    return str(inst.get("name", "")).rsplit("/", 1)[0]


def plan_of(play: dict, folder: Path, cache: dict) -> Plan | None:
    """The plan a play runs on, from a plan folder: <map>.json, the map of --map=."""
    path = folder / f"{arg_value(play, 'map') or 'downtown'}.json"
    if path not in cache:
        cache[path] = Plan.load(path) if path.is_file() else None
    return cache[path]


def check_manifest(manifest: Path, playtests: Path, plans: Path) -> list[dict]:
    """Compare every instance of a manifest with its playtest.

    Returns:
        One {"file", "name", "playtest", "repeats": [reasons]} per instance, in manifest
        order; "playtest" is None when no shipped playtest has the name.

    Raises:
        OSError, ValueError: An unreadable manifest, playtest or instance.
    """
    tests = {}
    for path in sorted(playtests.glob("*.json")):
        play = json.loads(path.read_text())
        tests[play["name"]] = play
    data = json.loads(manifest.read_text())
    cache: dict = {}
    out = []
    for entry in data["instances"]:
        inst = json.loads((manifest.parent / entry["file"]).read_text())
        name = playtest_name(inst)
        test = tests.get(name)
        row = {
            "file": entry["file"],
            "name": inst.get("name"),
            "playtest": None,
            "repeats": [],
        }
        if test is not None:
            folder = manifest.parent / entry["plans"] if entry.get("plans") else plans
            row["playtest"] = name
            row["repeats"] = repeats(
                inst, test, plan_of(inst, folder, cache), plan_of(test, plans, cache)
            )
        out.append(row)
    return out


def main() -> int:
    """Check a manifest; print one line per instance."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--playtests", type=Path, default=TASK / "common/kit/playtests")
    ap.add_argument("--plans", type=Path, default=TASK / "common/design/plan")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()
    try:
        rows = check_manifest(a.manifest, a.playtests, a.plans)
    except (OSError, ValueError, KeyError) as exc:
        print(f"cannot check: {exc}", file=sys.stderr)
        return 2
    bad = 0
    for r in rows:
        if r["playtest"] is None:
            print(f"no playtest  {r['name']}")
        elif r["repeats"]:
            bad += 1
            print(f"REPEATS      {r['name']}: {'; '.join(r['repeats'])}")
        else:
            print(f"disjoint     {r['name']}")
    compared = sum(r["playtest"] is not None for r in rows)
    print(f"{compared} instances compared with their playtests, {bad} repeat one")
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
