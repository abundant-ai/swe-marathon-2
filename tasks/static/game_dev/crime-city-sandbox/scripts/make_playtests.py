"""Write QA's playtests (qa-play/1) into common/kit/playtests/ (author tool, never packaged).

Each playtest sets up a situation on the shipped plans with fixed values and lists the
expectations that must hold, each citing its design rule. Expected points are the anchors
resolved here with the kit's own plan reader, so every value in a file is explicit. The
numbers come from the design document only: the placement tolerance (0.5 m, chapter 17),
the clock rate (one game minute per second of play, within 1%), the new game's values
(chapters 2, 10, 11 and 13) and the DevConsole table.

The first set covers the automation contract (chapter 17) and the rules closest to it:
IN-3, WD-11, WD-14 and SV-4 to SV-6.

Usage:
  python scripts/make_playtests.py [--out DIR] [--check]
--check compares the files on disk with what would be written and exits 1 on a difference.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))

from qakit.plan import Plan
from qakit.play import parse_play

sys.path.insert(0, str(TASK / "scripts"))
from plan_probes import BUILT, Probes, inset

OUT = TASK / "common" / "kit" / "playtests"
PLAN_FILE = TASK / "common" / "design" / "plan" / "downtown.json"
PLAN = Plan.load(PLAN_FILE)
LIMITS = {
    "wall_s": 240,
    "boot_s": 60,
    "step_s": 30,
    "cpu_s": 600,
    "memory_mb": 1536,
    "disk_mb": 512,
}
PLACED_M = (
    0.5  # chapter 17: placed things end within 0.5 m of their point, horizontally
)
NEW_GAME_MONEY = 500  # EC-1


def point(anchor: object) -> list[float]:
    """The anchor's position, rounded to the millimetre."""
    return [round(c, 3) for c in PLAN.resolve(anchor).p]


class Playtest:
    """A playtest being written: steps with their indices, expectations."""

    def __init__(
        self, name: str, rules: list[str], about: str, args: list[str], **extra: object
    ) -> None:
        self.name = name
        self.raw: dict = {
            "format": "qa-play/1",
            "name": name,
            "template": name.split("/")[0],
            "about": about,
            "rules": rules,
            "role": extra.pop("role", "solo"),
            "args": args,
            "mode": extra.pop("mode", "lockstep"),
            "runs": extra.pop("runs", [{"pace_ms": 0}]),
            "limits": dict(LIMITS, **extra.pop("limits", {})),
            "steps": [],
            "expect": [],
            "tags": extra.pop("tags", []),
        }

    def step(self, kind: str, arg: object) -> int:
        """Append a step; returns its index."""
        self.raw["steps"].append({kind: arg})
        return len(self.raw["steps"]) - 1

    def dev(self, *cmds: tuple[str, dict]) -> int:
        """Append a DevConsole step; returns its index."""
        return self.step("dev", [[c, a] for c, a in cmds])

    def mark(self, name: str) -> None:
        """Remember the current frame under a name."""
        self.step("mark", name)

    def expect(
        self,
        eid: str,
        check: str,
        args: dict,
        rule: str,
        says: str,
        kind: str = "assert",
    ) -> None:
        """Append an expectation."""
        e = {"id": eid, "check": check, "args": args, "rule": rule, "says": says}
        if kind != "assert":
            e["kind"] = kind
        self.raw["expect"].append(e)

    def state_is(
        self, eid: str, mark: str, path: str, value: object, rule: str, says: str
    ) -> None:
        """A state-report value equals a value at a mark."""
        self.expect(
            eid,
            "state_value",
            {"mark": mark, "path": path, "equals": value},
            rule,
            says,
        )


def bad_input() -> Playtest:
    p = Playtest(
        "contract.devconsole/bad-input",
        ["AC-2", "EC-4"],
        "Commands with mistakes in them: an unknown command, wrong types, values out of range. "
        "Every answer keeps the contract's form, nothing changes, and the game goes on.",
        ["--role=solo", "--variation=3", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": True, "state": True, "every": 6})
    p.dev(("world.reset", {"variation": 3}))
    p.mark("before")
    bad = p.dev(
        ("no.such.command", {}),
        ("player.spawn", {"at": "nowhere"}),
        ("player.spawn", {"at": [1, 2]}),
        ("time.set", {"hhmm": "25:61"}),
        ("weather.set", {"kind": ["rain"]}),
        ("player.give", {"money": "lots"}),
        ("world.reset", {"variation": "x"}),
        ("load", {"slot": 9}),
        ("save", {"slot": -1.5}),
        ("vehicle.spawn", {"model": "hovercraft", "at": [0.0, 0.0, 0.0]}),
        ("npc.spawn", {"archetype": "office_worker", "at": {"poi": "no_such_place"}}),
        ("prop.spawn", {"kind": "crate", "at": [0.0, 0.0, 0.0], "size": "big"}),
        ("traffic.set", {"density": 7}),
        ("mission.start", {"id": "Z9"}),
    )
    p.step("run", 30)
    p.mark("after")
    still = p.dev(("state", {}))
    whole_v = p.dev(("world.reset", {"variation": 4.0}))
    whole_m = p.dev(("player.give", {"money": 100.0}))
    p.expect(
        "answers", "dev_answers", {"steps": [bad]}, "AC-2",
        'every command gets an answer {"ok": true, ...} or {"ok": false, "error": "..."}',
    )  # fmt: skip
    p.expect(
        "unknown_refused", "dev_result", {"step": bad, "index": 0, "equals": {"ok": False}}, "AC-2",
        "an unknown command is refused",
    )  # fmt: skip
    p.expect(
        "no_money_moves", "event_seen",
        {"name": "money_changed", "after": "before", "before": "after", "min_count": 0, "max_count": 0},
        "EC-4", "commands with mistakes move no money",
    )  # fmt: skip
    p.expect(
        "money_kept", "state_value", {"mark": "after", "path": "player.money", "equals": NEW_GAME_MONEY},
        "EC-4", "the new game's $500 are still there",
    )  # fmt: skip
    p.expect(
        "still_answers", "dev_result", {"step": still, "equals": {"ok": True}}, "AC-2",
        "the game keeps answering after the bad commands",
    )  # fmt: skip
    p.expect(
        "whole_float_variation", "dev_result", {"step": whole_v, "equals": {"ok": True}}, "AC-2",
        "a whole number sent as 4.0 is accepted",
    )  # fmt: skip
    p.expect(
        "whole_float_money", "dev_result", {"step": whole_m, "equals": {"ok": True}}, "AC-2",
        "a whole number of dollars sent as 100.0 is accepted",
    )  # fmt: skip
    return p


def commands() -> Playtest:
    p = Playtest(
        "contract.devconsole/commands",
        ["AC-3", "AC-13", "AC-14", "EC-4", "MS-12"],
        "Each DevConsole command does what chapter 17 says, at once, with the events it causes.",
        ["--role=solo", "--variation=2", "--save-dir={save_dir}"],
    )
    plaza = {"poi": "plaza_central"}
    crate_at = [12.0, 0.15, -2.0]
    lane = {"lane": "e_22_23:ab0", "s": 20.0}
    walk = {"sidewalk": "sw_33", "s": 15.0}
    p.step("observe", {"census": True, "state": True, "every": 6})
    p.dev(("world.reset", {"variation": 2}))
    p.mark("reset")
    p.dev(("time.set", {"hhmm": "21:30"}))
    p.mark("time")
    p.dev(("weather.set", {"kind": "fog"}))
    p.mark("weather")
    p.dev(("player.give", {"money": 250}))
    p.mark("money")
    p.dev(("player.give", {"weapon": "pistol", "ammo": 24}))
    p.mark("pistol")
    p.dev(("player.give", {"outfit": "street", "health": 40, "armour": 75}))
    p.mark("given")
    spawn = p.dev(("player.spawn", {"lead": "lead_2", "at": plaza}))
    p.mark("spawned")
    prop = p.dev(("prop.spawn", {"kind": "crate", "at": crate_at}))
    p.mark("prop")
    car = p.dev(("vehicle.spawn", {"model": "sedan", "at": lane}))
    p.mark("car")
    npc = p.dev(("npc.spawn", {"archetype": "shopper", "at": walk}))
    p.mark("npc")
    p.dev(
        (
            "npc.spawn",
            {
                "archetype": "tourist",
                "seat": {"vehicle": {"$answer": [car, "id"]}, "index": 1},
            },
        )
    )
    p.mark("passenger")
    drive = p.dev(
        ("vehicle.spawn", {"model": "hatchback", "at": "player", "driver": "player"})
    )
    p.mark("driving")
    p.dev(("traffic.set", {"density": 0.5}))
    p.dev(("mission.start", {"id": "D1", "stage": 2}))
    p.mark("mission")
    p.dev(("world.reset", {"variation": 2}))
    p.mark("reset_again")
    p.state_is(
        "reset_clock",
        "reset",
        "clock",
        "08:00",
        "AC-3",
        "world.reset sets the clock to 08:00",
    )
    p.state_is(
        "reset_weather",
        "reset",
        "weather",
        "clear",
        "AC-3",
        "world.reset sets clear weather",
    )
    p.state_is(
        "reset_variation",
        "reset",
        "variation",
        2,
        "AC-3",
        "world.reset builds the variation asked for",
    )
    p.state_is(
        "time_set",
        "time",
        "clock",
        "21:30",
        "AC-3",
        'time.set with "21:30" sets the clock at once',
    )
    p.state_is(
        "weather_set",
        "weather",
        "weather",
        "fog",
        "AC-3",
        "weather.set sets the weather at once",
    )
    p.state_is(
        "money_given", "money", "player.money", NEW_GAME_MONEY + 250, "AC-3",
        "player.give adds the money given ($500 + $250)",
    )  # fmt: skip
    p.expect(
        "money_event", "event_seen",
        {"name": "money_changed", "after": "weather", "before": "money",
         "where": {"amount": 250, "reason": "setup", "balance": NEW_GAME_MONEY + 250}},
        "EC-4", "money_changed announces it: amount 250, reason setup, balance 750",
    )  # fmt: skip
    p.expect(
        "pistol_owned", "state_value", {"mark": "pistol", "path": "player.weapons", "contains": "pistol"},
        "AC-3", "player.give makes the weapon owned",
    )  # fmt: skip
    p.expect(
        "outfit_owned", "state_value", {"mark": "given", "path": "player.outfits", "contains": "street"},
        "AC-3", "player.give makes the outfit owned",
    )  # fmt: skip
    p.state_is(
        "health_set", "given", "player.health", 40, "AC-3", "player.give sets health"
    )
    p.state_is(
        "armour_set", "given", "player.armour", 75, "AC-3", "player.give sets armour"
    )
    p.state_is(
        "lead_spawned",
        "spawned",
        "player.lead",
        "lead_2",
        "AC-3",
        "player.spawn plays the lead asked for",
    )
    p.expect(
        "player_placed", "entity_near",
        {"mark": "spawned", "kind": "player", "id_from": {"step": spawn}, "p": point(plaza), "max_m": PLACED_M},
        "AC-3", "player.spawn answers the player's id and puts the player at the anchor",
    )  # fmt: skip
    p.expect(
        "spawn_teleport", "event_seen",
        {"name": "teleport", "after": "given", "before": "spawned", "where": {"reason": "setup"}},
        "AC-14", "the move is announced by a teleport event with reason setup",
    )  # fmt: skip
    p.expect(
        "crate_placed", "entity_near",
        {"mark": "prop", "kind": "prop", "archetype": "crate", "id_from": {"step": prop},
         "p": crate_at, "max_m": PLACED_M},
        "AC-3", "prop.spawn answers the crate's id and puts it at the point",
    )  # fmt: skip
    p.expect(
        "car_placed", "entity_near",
        {"mark": "car", "kind": "vehicle", "archetype": "sedan", "id_from": {"step": car},
         "p": point(lane), "max_m": PLACED_M},
        "AC-3", "vehicle.spawn answers the car's id and puts it on the lane point",
    )  # fmt: skip
    p.expect(
        "npc_placed", "entity_near",
        {"mark": "npc", "kind": "npc", "archetype": "shopper", "id_from": {"step": npc},
         "p": point(walk), "max_m": PLACED_M},
        "AC-3", "npc.spawn answers the person's id and puts them on the sidewalk point",
    )  # fmt: skip
    p.expect(
        "passenger_seated", "event_seen",
        {"name": "vehicle_entered", "after": "npc", "before": "passenger", "where": {"seat": 1}},
        "AC-3", "npc.spawn with a seat puts the person in that seat (vehicle_entered, seat 1)",
    )  # fmt: skip
    p.expect(
        "driving_vehicle", "state_value",
        {"mark": "driving", "path": "player.vehicle", "equals_answer": {"step": drive}},
        "AC-3", "vehicle.spawn with driver player seats the player in the new vehicle",
    )  # fmt: skip
    p.state_is(
        "driving_seat",
        "driving",
        "player.seat",
        0,
        "AC-3",
        "the player drives (seat 0)",
    )
    p.expect(
        "mission_event", "event_seen",
        {"name": "mission", "after": "driving", "before": "mission",
         "where": {"id": "D1", "state": "active", "stage": 2}},
        "AC-3", "mission.start starts the mission at the stage asked for",
    )  # fmt: skip
    p.state_is(
        "mission_state", "mission", "missions.D1", {"state": "active", "stage": 2}, "MS-12",
        "state.missions reports D1 active at stage 2",
    )  # fmt: skip
    p.state_is(
        "reset_again_clock",
        "reset_again",
        "clock",
        "08:00",
        "AC-3",
        "world.reset sets 08:00 again",
    )
    p.state_is(
        "reset_again_weather",
        "reset_again",
        "weather",
        "clear",
        "AC-3",
        "and clear weather again",
    )
    return p


def state_report() -> Playtest:
    p = Playtest(
        "contract.devconsole/state-report",
        ["AC-12", "MS-12", "WD-14", "NT-1"],
        "The state report carries every field chapter 17 lists, on foot and at the wheel.",
        ["--role=solo", "--variation=5", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": True, "state": True, "every": 6})
    p.dev(("world.reset", {"variation": 5}))
    p.step("run", 6)
    p.mark("on_foot")
    p.dev(("vehicle.spawn", {"model": "suv", "at": "player", "driver": "player"}))
    p.step("run", 6)
    p.mark("driving")
    for mark in ("on_foot", "driving"):
        p.expect(
            f"fields_{mark}", "state_fields", {"mark": mark}, "AC-12",
            "the report has tick, map, clock, weather, variation, player, missions, garages, ui and network",
        )  # fmt: skip
    p.state_is(
        "role",
        "on_foot",
        "network.role",
        "solo",
        "NT-1",
        "a solo game reports role solo",
    )
    return p


def new_game() -> Playtest:
    p = Playtest(
        "contract.devconsole/new-game",
        ["AC-1", "EC-1", "CA-3", "MS-12", "UI-6"],
        "--role=solo starts a new game: lead_1 at the Downtown safehouse at 08:00 in clear "
        "weather, with $500, fists only, 100 health, no armour, and D1 the only mission offered.",
        ["--role=solo", "--variation=1", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": True, "state": True, "every": 1})
    p.step("run", 1)
    p.mark("start")
    for eid, path, value, rule, says in (
        (
            "money",
            "player.money",
            NEW_GAME_MONEY,
            "EC-1",
            "a new game starts with $500",
        ),
        ("fists_only", "player.weapons", ["fists"], "EC-1", "and fists only"),
        ("health", "player.health", 100, "EC-1", "100 health"),
        ("armour", "player.armour", 0, "EC-1", "no armour"),
        ("lead", "player.lead", "lead_1", "UI-6", "playing lead_1"),
        (
            "leads_unlocked",
            "player.leads_unlocked",
            ["lead_1"],
            "CA-3",
            "only lead_1 unlocked",
        ),
        ("clock", "clock", "08:00", "UI-6", "at 08:00"),
        ("weather", "weather", "clear", "UI-6", "in clear weather"),
        ("map", "map", "downtown", "UI-6", "in Downtown"),
        ("d1", "missions.D1.state", "available", "UI-6", "with D1 available"),
    ):
        p.state_is(eid, "start", path, value, rule, says)
    for m in ("C1", "R1", "D2", "C2", "R2", "H1", "H2"):
        p.state_is(
            f"locked_{m}",
            "start",
            f"missions.{m}.state",
            "locked",
            "MS-12",
            f"{m} locked until unlocked",
        )
    p.expect(
        "at_safehouse", "entity_near",
        {"mark": "start", "kind": "player", "p": point({"poi": "safehouse_downtown"}), "max_m": PLACED_M},
        "UI-6", "the new game starts at safehouse_downtown",
    )  # fmt: skip
    return p


def server_role() -> Playtest:
    p = Playtest(
        "contract.devconsole/server-role",
        ["AC-1", "NT-1", "PF-4"],
        "--role=server starts a dedicated server: it builds the world and reports role server.",
        ["--role=server", "--port=47031", "--variation=1", "--save-dir={save_dir}"],
        role="server",
    )
    p.step("observe", {"census": True, "state": True, "every": 6})
    p.step("run", 6)
    p.mark("up")
    p.state_is(
        "role", "up", "network.role", "server", "NT-1", "the server reports role server"
    )
    p.state_is("map", "up", "map", "downtown", "AC-1", "on the default map, Downtown")
    return p


def same_start() -> Playtest:
    p = Playtest(
        "world.same_start/variations",
        ["AC-16", "AC-1"],
        "The same variation gives the same starting population and another variation another "
        "one; --variation=7 starts the population world.reset builds for 7.",
        ["--role=solo", "--variation=7", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": True, "every": 6})
    p.step("run", 1)
    p.mark("boot")
    p.dev(("world.reset", {"variation": 7}))
    p.mark("a")
    p.step("run", 30)
    p.dev(("world.reset", {"variation": 7}))
    p.mark("b")
    p.step("run", 12)
    p.dev(("world.reset", {"variation": 8}))
    p.mark("c")
    p.step("run", 6)
    kinds = ["player", "npc", "vehicle"]
    p.expect(
        "same_start", "same_start", {"same": ["a", "b"], "different": ["a", "c"], "kinds": kinds},
        "AC-16", "the same variation number rebuilds the same starting population; 8 builds another",
    )  # fmt: skip
    p.expect(
        "variation_flag", "same_start", {"same": ["boot", "a"], "different": ["boot", "c"], "kinds": kinds},
        "AC-1", "--variation=7 starts the population of variation 7",
    )  # fmt: skip
    return p


def replay() -> Playtest:
    p = Playtest(
        "world.replay/two-paces",
        ["AC-15", "AC-17"],
        "One input timeline played twice, the second time with a pause between ticks as on a slower "
        "machine: the game does the same thing tick for tick.",
        ["--role=solo", "--variation=5", "--save-dir={save_dir}"],
        runs=[{"pace_ms": 0}, {"pace_ms": 4}],
        tags=["physics-sensitive"],
    )
    p.step(
        "observe",
        {
            "census": True,
            "every": 3,
            "bones": {
                "ids": ["player"],
                "names": ["Hips", "Head", "LeftToes", "RightHand"],
            },
        },
    )
    p.dev(("world.reset", {"variation": 5}))
    p.dev(("player.spawn", {"at": {"poi": "plaza_central"}, "heading": 90}))
    p.mark("start")
    p.step("press", {"move_forward": 0.4})
    p.step("run", 60)
    p.step("press", {"move_forward": 1.0, "look_left": 0.5})
    p.step("run", 45)
    p.step("press", {"sprint": 1.0})
    p.step("run", 30)
    p.step("release", ["move_forward", "look_left", "sprint"])
    p.step("press", {"move_right": 1.0})
    p.step("run", 30)
    p.step("release", ["move_right"])
    p.step("run", 60)
    p.mark("end")
    p.expect(
        "player_moves", "moved", {"from": "start", "to": "end", "kind": "player", "min_m": 1.0, "horizontal": True},
        "AC-17", "the player walks, runs and sprints during the timeline", "pre",
    )  # fmt: skip
    p.expect("replay", "replay_equal", {}, "AC-17", "both runs give the same trace")
    return p


def same_tick() -> Playtest:
    p = Playtest(
        "people.locomotion/same-tick",
        ["IN-3"],
        "An action pressed in physics tick t takes effect in tick t: the player moves in the "
        "tick move_forward is pressed.",
        ["--role=solo", "--variation=6", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": True, "every": 1})
    p.dev(("world.reset", {"variation": 6}))
    p.dev(("player.spawn", {"at": {"poi": "plaza_central"}, "heading": 0}))
    p.step("run", 30)
    p.mark("before")
    p.step("press", {"move_forward": 1.0})
    p.step("run", 1)
    p.mark("after")
    p.step("release", ["move_forward"])
    p.step("run", 1)
    p.expect(
        "same_tick", "moved",
        {"from": "before", "to": "after", "kind": "player", "ticks": 1, "min_m": 0.001, "horizontal": True},
        "IN-3", "the player moves within the tick the action is pressed",
    )  # fmt: skip
    return p


def clock_rate() -> Playtest:
    p = Playtest(
        "world.clock_lights/rate",
        ["WD-11"],
        "Game time runs one minute per second of play: an hour of game time in 3,600 ticks, "
        "within 1%.",
        ["--role=solo", "--variation=1", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": False, "state": True, "every": 60})
    p.dev(("world.reset", {"variation": 1}))
    p.dev(("time.set", {"hhmm": "10:00"}))
    p.mark("start")
    p.step("run", 3600)
    p.mark("hour")
    p.state_is(
        "set", "start", "clock", "10:00", "WD-11", "time.set changes the clock at once"
    )
    p.expect(
        "rate", "state_value", {"mark": "hour", "path": "clock", "as": "minutes", "min": 659, "max": 660},
        "WD-11", "60 seconds of play later the clock reads 10:59 or 11:00 (60 minutes within 1%)",
    )  # fmt: skip
    return p


def weather_hold() -> Playtest:
    p = Playtest(
        "world.weather/set-and-hold",
        ["WD-14"],
        "Weather changes only when set, and the state report says which it is.",
        ["--role=solo", "--variation=1", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": False, "state": True, "every": 30})
    p.dev(("world.reset", {"variation": 1}))
    p.mark("reset")
    p.dev(("weather.set", {"kind": "rain"}))
    p.mark("rain")
    p.step("run", 1800)
    p.mark("rain_held")
    p.dev(("weather.set", {"kind": "overcast"}))
    p.dev(("time.set", {"hhmm": "23:45"}))
    p.mark("overcast")
    p.step("run", 1800)
    p.mark("past_midnight")
    p.state_is(
        "clear_after_reset",
        "reset",
        "weather",
        "clear",
        "WD-14",
        "clear after world.reset",
    )
    p.state_is("rain", "rain", "weather", "rain", "WD-14", "rain once set")
    p.state_is(
        "rain_held",
        "rain_held",
        "weather",
        "rain",
        "WD-14",
        "still rain half an hour of game time later",
    )
    p.state_is(
        "overcast", "overcast", "weather", "overcast", "WD-14", "overcast once set"
    )
    p.state_is(
        "overcast_held", "past_midnight", "weather", "overcast", "WD-14", "still overcast past midnight"
    )  # fmt: skip
    return p


def kill_after_save() -> Playtest:
    p = Playtest(
        "persistence.round_trip/kill-after-save",
        ["SV-1", "SV-3", "SV-4", "SV-6"],
        "Once saved fires, killing the process leaves the slot loadable with what was saved.",
        ["--role=solo", "--variation=4", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": True, "state": True, "every": 6})
    p.dev(("world.reset", {"variation": 4}))
    p.dev(("player.give", {"money": 300}))
    p.dev(("player.give", {"weapon": "bat"}))
    p.dev(("save", {"slot": 3}))
    p.step("wait_for", {"event": "saved", "max_ticks": 120})
    p.step("restart", {})
    loads = p.dev(("load", {"slot": 3}))
    p.step("run", 6)
    p.mark("loaded")
    p.expect(
        "saved", "event_seen", {"name": "saved", "min_count": 1}, "SV-1", "the save fires saved", "pre"
    )  # fmt: skip
    p.expect(
        "loads",
        "dev_result",
        {"step": loads, "equals": {"ok": True}},
        "SV-4",
        "slot 3 loads after the kill",
    )
    p.state_is(
        "money_kept", "loaded", "player.money", NEW_GAME_MONEY + 300, "SV-3", "the money saved comes back ($800)"
    )  # fmt: skip
    p.expect(
        "weapon_kept", "state_value", {"mark": "loaded", "path": "player.weapons", "contains": "bat"},
        "SV-3", "and the weapons saved",
    )  # fmt: skip
    p.expect(
        "loaded_event",
        "event_seen",
        {"name": "loaded", "min_count": 1},
        "AC-13",
        "loading fires loaded",
    )
    return p


def damaged_slot() -> Playtest:
    p = Playtest(
        "persistence.round_trip/damaged-slot",
        ["SV-5", "SV-6"],
        'A damaged save file does not crash the game: loading it answers "Slot 2 is damaged", '
        "the game keeps answering, and another slot still loads.",
        ["--role=solo", "--variation=2", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": True, "state": True, "every": 6})
    p.dev(("world.reset", {"variation": 2}))
    p.dev(("player.give", {"money": 250}))
    p.dev(("save", {"slot": 1}))
    p.mark("before_second")
    p.dev(("player.give", {"money": 100}))
    p.dev(("save", {"slot": 2}))
    p.step("files", {"op": "damage", "since": "before_second"})
    damaged = p.dev(("load", {"slot": 2}))
    p.step("run", 30)
    still = p.dev(("state", {}))
    other = p.dev(("load", {"slot": 1}))
    p.step("run", 6)
    p.mark("after")
    p.expect(
        "saved", "event_seen", {"name": "saved", "min_count": 2}, "SV-1", "both saves fire saved", "pre"
    )  # fmt: skip
    p.expect(
        "damaged_refused", "dev_result",
        {"step": damaged, "equals": {"ok": False}, "contains": {"error": "Slot 2 is damaged"}},
        "SV-5", 'loading the damaged slot answers "Slot 2 is damaged"',
    )  # fmt: skip
    p.expect(
        "still_answers", "dev_result", {"step": still, "equals": {"ok": True}}, "SV-5",
        "the game stays responsive",
    )  # fmt: skip
    p.expect(
        "other_slot", "dev_result", {"step": other, "equals": {"ok": True}}, "SV-5", "slot 1 still loads"
    )  # fmt: skip
    p.state_is(
        "restored", "after", "player.money", NEW_GAME_MONEY + 250, "SV-6",
        "slot 1's money comes back from the save folder given ($750)",
    )  # fmt: skip
    return p


def realtime() -> Playtest:
    p = Playtest(
        "inv.telemetry/realtime",
        ["AC-18"],
        "Played in real time, the game keeps QA's telemetry node ticking with it.",
        ["--role=solo", "--variation=9", "--save-dir={save_dir}"],
        mode="realtime",
        limits={"heartbeat_gap_s": 1.0},
    )
    p.step("observe", {"census": True, "every": 30})
    p.step("wait_s", 1.5)
    p.mark("start")
    p.step("press", {"move_forward": 1.0})
    p.step("wait_s", 1.0)
    p.step("release", ["move_forward"])
    p.step("wait_s", 0.5)
    p.mark("end")
    p.expect(
        "player_moves", "moved", {"from": "start", "to": "end", "kind": "player", "min_m": 0.5, "horizontal": True},
        "AC-18", "the player runs while QA watches in real time", "pre",
    )  # fmt: skip
    p.expect(
        "heartbeat", "heartbeat", {"max_gap_s": 1.0}, "AC-18", "a heartbeat every tick, no silence over 1 s"
    )  # fmt: skip
    return p


def plan_compliance() -> Playtest:
    p = Playtest(
        "world.plan_compliance/downtown",
        ["WD-1", "WD-2", "WD-3", "WD-4", "WD-5", "AC-8"],
        "QA casts rays over the whole of Downtown: along every lane and sidewalk, across every "
        "crosswalk, over every parcel, through every door and room, and down onto every point "
        "of interest. What they hit has the plan's heights and the surface tags of chapter 17.",
        ["--role=solo", "--variation=1", "--save-dir={save_dir}"],
        limits={"step_s": 60},
    )
    rays = Probes(json.loads(PLAN_FILE.read_text())).build()
    p.step("observe", {"census": False, "every": 30})
    p.step("run", 30)
    step = p.step("query", rays.queries)
    p.step("run", 1)
    for e in rays.expects:
        p.expect(e["id"], e["check"], dict(e["args"], step=step), e["rule"], e["says"])
    return p


# Chapter 5 (FT-1, FT-2, FT-6), chapter 4 (IN-2, CM-1 to CM-3), chapter 2 (CA-1, CA-2).
PACES = {
    "walk": (0.80, 1.50),
    "run": (4.60, 6.40),
    "sprint": (7.40, 9.60),
    "crouched": (0.50, 1.10),
}
SLIDE = {"walk": 0.25, "run": 0.40, "sprint": 0.60}
ASPECT = 1280 / 720  # the window the project sets (display/window/size)
PLAZA = {"poi": "plaza_central"}
LEAD_BONES = [
    "Hips", "Spine", "Chest", "Neck", "Head", "LeftUpperArm", "LeftHand", "LeftUpperLeg",
    "LeftFoot", "LeftToes", "RightUpperArm", "RightHand", "RightUpperLeg", "RightFoot",
    "RightToes",
]  # fmt: skip


def lead_table() -> dict[str, dict]:
    """Chapter 2's table of leads, read from the design document."""
    text = (TASK / "common" / "design" / "GDD.md").read_text()
    out = {}
    for line in text.splitlines():
        if line.startswith("| `lead_"):
            cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
            out[cells[0]] = dict(
                zip(
                    ("body", "hair", "skin", "top", "bottom", "shoes"),
                    cells[2:8],
                    strict=True,
                )
            )
    return out


def gait_segment(
    p: Playtest, name: str, press: dict, settle: int, measure: int
) -> None:
    """Spawn at the plaza, hold the actions, let the gait settle, mark, measure, mark."""
    p.dev(("player.spawn", {"at": PLAZA, "heading": 90}))
    p.step("press", press)
    p.step("run", settle)
    p.mark(f"{name}_a")
    p.step("run", measure)
    p.mark(f"{name}_b")
    p.step("release", sorted(press))


def paces() -> Playtest:
    p = Playtest(
        "people.locomotion/paces",
        ["FT-1", "IN-2"],
        "On the level plaza the player walks, runs and sprints: QA presses move_forward at "
        "different strengths (and sprint), lets each gait settle for 1.5 s, and measures the "
        "horizontal speed of the hips over the next second.",
        ["--role=solo", "--variation=2", "--save-dir={save_dir}"],
    )
    p.step(
        "observe",
        {"census": True, "every": 6, "bones": {"ids": ["player"], "names": ["Hips"]}},
    )
    p.dev(("world.reset", {"variation": 2}))
    segments = [
        ("walk", {"move_forward": 0.3}, "walk", "FT-1", "at a walk the hips move at 0.80-1.50 m/s"),
        ("half", {"move_forward": 0.5}, "walk", "IN-2", "a move strength of 0.5 still walks"),
        ("over_half", {"move_forward": 0.6}, "run", "IN-2", "a move strength above 0.5 runs"),
        ("run", {"move_forward": 1.0}, "run", "FT-1", "running, the hips move at 4.60-6.40 m/s"),
        ("sprint", {"move_forward": 1.0, "sprint": 1.0}, "sprint", "FT-1",
         "sprinting, the hips move at 7.40-9.60 m/s"),
    ]  # fmt: skip
    for name, press, _, _, _ in segments:
        gait_segment(p, name, press, 90, 60)
    for name, _, gait, rule, says in segments:
        lo, hi = PACES[gait]
        p.expect(
            f"pace_{name}", "pace",
            {"from": f"{name}_a", "to": f"{name}_b", "kind": "player", "bone": "Hips",
             "min_mps": lo, "max_mps": hi},
            rule, says,
        )  # fmt: skip
    p.expect(
        "sprint_while_running", "pace",
        {"from": "sprint_a", "to": "sprint_b", "kind": "player", "bone": "Hips",
         "min_mps": PACES["sprint"][0]},
        "IN-2", "sprint held while running sprints: the hips reach FT-1's sprint pace, 7.40 m/s",
    )  # fmt: skip
    return p


def camera() -> Playtest:
    p = Playtest(
        "people.locomotion/camera",
        ["CM-1", "CM-2", "CM-3"],
        "On foot on the plaza: the camera's distance from the head and where the hips sit in "
        "the view while the player stands, turns the camera, tilts it up and down, and walks; "
        "how fast look_right turns it; and that move_forward follows the camera.",
        ["--role=solo", "--variation=3", "--save-dir={save_dir}"],
    )
    p.step(
        "observe",
        {"census": True, "camera": True, "every": 2,
         "bones": {"ids": ["player"], "names": ["Head", "Hips"]}},
    )  # fmt: skip
    p.dev(("world.reset", {"variation": 3}))
    p.dev(("player.spawn", {"at": PLAZA, "heading": 0}))
    p.step("run", 30)
    p.mark("start")
    p.step("run", 30)
    p.step("press", {"look_right": 1.0})
    p.step("run", 6)
    p.mark("turn_a")
    p.step("run", 30)
    p.mark("turn_b")
    p.step("release", ["look_right"])
    p.step("run", 6)
    p.mark("tilt_a")
    p.step("press", {"look_up": 1.0})
    p.step("run", 120)
    p.mark("tilt_top")
    p.step("release", ["look_up"])
    p.step("press", {"look_down": 1.0})
    p.step("run", 180)
    p.mark("tilt_bottom")
    p.step("release", ["look_down"])
    p.step("press", {"look_up": 1.0})
    p.step("run", 60)
    p.mark("tilt_up")
    p.step("release", ["look_up"])
    p.step("run", 6)
    p.mark("move_a")
    p.step("press", {"move_forward": 1.0})
    p.step("run", 60)
    p.mark("move_b")
    p.step("release", ["move_forward"])
    p.step("run", 6)
    p.mark("end")
    p.expect(
        "camera_frame", "camera_frame",
        {"from": "start", "to": "end", "kind": "player", "min_m": 2.5, "max_m": 6.0,
         "middle": 0.4, "aspect": round(ASPECT, 4)},
        "CM-1",
        "on foot the camera stays 2.5-6.0 m from the player's Head bone and the Hips bone "
        "stays inside the middle 40% of the 1280 x 720 view, by width and height",
    )  # fmt: skip
    p.expect(
        "look_rate", "look_rate",
        {"from": "turn_a", "to": "turn_b", "min_dps": 120, "max_dps": 240},
        "CM-2", "look_right at full strength turns the camera at 120-240 degrees per second",
    )  # fmt: skip
    p.expect(
        "tilt_range", "camera_tilt",
        {"from": "tilt_a", "to": "tilt_up", "min_deg": -60, "max_deg": 30},
        "CM-2",
        "while look_up and look_down are held the camera's pitch (positive looking up) stays "
        "between -60 and +30 degrees",
    )  # fmt: skip
    p.expect(
        "tilt_down", "camera_tilt",
        {"from": "tilt_top", "to": "tilt_bottom", "min_deg": -60, "max_deg": 30, "falls": True,
         "min_change_deg": 1.0},
        "CM-2", "after look_up has been held, holding look_down tilts the camera down",
    )  # fmt: skip
    p.expect(
        "tilt_up", "camera_tilt",
        {"from": "tilt_bottom", "to": "tilt_up", "min_deg": -60, "max_deg": 30, "rises": True,
         "min_change_deg": 1.0},
        "CM-2", "after look_down has been held, holding look_up tilts the camera up",
    )  # fmt: skip
    p.expect(
        "moves_along_camera", "moves_along_camera",
        {"from": "move_a", "to": "move_b", "kind": "player", "within_deg": 15},
        "CM-3",
        "move_forward moves the player within 15 degrees of the camera's horizontal forward",
    )  # fmt: skip
    return p


def lineup() -> Playtest:
    p = Playtest(
        "people.lineup/leads",
        ["CA-1", "CA-2", "AC-5", "AC-11", "AR-3"],
        "Each of the six leads in turn on the plaza: its look matches chapter 2's table, the "
        "leads differ from each other, and each has one Skeleton3D with the humanoid profile's "
        "bone names and a skinned body bound to it.",
        ["--role=solo", "--variation=4", "--save-dir={save_dir}"],
    )
    p.step("observe", {"census": {"meta": ["look"]}, "every": 6})
    p.dev(("world.reset", {"variation": 4}))
    table = lead_table()
    marks = []
    for lead in sorted(table):
        spawn = p.dev(("player.spawn", {"lead": lead, "at": PLAZA}))
        p.step("run", 6)
        p.mark(lead)
        marks.append(lead)
        sk = p.step(
            "query",
            [{"id": "skeleton", "type": "skeleton", "entity": {"$answer": [spawn, "id"]}},
             {"id": "unregistered", "type": "unregistered"}],
        )  # fmt: skip
        p.expect(
            f"look_{lead}", "look",
            {"mark": lead, "kind": "player", "expect": dict(table[lead], scale=1.0),
             "colour_tol": 0.02},
            "CA-1",
            f"{lead} is spawned with chapter 2's body, hair and colours (within 0.02 per "
            "channel) at scale 1.0, and its look metadata has every field of AC-11",
        )  # fmt: skip
        p.expect(
            f"skeleton_{lead}", "skeleton",
            {"step": sk, "query": "skeleton", "bones": LEAD_BONES, "min_bound_meshes": 1},
            "AC-5",
            f"{lead} has exactly one Skeleton3D using the humanoid profile's bone names, with "
            "skinned meshes bound to it",
        )  # fmt: skip
        if lead == "lead_1":
            p.expect(
                "unregistered", "none_listed", {"step": sk, "query": "unregistered"}, "AC-5",
                "nothing outside the entity registry has a Skeleton3D, CharacterBody3D or "
                "VehicleBody3D",
            )  # fmt: skip
            p.expect(
                "look_fields", "look", {"mark": lead, "kind": "player", "expect": {}}, "AC-11",
                "the player's look metadata has body, hair, skin, top, bottom, shoes, "
                "hair_colour, props and scale",
            )  # fmt: skip
            p.expect(
                "lead_scale", "look", {"mark": lead, "kind": "player", "expect": {"scale": 1.0}},
                "AR-3", "a lead is shown at scale 1.0",
            )  # fmt: skip
    p.expect(
        "leads_distinct", "looks_distinct", {"marks": marks, "kind": "player", "min_top_distance": 0.2},
        "CA-2", "any two leads differ in body or hair, and their tops by at least 0.20",
    )  # fmt: skip
    return p


def feet() -> Playtest:
    p = Playtest(
        "people.locomotion/feet",
        ["FT-2"],
        "Walking, running and sprinting on the plaza, the feet are planted: steps alternate "
        "between the feet, and a planted toe barely slides. A stance is a run of samples with "
        "the toe within 0.04 m of its lowest height; slide is measured over its middle 60%.",
        ["--role=solo", "--variation=5", "--save-dir={save_dir}"],
    )
    p.step(
        "observe",
        {"census": True, "every": 2,
         "bones": {"ids": ["player"], "names": ["LeftToes", "RightToes"]}},
    )  # fmt: skip
    p.dev(("world.reset", {"variation": 5}))
    gaits = [
        ("walk", {"move_forward": 0.3}),
        ("run", {"move_forward": 1.0}),
        ("sprint", {"move_forward": 1.0, "sprint": 1.0}),
    ]
    for name, press in gaits:
        gait_segment(p, name, press, 90, 240 if name == "walk" else 180)
    for name, _ in gaits:
        p.expect(
            f"feet_{name}", "feet",
            {"from": f"{name}_a", "to": f"{name}_b", "kind": "player", "min_steps": 3,
             "min_alternation": 0.9, "max_slide_mps": SLIDE[name], "contact_m": 0.04},
            "FT-2",
            f"at a {name} at least 90% of steps alternate feet and a planted toe slides at "
            f"most {SLIDE[name]:.2f} m/s (p95, middle 60% of each stance)",
        )  # fmt: skip
    return p


def crouch() -> Playtest:
    p = Playtest(
        "people.locomotion/crouch",
        ["FT-6", "FT-1"],
        "crouch toggles crouching: crouched, the hips are at most 75% of their standing height "
        "above the plaza, and a crouched walk moves at 0.50-1.10 m/s.",
        ["--role=solo", "--variation=6", "--save-dir={save_dir}"],
    )
    p.step(
        "observe",
        {"census": True, "every": 6, "bones": {"ids": ["player"], "names": ["Hips"]}},
    )
    p.dev(("world.reset", {"variation": 6}))
    p.dev(("player.spawn", {"at": PLAZA, "heading": 90}))
    p.step("run", 60)
    p.mark("standing")
    p.step("press", {"crouch": 1.0})
    p.step("run", 2)
    p.step("release", ["crouch"])
    p.step("run", 60)
    p.mark("crouched")
    p.step("press", {"move_forward": 0.3})
    p.step("run", 90)
    p.mark("crouch_walk_a")
    p.step("run", 60)
    p.mark("crouch_walk_b")
    p.step("release", ["move_forward"])
    plaza_y = point(PLAZA)[1]
    p.expect(
        "crouch_height", "hips_ratio",
        {"standing": "standing", "crouched": "crouched", "kind": "player", "bone": "Hips",
         "ground_y": plaza_y, "max_ratio": 0.75},
        "FT-6", "after crouch is pressed once, the hips are at most 75% of their standing height",
    )  # fmt: skip
    lo, hi = PACES["crouched"]
    p.expect(
        "crouch_pace", "pace",
        {"from": "crouch_walk_a", "to": "crouch_walk_b", "kind": "player", "bone": "Hips",
         "min_mps": lo, "max_mps": hi},
        "FT-1", "a crouched walk moves the hips at 0.50-1.10 m/s",
    )  # fmt: skip
    return p


# Chapter 5 (FT-3 to FT-5) and CM-4, with props placed by prop.spawn: a prop stands on its
# `at` point (the middle of its base); its size is [width, height, depth], its depth along
# its heading.
BODY_BONES = [
    "Hips", "Spine", "Chest", "Neck", "Head", "LeftUpperArm", "LeftLowerArm", "LeftHand",
    "RightUpperArm", "RightLowerArm", "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
    "LeftToes", "RightUpperLeg", "RightLowerLeg", "RightFoot", "RightToes",
]  # fmt: skip
NO_DEEPER_M = 0.05  # FT-4, FT-5: no bone more than 0.05 m into the obstacle


def prop_box(at: list[float], size: list[float], heading: float) -> dict:
    """The box a prop placed at `at` with `size` and `heading` fills."""
    return {"p": [round(c, 3) for c in at], "size": size, "heading": heading}


def jump_climb_vault() -> Playtest:
    p = Playtest(
        "people.jump_climb_vault/plaza",
        ["FT-3", "FT-4", "FT-5", "CM-4"],
        "On the plaza: a jump from standing; walking into a 1.2 m and a 2.2 m ledge and "
        "pressing jump; running at a 0.8 m barrier and pressing jump 1.2 m before it; then "
        "standing 2 m in front of a wall with the camera behind it, turning the camera and "
        "backing towards the wall. QA reads the bones every tick and checks them against "
        "each prop.",
        ["--role=solo", "--variation=8", "--save-dir={save_dir}"],
        limits={"step_s": 60},
    )
    x0, y0, z0 = point(PLAZA)
    light = {"census": True, "every": 6}
    dense = {"census": True, "camera": True, "every": 1,
             "bones": {"ids": ["player"], "names": BODY_BONES}}  # fmt: skip
    p.step("observe", light)
    p.dev(("world.reset", {"variation": 8}))
    # FT-3: a jump from standing on the level plaza
    p.dev(("player.spawn", {"at": [x0, y0, z0], "heading": 0}))
    p.step("run", 30)
    p.step("observe", dense)
    p.step("run", 1)
    p.mark("jump_a")
    p.step("press", {"jump": 1.0})
    p.step("run", 2)
    p.step("release", ["jump"])
    p.step("run", 70)
    p.mark("jump_b")
    p.step("observe", light)
    p.expect(
        "jump", "jump",
        {"from": "jump_a", "to": "jump_b", "kind": "player", "bone": "Hips", "off_m": 0.02,
         "min_rise_m": 0.40, "max_rise_m": 0.80, "min_air_s": 0.50, "max_air_s": 0.90},
        "FT-3",
        "jump from standing lifts the hips 0.40-0.80 m and keeps the player off the ground "
        "(more than 0.02 m above it) for 0.50-0.90 s",
    )  # fmt: skip
    # FT-4: walk into a ledge 2 m ahead, then press jump
    for name, dx, height in (("climb_low", -15.0, 1.2), ("climb_high", -30.0, 2.2)):
        at = [x0 + dx, y0, z0 - 3.0]
        size = [4.0, height, 2.0]
        p.dev(("prop.spawn", {"kind": "wall", "at": at, "size": size, "heading": 0}))
        p.dev(("player.spawn", {"at": [x0 + dx, y0, z0], "heading": 0}))
        p.step("press", {"move_forward": 0.3})
        p.step("run", 120)
        p.step("observe", dense)
        p.step("run", 1)
        p.mark(f"{name}_a")
        p.step("press", {"jump": 1.0})
        p.step("run", 2)
        p.step("release", ["jump", "move_forward"])
        p.step("run", 240)
        p.mark(f"{name}_b")
        p.step("observe", light)
        top = round(y0 + height, 3)
        edge = [[round(x0 + dx - 2.0, 3), top, round(z0 - 2.0, 3)],
                [round(x0 + dx + 2.0, 3), top, round(z0 - 2.0, 3)]]  # fmt: skip
        p.expect(
            name, "climb",
            {"from": f"{name}_a", "to": f"{name}_b", "kind": "player",
             "box": prop_box(at, size, 0), "edge": edge, "within_s": 3.5, "hand_m": 0.35,
             "on_top_m": 0.10, "max_into_m": NO_DEEPER_M},
            "FT-4",
            f"walking into a {height} m ledge and pressing jump climbs on top within 3.5 s; a "
            "hand comes within 0.35 m of the top edge while the hips are below it, and no bone "
            "goes more than 0.05 m into the ledge",
        )  # fmt: skip
    # FT-5: run at a barrier and press jump 1.2 m before it
    at = [x0 + 15.0, y0, z0 - 8.0]
    size = [3.0, 0.8, 0.4]
    face = [round(x0 + 15.0, 3), y0, round(z0 - 8.0 + 0.2, 3)]
    p.dev(("prop.spawn", {"kind": "barrier", "at": at, "size": size, "heading": 0}))
    p.dev(("player.spawn", {"at": [x0 + 15.0, y0, z0], "heading": 0}))
    p.step("press", {"move_forward": 1.0})
    p.step("observe", dense)
    p.step(
        "wait_for",
        {"near": {"kind": "player", "p": face, "within_m": 1.2}, "max_ticks": 240},
    )
    p.mark("vault_a")
    p.step("press", {"jump": 1.0})
    p.step("run", 2)
    p.step("release", ["jump"])
    p.step("run", 70)
    p.mark("vault_b")
    p.step("release", ["move_forward"])
    p.step("observe", light)
    p.expect(
        "vault_press", "entity_near",
        {"mark": "vault_a", "kind": "player", "p": face, "max_m": 1.5},
        "FT-5", "jump is pressed while the player runs at the barrier, 1.0-1.5 m before it", "pre",
    )  # fmt: skip
    p.expect(
        "vault", "vault",
        {"from": "vault_a", "to": "vault_b", "kind": "player", "box": prop_box(at, size, 0),
         "within_s": 1.2, "clear_m": 0.10, "max_into_m": NO_DEEPER_M},
        "FT-5",
        "running at a 0.8 m barrier and pressing jump takes the player over it within 1.2 s, "
        "the hips at least 0.10 m above its top while crossing, no bone more than 0.05 m into it",
    )  # fmt: skip
    # CM-4: a wall 2 m behind the player, the camera turned and the player backing towards it
    at = [x0, y0, z0 + 17.0]
    size = [8.0, 3.0, 0.4]
    p.dev(("prop.spawn", {"kind": "wall", "at": at, "size": size, "heading": 0}))
    p.dev(("player.spawn", {"at": [x0, y0, z0 + 15.0], "heading": 0}))
    p.step("run", 30)
    p.step("observe", dense)
    p.step("run", 1)
    p.mark("wall_a")
    for action, ticks in (("look_left", 60), ("look_right", 120), ("move_back", 60)):
        p.step("press", {action: 1.0 if action != "move_back" else 0.3})
        p.step("run", ticks)
        p.step("release", [action])
    p.mark("wall_b")
    p.step("observe", light)
    p.expect(
        "camera_clear", "camera_clear",
        {"from": "wall_a", "to": "wall_b", "kind": "player", "boxes": [prop_box(at, size, 0)],
         "min_share": 0.99},
        "CM-4",
        "with a wall behind the player, the segment from the Head bone to the camera misses "
        "the wall in at least 99% of ticks",
    )  # fmt: skip
    return p


def falls() -> Playtest:
    p = Playtest(
        "people.fall_ragdoll/falls",
        ["FT-8", "FT-9"],
        "The player walks off towers 2.4, 6, 10 and 16 m high on the plaza: a fall of under 3 m "
        "costs no health, one from 3 m to 15 m costs 100 * (h - 3) / 12 (within 10%), and 15 m "
        "or more kills. Landing from 10 m and from 16 m the body goes limp at once (the limp "
        "metadata) and moves under physics with no bone under the ground; from 10 m the player "
        "gets up within 6 s. Then the player walks off a fifth tower, 16 m, and is killed 1.5 m "
        "into the fall: limp in mid-air, the hips fall at g within 20%. QA reads the health 12 s "
        "after each walk starts, time enough to land and get up, and sets it back to 100 before "
        "each tower.",
        ["--role=solo", "--variation=10", "--save-dir={save_dir}"],
        limits={"step_s": 60},
    )
    x0, y0, z0 = point(PLAZA)
    light = {"census": {"meta": ["limp"]}, "state": True, "every": 6,
             "bones": {"ids": ["player"], "names": ["Hips"]}}  # fmt: skip
    dense = {"census": {"meta": ["limp"], "kinds": ["player"]}, "state": True, "every": 1,
             "bones": {"ids": ["player"], "names": BODY_BONES}}  # fmt: skip
    p.step("observe", light)
    p.dev(("world.reset", {"variation": 10}))
    towers = []
    for k, height in enumerate((2.4, 6.0, 10.0, 16.0, 16.0)):
        at = [round(x0 - 30.0 + 20.0 * k, 3), y0, round(z0 + 20.0, 3)]
        towers.append(prop_box(at, [4.0, height, 4.0], 0))
        p.dev(
            (
                "prop.spawn",
                {"kind": "tower", "at": at, "size": [4.0, height, 4.0], "heading": 0},
            )
        )
        p.dev(("player.give", {"health": 100}))
        p.dev(
            (
                "player.spawn",
                {"at": [at[0], round(y0 + height, 3), at[2]], "heading": 0},
            )
        )
        p.step("run", 30)
        name = f"tower_{k + 1}"
        if k >= 2:
            p.step("observe", dense)
        p.mark(f"{name}_top")
        p.step("press", {"move_forward": 0.3})
        if k == 4:
            # killed 1.5 m into the fall (CB-7: health 0 is death)
            p.step("wait_for", {"entity": {"kind": "player", "below_y": round(y0 + height - 1.5, 3)},
                                "max_ticks": 300})  # fmt: skip
            p.step("release", ["move_forward"])
            p.dev(("player.give", {"health": 0}))
            p.step("run", 600)
        else:
            p.step("run", 150)
            p.step("release", ["move_forward"])
            p.step("run", 570)
        p.mark(f"{name}_down")
        if k >= 2:
            p.step("observe", light)
        if k == 4:
            continue
        lost = (
            "nothing"
            if height < 3
            else (
                "all of it" if height >= 15 else f"{100 * (height - 3) / 12:.1f} health"
            )
        )
        p.expect(
            f"fall_{k + 1}", "fall_damage",
            {"from": f"{name}_top", "to": f"{name}_down", "kind": "player", "safe_m": 3.0,
             "fatal_m": 15.0, "tol": 0.1},
            "FT-8", f"walking off a {height} m tower costs {lost}",
        )  # fmt: skip
    p.expect(
        "fall_kills", "event_seen",
        {"after": "tower_4_top", "before": "tower_4_down", "name": "died"},
        "FT-8", "a fall of 15 m or more kills: the player's died event",
    )  # fmt: skip
    ground = {"ground_y": y0, "boxes": towers}
    p.expect(
        "ragdoll_10", "ragdoll",
        {"from": "tower_3_top", "to": "tower_3_down", "kind": "player",
         "trigger": {"landing_y": y0, "near_m": 0.25}, "within_ticks": 12, "min_s": 1.0,
         "below_m": 0.05, "step_m": 1.0, **ground},
        "FT-9",
        "landing from 10 m the player goes limp within 0.2 s (its limp metadata, the state "
        "report's player.limp the same) and stays limp at least 1.0 s; meanwhile no bone is more "
        "than 0.05 m under the ground and the hips never move more than 1 m in a tick",
    )  # fmt: skip
    p.expect(
        "get_up_10", "get_up",
        {"from": "tower_3_top", "to": "tower_3_down", "kind": "player", "ground_y": y0,
         "within_s": 6.0, "ratio": 0.9},
        "FT-9",
        "still alive after the 10 m fall, the player gets up within 6.0 s of going limp: limp "
        "false and the hips back to at least 90% of their standing height",
    )  # fmt: skip
    p.expect(
        "ragdoll_16", "ragdoll",
        {"from": "tower_4_top", "to": "tower_4_down", "kind": "player",
         "trigger": {"event": "died"}, "within_ticks": 12, "min_s": 1.0, "below_m": 0.05,
         "step_m": 1.0, **ground},
        "FT-9",
        "killed by the 16 m fall, the player goes limp within 0.2 s of the died event and stays "
        "limp; no bone is more than 0.05 m under the ground",
    )  # fmt: skip
    p.expect(
        "midair_died", "event_seen",
        {"after": "tower_5_top", "before": "tower_5_down", "name": "died"},
        "CB-7", "health set to 0 in mid-fall kills: the player's died event", "pre",
    )  # fmt: skip
    p.expect(
        "ragdoll_midair", "ragdoll",
        {"from": "tower_5_top", "to": "tower_5_down", "kind": "player",
         "trigger": {"event": "died"}, "within_ticks": 12, "min_s": 1.0, "below_m": 0.05,
         "step_m": 1.0, **ground},
        "FT-9",
        "killed 1.5 m into a 16 m fall, the player goes limp in mid-air within 0.2 s and stays "
        "limp; no bone goes more than 0.05 m under the ground on landing",
    )  # fmt: skip
    p.expect(
        "free_fall", "free_fall",
        {"from": "tower_5_top", "to": "tower_5_down", "kind": "player", "ground_y": y0,
         "clear_m": 0.3, "tol": 0.2, "min_ticks": 10},
        "FT-9",
        "limp in mid-air, the hips fall under physics: a parabola fitted to their height while "
        "every bone is at least 0.3 m above the ground gives 9.81 m/s^2 within 20%",
    )  # fmt: skip
    return p


# Chapter 6: vehicles. The handling table is read from the design document itself.
GDD_FILE = TASK / "common" / "design" / "GDD.md"
VEHICLE_KINDS = ["player", "vehicle"]
DRIVE_BONES = ["Hips", "Head", "LeftHand", "RightHand"]
# The proving runs (chapter 6: level dry asphalt, a road or a parking lot): the north-south
# arterial's lanes towards the south, and the parking lot north-east of the plaza.
DRY_LANE = {"lane": "e_30_31:ab0", "s": 8}
HANDBRAKE_LANE = {"lane": "e_32_33:ab0", "s": 8}
PAD = [29.25, 0.15, 135.65]  # parking lot p_28, 7 m east of its middle


def vehicle_table() -> dict[str, dict]:
    """Chapter 6's handling table: model -> seats, mass and the bands, from GDD.md."""
    out = {}
    text = GDD_FILE.read_text()
    chapter = text[text.index("## 6. Vehicles") : text.index("## 7. ")]
    for line in chapter.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8 or not cells[0].startswith("`") or cells[0] == "`Model`":
            continue
        if not cells[2].isdigit():
            continue

        def band(text: str) -> list[float]:
            lo, hi = text.replace(",", "").split("-")
            return [float(lo), float(hi)]

        out[cells[0].strip("`")] = {
            "seats": int(cells[2]), "mass": float(cells[3].replace(",", "")),
            "t060": band(cells[4]), "top": band(cells[5]), "brake": band(cells[6]),
            "circle": band(cells[7]),
        }  # fmt: skip
    return out


def heading_to(a: list[float], b: list[float]) -> float:
    """The heading (degrees clockwise from north, -z) from point a towards point b."""
    return round(math.degrees(math.atan2(b[0] - a[0], -(b[2] - a[2]))) % 360.0, 2)


def beside(
    at: list[float], heading: float, left_m: float, ahead_m: float
) -> list[float]:
    """A point left_m to the left of (negative: right of) and ahead_m ahead of `at` for
    something facing `heading`."""
    h = math.radians(heading)
    fwd = (math.sin(h), -math.cos(h))
    left = (fwd[1], -fwd[0])  # facing north (-z), left is west (-x)
    return [
        round(at[0] + left[0] * left_m + fwd[0] * ahead_m, 3),
        at[1],
        round(at[2] + left[1] * left_m + fwd[1] * ahead_m, 3),
    ]


def handling(label: str, models: list[str], variation: int) -> Playtest:
    table = vehicle_table()
    p = Playtest(
        f"vehicle.handling/{label}",
        ["VH-1", "VH-2", "IN-2", "AC-6"] + (["VH-9"] if "motorbike" in models else []),
        "Proving runs for each model in turn, the player driving alone, on Downtown's north-south "
        "arterial (level dry asphalt) and in the parking lot north-east of the plaza: 0-60 km/h "
        "at full throttle; a full stop from 60 km/h, dry and then in rain; the handbrake alone "
        "from 40 km/h; the turning circle at 8 km/h with full lock. Each model's body is a "
        "physics body on the vehicles layer with its listed mass. Traffic and people are set to "
        "none for the runs, and the wet stop uses the dry stop's lane. (Top speed needs a "
        "straight of at least 1.5 km, which Downtown does not have.)",
        ["--role=solo", f"--variation={variation}", "--save-dir={save_dir}"],
        limits={"wall_s": 900, "cpu_s": 1200, "step_s": 60},
    )
    light = {"census": {"kinds": VEHICLE_KINDS}, "every": 30}
    dense = {"census": {"kinds": VEHICLE_KINDS}, "every": 1}
    p.step("observe", light)
    for model in models:
        row = table[model]
        p.dev(("world.reset", {"variation": variation}))
        p.dev(("traffic.set", {"density": 0}))
        # IN-2 and VH-1: move_* does not drive; full throttle from rest to 60 km/h; stop
        spawn = p.dev(
            ("vehicle.spawn", {"model": model, "at": DRY_LANE, "driver": "player"})
        )
        vid = {"$answer": [spawn, "id"]}
        body = p.step("query", [{"id": "body", "type": "body", "entity": vid}])
        p.step("run", 30)
        p.mark(f"{model}_walk_a")
        p.step("press", {"move_forward": 1.0})
        p.step("run", 60)
        p.step("release", ["move_forward"])
        p.mark(f"{model}_walk_b")
        p.step("run", 30)
        p.step("observe", dense)
        p.step("run", 1)
        p.mark(f"{model}_accel_a")
        p.step("press", {"accelerate": 1.0})
        p.step("wait_for", {"entity": {"id": vid, "min_kmh": 60.0}, "max_ticks": 900})
        p.step("release", ["accelerate"])
        p.step("press", {"brake": 1.0})
        p.mark(f"{model}_brake_a")
        p.step("wait_for", {"entity": {"id": vid, "max_kmh": 0.2}, "max_ticks": 480})
        p.step("run", 10)
        p.step("release", ["brake"])
        p.mark(f"{model}_brake_b")
        p.step("observe", light)
        idf = {"id_from": {"step": spawn, "index": 0}}
        p.expect(
            f"{model}_body", "body", {"step": body, "query": "body", "layer": 2,
             "mass_kg": row["mass"], "tol": 0.1},
            "VH-1", f"the {model} model's root is a physics body on the vehicles layer with a mass of "
            f"{row['mass']:,.0f} kg within 10%",
        )  # fmt: skip
        p.expect(
            f"{model}_walk_keys", "moved",
            {"from": f"{model}_walk_a", "to": f"{model}_walk_b", "kind": "vehicle",
             "min_m": 0.0, "max_m": 0.3},
            "IN-2", f"move_forward held for 1 s in the {model} model does not drive it (at most 0.3 m)",
        )  # fmt: skip
        lo, hi = row["t060"]
        p.expect(
            f"{model}_accel", "accel",
            {"from": f"{model}_accel_a", "to": f"{model}_brake_a", **idf, "kmh": 60.0,
             "min_s": lo, "max_s": hi},
            "VH-1", f"the {model} model reaches 60 km/h from rest in {lo}-{hi} s",
        )  # fmt: skip
        lo, hi = row["brake"]
        p.expect(
            f"{model}_brake_dry", "brake",
            {"from": f"{model}_brake_a", "to": f"{model}_brake_b", **idf, "kmh": 60.0,
             "min_m": lo, "max_m": hi},
            "VH-1", f"the {model} model stops from 60 km/h within {lo}-{hi} m on dry asphalt",
        )  # fmt: skip
        # VH-2: the same stop in rain, on the same lane
        p.dev(("world.reset", {"variation": variation}))
        p.dev(("traffic.set", {"density": 0}))
        p.dev(("weather.set", {"kind": "rain"}))
        wet = p.dev(
            ("vehicle.spawn", {"model": model, "at": DRY_LANE, "driver": "player"})
        )
        wid = {"$answer": [wet, "id"]}
        p.step("run", 30)
        p.step("observe", dense)
        p.step("press", {"accelerate": 1.0})
        p.step("wait_for", {"entity": {"id": wid, "min_kmh": 60.0}, "max_ticks": 900})
        p.step("release", ["accelerate"])
        p.step("press", {"brake": 1.0})
        p.mark(f"{model}_wet_a")
        p.step("wait_for", {"entity": {"id": wid, "max_kmh": 0.2}, "max_ticks": 600})
        p.step("run", 10)
        p.step("release", ["brake"])
        p.mark(f"{model}_wet_b")
        p.step("observe", light)
        p.dev(("weather.set", {"kind": "clear"}))
        p.expect(
            f"{model}_brake_wet", "brake",
            {"from": f"{model}_wet_a", "to": f"{model}_wet_b",
             "id_from": {"step": wet, "index": 0}, "kmh": 60.0,
             "dry": {"from": f"{model}_brake_a", "to": f"{model}_brake_b", **idf},
             "min_ratio": 1.15, "max_ratio": 1.60},
            "VH-2", f"in rain the {model} model needs 1.15-1.60 times its dry distance to stop from 60 km/h",
        )  # fmt: skip
        if model != "motorbike":
            # IN-2: the handbrake alone from 40 km/h
            hb = p.dev(
                (
                    "vehicle.spawn",
                    {"model": model, "at": HANDBRAKE_LANE, "driver": "player"},
                )
            )
            hid = {"$answer": [hb, "id"]}
            p.step("run", 30)
            p.step("observe", dense)
            p.step("press", {"accelerate": 1.0})
            p.step(
                "wait_for", {"entity": {"id": hid, "min_kmh": 40.0}, "max_ticks": 600}
            )
            p.step("release", ["accelerate"])
            p.step("press", {"handbrake": 1.0})
            p.mark(f"{model}_handbrake_a")
            p.step("run", 90)
            p.step("release", ["handbrake"])
            p.step("press", {"brake": 1.0})
            p.mark(f"{model}_handbrake_b")
            p.step("run", 240)
            p.step("release", ["brake"])
            p.step("observe", light)
            p.expect(
                f"{model}_handbrake", "decel",
                {"from": f"{model}_handbrake_a", "to": f"{model}_handbrake_b",
                 "id_from": {"step": hb, "index": 0}, "min_kmh": 35.0, "over_s": 1.0,
                 "min_mps2": 2.0, "max_mps2": 6.0},
                "IN-2", f"the handbrake held alone slows the {model} model at 2-6 m/s^2 from 40 km/h",
            )  # fmt: skip
        # VH-1: the turning circle at 8 km/h with full lock, in the parking lot
        pad = p.dev(
            (
                "vehicle.spawn",
                {"model": model, "at": PAD, "heading": 0, "driver": "player"},
            )
        )
        pid = {"$answer": [pad, "id"]}
        p.step("run", 30)
        p.step(
            "cruise",
            {
                "entity": {"id": pid},
                "kmh": 8.0,
                "ticks": 240,
                "hold": {"steer_left": 1.0},
            },
        )
        p.step("observe", dense)
        p.mark(f"{model}_circle_a")
        p.step(
            "cruise",
            {
                "entity": {"id": pid},
                "kmh": 8.0,
                "ticks": 900,
                "hold": {"steer_left": 1.0},
            },
        )
        p.mark(f"{model}_circle_b")
        p.step("observe", light)
        lo, hi = row["circle"]
        p.expect(
            f"{model}_circle", "turn_circle",
            {"from": f"{model}_circle_a", "to": f"{model}_circle_b",
             "id_from": {"step": pad, "index": 0}, "kmh": 8.0, "kmh_tol": 1.5,
             "min_turn_deg": 180.0, "min_m": lo, "max_m": hi},
            "VH-1", f"at 8 km/h with full lock the {model} model's position traces a circle {lo}-{hi} m across",
        )  # fmt: skip
        if model == "motorbike":
            # VH-9: leaning into a tight turn at 15 km/h (about 4 m/s^2)
            p.step("cruise", {"entity": {"id": pid}, "kmh": 15.0, "ticks": 240,
                              "hold": {"steer_left": 1.0}, "keep": True})  # fmt: skip
            p.step("observe", dense)
            p.mark("motorbike_lean_a")
            p.step("cruise", {"entity": {"id": pid}, "kmh": 15.0, "ticks": 300,
                              "hold": {"steer_left": 1.0}})  # fmt: skip
            p.mark("motorbike_lean_b")
            p.step("observe", light)
            p.expect(
                "motorbike_lean", "lean",
                {"from": "motorbike_lean_a", "to": "motorbike_lean_b",
                 "id_from": {"step": pad, "index": 0}, "min_lat": 2.0, "min_deg": 10.0,
                 "share": 0.9, "min_samples": 30},
                "VH-9", "cornering at 2 m/s^2 or more, the motorbike leans at least 10 degrees",
            )  # fmt: skip
    return p


def handling_cars() -> Playtest:
    return handling(
        "cars", ["sedan", "hatchback", "sports", "suv", "van", "pickup"], 12
    )


def handling_service() -> Playtest:
    return handling(
        "service", ["taxi", "police", "ambulance", "tactical_van", "motorbike"], 13
    )


def vehicle_entry() -> Playtest:
    table = vehicle_table()
    p = Playtest(
        "people.vehicle_entry/sedan",
        ["FT-10", "AC-6", "CM-1", "IN-2"],
        "A sedan parked on the north-south arterial, traffic and people set to none. The player "
        "stands 2.4 m to the right of its centre line, level with the front seats, presses "
        "interact, sits in the seat whose door is nearest, then presses interact to get out. Then "
        "the same 2.4 m to the left, and this time drives 3 s and stops before getting out. QA reads the seat points (seat, door "
        "and wheel, in world space) every tick: "
        "the walk passes within 1.0 m of the door, the player is seated 1.0-4.0 s after "
        "interact, the hips stay within 0.35 m of the seat point and a driver's hands within "
        "0.30 m of the wheel point, getting out takes 1.0-3.0 s and ends within 2.5 m of the "
        "door (horizontally), and while driving the camera keeps 5.0-10.0 m from the sedan with the hips in "
        "the middle of the view.",
        ["--role=solo", "--variation=11", "--save-dir={save_dir}"],
        limits={"step_s": 60},
    )
    at_lane = {"lane": "e_34_35:ab0", "s": 40}
    car = PLAN.resolve(at_lane)
    car_p, car_h = [round(c, 3) for c in car.p], car.heading_deg
    p.step("observe", {"census": {"kinds": VEHICLE_KINDS}, "state": True, "every": 6})
    p.dev(("world.reset", {"variation": 11}))
    p.dev(("traffic.set", {"density": 0}))
    spawn = p.dev(
        ("vehicle.spawn", {"model": "sedan", "at": at_lane, "driver": "none"})
    )
    vid = {"$answer": [spawn, "id"]}
    idf = {"id_from": {"step": spawn, "index": 0}}
    dense = {"census": {"kinds": VEHICLE_KINDS}, "state": True, "camera": True, "every": 1,
             "bones": {"ids": ["player"], "names": DRIVE_BONES}, "seats": {"ids": [vid]}}  # fmt: skip
    for side, left_m in (("right", -2.4), ("left", 2.4)):
        stand = beside(car_p, car_h, left_m, 0.6)
        p.dev(("player.spawn", {"at": stand, "heading": heading_to(stand, car_p)}))
        p.step("run", 30)
        p.step("observe", dense)
        p.step("run", 1)
        p.mark(f"{side}_ready")
        p.mark(f"{side}_in_a")
        p.step("press", {"interact": 1.0})
        p.step("run", 2)
        p.step("release", ["interact"])
        p.step("run", 300)
        p.mark(f"{side}_in_b")
        p.step("run", 60)
        if side == "left":
            p.mark("drive_a")
            p.step("press", {"accelerate": 0.6})
            p.step("run", 180)
            p.step("release", ["accelerate"])
            p.step("press", {"brake": 1.0})
            p.step(
                "wait_for", {"entity": {"id": vid, "max_kmh": 0.5}, "max_ticks": 300}
            )
            p.step("release", ["brake"])
            p.mark("drive_b")
            p.step("run", 30)
        p.mark(f"{side}_seated_b")
        p.mark(f"{side}_out_a")
        p.step("press", {"interact": 1.0})
        p.step("run", 2)
        p.step("release", ["interact"])
        p.step("run", 240)
        p.mark(f"{side}_out_b")
        p.step(
            "observe", {"census": {"kinds": VEHICLE_KINDS}, "state": True, "every": 6}
        )
        p.expect(
            f"{side}_get_in", "get_in",
            {"from": f"{side}_in_a", "to": f"{side}_in_b", **idf, "near_m": 3.0, "door_m": 1.0,
             "min_s": 1.0, "max_s": 4.0},
            "FT-10",
            f"interact 2.4 m to the {side} of the sedan's centre line walks the player to the nearest "
            "door "
            "(the path within 1.0 m of it) and seats them in that door's seat 1.0-4.0 s later",
        )  # fmt: skip
        p.expect(
            f"{side}_seated", "seated",
            {"from": f"{side}_in_a", "to": f"{side}_seated_b", **idf, "hips_m": 0.35,
             "hands_m": 0.30},
            "FT-10",
            "seated (and driving), the hips stay within 0.35 m of the seat point; in the driver's "
            "seat both hands stay within 0.30 m of the wheel point",
        )  # fmt: skip
        p.expect(
            f"{side}_get_out", "get_out",
            {"from": f"{side}_out_a", "to": f"{side}_out_b", **idf, "min_s": 1.0, "max_s": 3.0,
             "door_m": 2.5},
            "FT-10",
            "interact in the sedan gets the player out within 1.0-3.0 s, on foot within 2.5 m of "
            "the door of the seat they sat in",
        )  # fmt: skip
    p.expect(
        "seats", "seats", {"mark": "left_ready", **idf, "count": table["sedan"]["seats"]},
        "AC-6",
        f"the sedan has {table['sedan']['seats']} seat markers, indices 0 to "
        f"{table['sedan']['seats'] - 1}, each with a door point, the driver's with a wheel point",
    )  # fmt: skip
    p.expect(
        "camera_vehicle", "camera_vehicle",
        {"from": "drive_a", "to": "drive_b", **idf, "min_m": 5.0, "max_m": 10.0,
         "middle": 0.4, "aspect": ASPECT},
        "CM-1",
        "driving, the camera stays 5.0-10.0 m from the sedan's position and the player's hips "
        "inside the middle 40% of the view",
    )  # fmt: skip
    p.expect(
        "drive_moves", "moved",
        {"from": "drive_a", "to": "drive_b", "kind": "vehicle", "min_m": 3.0},
        "IN-2", "accelerate drives the sedan (it moves at least 3 m)", "pre",
    )  # fmt: skip
    return p


def crash() -> Playtest:
    p = Playtest(
        "vehicle.crash/barrier",
        ["VH-3", "VH-4", "VH-5", "VH-6", "FT-9", "AC-10"],
        "Damage. A sedan already at damage 0.15 coasts from 45 km/h into a wall across the "
        "east-west arterial: the damage rises by 0.004 * (dv - 8) within 25% and, the impact "
        "being 25 km/h or more with the damage at 0.25 or above, a part comes off within 0.5 s. "
        "A sedan at damage 0.78 gets at most 10 km/h from full throttle. A sedan put on the "
        "plaza at damage 0.85 burns and explodes 8-12 s later, leaving a wreck at 1.0: a man "
        "2 m from it dies, the player 4.5 m away loses 50 health and goes limp, and a parked "
        "sedan 5 m away is pushed at least 0.3 m off and takes 0.30 damage. Last, the player drives "
        "a sedan at 30 km/h into a man standing in the lane 35 m ahead: he goes limp within 0.2 s "
        "and, if he lives, gets up. Traffic and people are set to none.",
        ["--role=solo", "--variation=14", "--save-dir={save_dir}"],
        limits={"step_s": 60, "wall_s": 400},
    )
    meta = ["damage", "burning", "vehicle", "limp"]
    kinds = ["player", "npc", "vehicle", "debris"]
    light = {"census": {"meta": meta, "kinds": kinds}, "state": True, "every": 6}
    dense = {"census": {"meta": meta, "kinds": kinds}, "state": True, "every": 1}
    p.step("observe", light)
    p.dev(("world.reset", {"variation": 14}))
    p.dev(("traffic.set", {"density": 0}))
    # VH-3, VH-4: into a wall at 45 km/h
    wall_at = point({"lane": "e_14_24:ab0", "s": 60})
    p.dev(
        (
            "prop.spawn",
            {"kind": "wall", "at": wall_at, "size": [8.0, 3.0, 1.0], "heading": 90},
        )
    )
    car = p.dev(("vehicle.spawn", {"model": "sedan", "at": {"lane": "e_14_24:ab0", "s": 5},
                                    "driver": "player", "damage": 0.15}))  # fmt: skip
    cid = {"$answer": [car, "id"]}
    p.step("run", 30)
    p.step("press", {"accelerate": 1.0})
    p.step("wait_for", {"entity": {"id": cid, "min_kmh": 45.0}, "max_ticks": 600})
    p.step("release", ["accelerate"])
    p.step("observe", dense)
    p.mark("crash_a")
    p.step("run", 300)
    p.mark("crash_b")
    p.step("observe", light)
    car_from = {"id_from": {"step": car, "index": 0}}
    p.expect(
        "impact_damage", "impact_damage",
        {"from": "crash_a", "to": "crash_b", **car_from, "rate": 0.004, "free_kmh": 8.0,
         "tol": 0.25, "min_dv_kmh": 15.0},
        "VH-3",
        "coasting into the wall from 45 km/h, the sedan's damage rises by 0.004 * (dv - 8) "
        "within 25%, dv the change of its velocity in km/h from just before the impact to 0.2 s "
        "after it, and never falls",
    )  # fmt: skip
    p.expect(
        "part_off", "part_off",
        {"from": "crash_a", "to": "crash_b", **car_from, "min_dv_kmh": 25.0,
         "min_damage": 0.25, "within_s": 0.5},
        "VH-4",
        "the impact (dv of 25 km/h or more, damage 0.25 or above after it) detaches a part "
        "within 0.5 s: a part_detached event and a debris entity naming the sedan",
    )  # fmt: skip
    # VH-5: an engine at damage 0.78
    weak = p.dev(("vehicle.spawn", {"model": "sedan", "at": {"lane": "e_24_34:ab0", "s": 5},
                                     "driver": "player", "damage": 0.78}))  # fmt: skip
    p.step("run", 30)
    p.step("observe", dense)
    p.mark("weak_a")
    p.step("press", {"accelerate": 1.0})
    p.step("run", 300)
    p.step("release", ["accelerate"])
    p.mark("weak_b")
    p.step("observe", light)
    p.expect(
        "engine_failed", "max_speed",
        {"from": "weak_a", "to": "weak_b", "id_from": {"step": weak, "index": 0},
         "max_kmh": 10.0},
        "VH-5", "at damage 0.78 full throttle for 5 s gives the sedan at most 10 km/h",
    )  # fmt: skip
    # VH-6 and FT-9: a burning sedan on the plaza
    x0, y0, z0 = point(PLAZA)
    burn_at = [round(x0 + 10.0, 3), y0, round(z0 + 10.0, 3)]
    p.dev(
        (
            "player.spawn",
            {"at": [round(burn_at[0] - 4.5, 3), y0, burn_at[2]], "heading": 90},
        )
    )
    p.dev(("player.give", {"health": 100}))
    man = p.dev(("npc.spawn", {"archetype": "office_worker",
                               "at": [burn_at[0], y0, round(burn_at[2] + 2.0, 3)],
                               "heading": 0, "behaviour": "idle"}))  # fmt: skip
    parked = p.dev(("vehicle.spawn", {"model": "sedan",
                                       "at": [burn_at[0], y0, round(burn_at[2] - 5.0, 3)],
                                       "heading": 90, "driver": "none"}))  # fmt: skip
    p.step("run", 10)
    burning = p.dev(("vehicle.spawn", {"model": "sedan", "at": burn_at, "heading": 90,
                                        "driver": "none", "damage": 0.85}))  # fmt: skip
    bid = {"id_from": {"step": burning, "index": 0}}
    p.step("observe", {**dense, "bones": {"ids": ["player"], "names": BODY_BONES}})
    p.step("run", 2)
    p.mark("burn_a")
    p.step("run", 900)
    p.mark("burn_b")
    p.step("observe", light)
    p.expect(
        "burning", "meta_value", {"mark": "burn_a", **bid, "key": "burning", "equals": True},
        "VH-6", "a sedan put down at damage 0.85 is burning (its burning metadata true)",
    )  # fmt: skip
    p.expect(
        "explosion", "explosion", {"from": "burn_a", "to": "burn_b", **bid, "min_s": 8.0,
                                   "max_s": 12.0},
        "VH-6",
        "the burning sedan explodes 8-12 s after it began burning (vehicle_exploded) and is "
        "left a wreck at damage 1.0",
    )  # fmt: skip
    p.expect(
        "blast_kills", "blast",
        {"from": "burn_a", "to": "burn_b", **bid, "what": "harm",
         "of": {"id_from": {"step": man, "index": 0}}},
        "VH-6", "the explosion kills a man 2 m away (his died event)",
    )  # fmt: skip
    p.expect(
        "blast_hurts", "blast",
        {"from": "burn_a", "to": "burn_b", **bid, "what": "harm", "tol": 0.1},
        "VH-6", "the player 4.5 m away loses 100 * (6 - 4.5) / 3 = 50 health, within 10%",
    )  # fmt: skip
    p.expect(
        "blast_push", "blast",
        {"from": "burn_a", "to": "burn_b", **bid, "what": "push", "push_m": 0.3,
         "of": {"id_from": {"step": parked, "index": 0}}},
        "VH-6",
        "a parked sedan 5 m away is pushed at least 0.3 m further off and takes 0.30 damage",
    )  # fmt: skip
    p.expect(
        "blast_ragdoll", "ragdoll",
        {"from": "burn_a", "to": "burn_b", "kind": "player",
         "trigger": {"event": "vehicle_exploded", "any": True}, "within_ticks": 12,
         "min_s": 1.0, "below_m": 0.05, "step_m": 1.0, "ground_y": y0, "boxes": []},
        "FT-9",
        "the player, 4.5 m from the explosion, goes limp within 0.2 s and stays limp at least "
        "1.0 s, no bone more than 0.05 m under the ground",
    )  # fmt: skip
    # FT-9: run into at 30 km/h
    lane = {"lane": "e_34_44:ab0", "s": 5}
    stand = point({"lane": "e_34_44:ab0", "s": 40})
    walker = p.dev(("npc.spawn", {"archetype": "office_worker", "at": stand, "heading": 270,
                                  "behaviour": "idle"}))  # fmt: skip
    driven = p.dev(
        ("vehicle.spawn", {"model": "sedan", "at": lane, "driver": "player"})
    )
    did = {"$answer": [driven, "id"]}
    p.step("run", 30)
    p.step(
        "observe",
        {**light, "bones": {"ids": [{"$answer": [walker, "id"]}], "names": BODY_BONES}},
    )
    p.step("run", 1)
    p.mark("hit_a")
    p.step("press", {"accelerate": 1.0})
    p.step("wait_for", {"entity": {"id": did, "min_kmh": 30.0}, "max_ticks": 600})
    p.step(
        "observe",
        {**dense, "bones": {"ids": [{"$answer": [walker, "id"]}], "names": BODY_BONES}},
    )
    p.step("cruise", {"entity": {"id": did}, "kmh": 30.0, "ticks": 300})
    p.step("press", {"brake": 1.0})
    p.step("wait_for", {"entity": {"id": did, "max_kmh": 0.5}, "max_ticks": 300})
    p.step("release", ["brake"])
    p.step("run", 240)
    p.mark("hit_b")
    p.step("observe", light)
    wid = {"id_from": {"step": walker, "index": 0}}
    p.expect(
        "run_into", "ragdoll",
        {"from": "hit_a", "to": "hit_b", **wid,
         "trigger": {"near_id_from": {"step": driven, "index": 0}, "near_m": 2.5},
         "within_ticks": 18, "min_s": 1.0, "below_m": 0.05, "step_m": 1.0, "ground_y": 0.0,
         "boxes": []},
        "FT-9",
        "a man the sedan runs into at 30 km/h (QA's bot holding the speed) goes limp within "
        "0.2 s of the hit, counted from the sedan's centre coming within 2.5 m of him (about "
        "where a sedan's front meets him) with 0.1 s more for a shorter front, and stays limp at "
        "least 1.0 s",
    )  # fmt: skip
    p.expect(
        "run_into_up", "get_up",
        {"from": "hit_a", "to": "hit_b", **wid, "ground_y": 0.0, "within_s": 6.0, "ratio": 0.9},
        "FT-9", "still alive, he gets up within 6.0 s of going limp",
    )  # fmt: skip
    return p


# Chapter 7, TR-4, and chapter 17, AC-7: the signals of every signalised junction.
SIGNAL_META = ["intersection", "approach", "crosswalk", "state"]
TICKS = 60  # physics ticks per second


def signal_programs() -> dict[str, dict]:
    """Every signalised junction's program in ticks (plan/FORMAT.md, "Signal program")."""
    out = {}
    for it in PLAN.data["intersections"]:
        if it.get("control") != "signal":
            continue
        sig = it["signal"]
        amber, all_red = round(sig["amber_s"] * TICKS), round(sig["all_red_s"] * TICKS)
        phases, t = [], 0
        for ph in sig["phases"]:
            green = round(ph["green_s"] * TICKS)
            phases.append({"start": t, "green_end": t + green, "amber_end": t + green + amber,
                           "green": list(ph["green"]), "walk": list(ph["walk"])})  # fmt: skip
            t += green + amber + all_red
        out[it["id"]] = {
            "offset": round(sig["offset_s"] * TICKS),
            "cycle": t,
            "phases": phases,
        }
    return out


def intersection_watch() -> Playtest:
    p = Playtest(
        "traffic.intersection_watch/signals",
        ["TR-4", "AC-7"],
        "Downtown's signals after a world reset: every signalised approach and every crosswalk "
        "with walk signals has its signal entity, and for 77 s (a full cycle of the longest "
        "program) every signal shows its plan program's state within one tick.",
        ["--role=solo", "--variation=9", "--save-dir={save_dir}"],
    )
    programs = signal_programs()
    approaches, crosswalks = [], []
    for it in PLAN.data["intersections"]:
        if it["id"] not in programs:
            continue
        walks = {c for ph in it["signal"]["phases"] for c in ph["walk"]}
        for leg in it["legs"]:
            if leg.get("approach"):
                approaches.append([it["id"], leg["approach"]["id"]])
            cw = leg.get("crosswalk")
            if cw and cw["id"] in walks:
                crosswalks.append([it["id"], cw["id"]])
    longest = max(prog["cycle"] for prog in programs.values())
    p.step("observe", {"census": {"meta": SIGNAL_META}, "every": 30})
    reset = p.dev(("world.reset", {"variation": 9}))
    p.step("run", 1)
    p.mark("after_reset")
    p.step("observe", {"census": {"meta": SIGNAL_META}, "every": 7})
    p.mark("watch_a")
    p.step("run", longest + 2 * TICKS)
    p.mark("watch_b")
    p.expect(
        "signal_entities", "signal_entities",
        {"mark": "after_reset", "approaches": approaches, "crosswalks": crosswalks},
        "AC-7",
        "each signalised approach has one signal entity with intersection, approach and a state "
        "of red, amber or green; each crosswalk with walk signals one with crosswalk and a state "
        "of walk or dont_walk",
    )  # fmt: skip
    p.expect(
        "program", "signal_program",
        {"from": "watch_a", "to": "watch_b", "programs": programs, "reset_step": reset},
        "TR-4",
        "every signal shows its program's state within one tick, program time counted from the "
        "tick the world.reset command ran in",
    )  # fmt: skip
    p.expect(
        "greens_compatible", "signal_greens",
        {"from": "watch_a", "to": "watch_b", "programs": programs, "reset_step": reset},
        "TR-4", "no two approaches are green at once unless their program puts them in one phase",
    )  # fmt: skip
    p.expect(
        "walk_in_green", "signal_walks",
        {"from": "watch_a", "to": "watch_b", "programs": programs, "reset_step": reset},
        "TR-4", "a crosswalk shows walk only during the green of the phase that lists it",
    )  # fmt: skip
    return p


# Chapter 7: traffic and people on foot.
STREET_META = [
    "vehicle",
    "seat",
    "limp",
    "state",
    "intersection",
    "approach",
    "crosswalk",
]
DRIVING = [
    "commuter_driver", "taxi_driver", "truck_driver", "paramedic", "police_officer",
    "police_tactical",
]  # fmt: skip
PROBES = Probes(PLAN.data)
WATCH_R = 75.0


def r2(v: float) -> float:
    return round(float(v), 2)


def node_xz(node_id: str) -> tuple[float, float]:
    n = PLAN.nodes[node_id]["p"]
    return float(n[0]), float(n[2])


def leg_geometry(inter: dict, leg: dict) -> tuple:
    """(node xz, unit direction away from the node, left and right half widths seen leaving
    it) of a leg."""
    edge = PLAN.edges[leg["edge"]]
    o, u, _y = PROBES.leg_frame(inter["node"], edge)
    left, right = PROBES.half_widths(edge, inter["node"])
    return o, u, left, right


def rect(o, u, a: float, b: float, left: float, right: float) -> list:
    """The part of a leg's carriageway from a to b metres out from the node."""
    rx, rz = -u[1], u[0]
    pts = []
    for d, side in ((a, -left), (b, -left), (b, right), (a, right)):
        pts.append([r2(o[0] + u[0] * d + rx * side), r2(o[1] + u[1] * d + rz * side)])
    return pts


def box_of(inter_id: str) -> list:
    """The junction box: the hull of every leg's carriageway out to its box_m."""
    inter = PLAN.intersections[inter_id]
    pts = []
    for leg in inter["legs"]:
        o, u, left, right = leg_geometry(inter, leg)
        pts += rect(o, u, 0.0, float(leg["box_m"]), left, right)
    return hull_xz(pts)


def hull_xz(points: list) -> list:
    pts = sorted({(p[0], p[1]) for p in points})

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for q in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    upper: list = []
    for q in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return [[r2(a), r2(b)] for a, b in lower[:-1] + upper[:-1]]


def stop_lines(inter_id: str) -> list[dict]:
    """Every approach of a junction: its stop line across the lanes that arrive there (the
    left part of the carriageway seen leaving the node; all of it on a one-way street), and
    the direction of travel towards the node."""
    inter = PLAN.intersections[inter_id]
    out = []
    for leg in inter["legs"]:
        ap = leg.get("approach")
        if not ap:
            continue
        edge = PLAN.edges[leg["edge"]]
        o, u, left, right = leg_geometry(inter, leg)
        d = float(ap["stop_line_m"])
        rx, rz = -u[1], u[0]
        far = -left
        near = right if edge.get("oneway") else 0.0
        out.append({
            "intersection": inter_id, "approach": ap["id"],
            "line": [[r2(o[0] + u[0] * d + rx * far), r2(o[1] + u[1] * d + rz * far)],
                     [r2(o[0] + u[0] * d + rx * near), r2(o[1] + u[1] * d + rz * near)]],
            "toward": [round(-u[0], 5), round(-u[1], 5)],
        })  # fmt: skip
    return out


def right_hand(inter_id: str) -> dict:
    """{approach: the approach on its right}: the leg whose outward heading is 90 degrees
    anticlockwise of its own (within 45 degrees)."""
    inter = PLAN.intersections[inter_id]
    heads = {}
    for leg in inter["legs"]:
        if leg.get("approach"):
            _o, u, _l, _r = leg_geometry(inter, leg)
            heads[leg["approach"]["id"]] = math.degrees(math.atan2(u[0], -u[1])) % 360.0
    out = {}
    for a, ha in heads.items():
        for b, hb in heads.items():
            rel = (hb - ha + 180.0) % 360.0 - 180.0
            if -135.0 < rel < -45.0:
                out[a] = b
    return out


def street_area(node_id: str, radius: float) -> dict:
    """The places QA's street checks read around a node (qakit/streets.py, "area"): lanes,
    carriageways and junction boxes, crosswalk bands, blocks, building footprints and rooms
    within about `radius` metres."""
    cx, cz = node_xz(node_id)

    def near(points: list, extra: float) -> bool:
        return any(math.hypot(q[0] - cx, q[1] - cz) <= radius + extra for q in points)

    lanes = []
    for lane_id in sorted(PLAN.lanes):
        edge, _lane = PLAN.lanes[lane_id]
        length = PLAN.lane_length(lane_id)
        n = max(1, math.ceil(length / 10.0))
        pts = [PLAN.lane_point(lane_id, length * k / n).p for k in range(n + 1)]
        xz = [[r2(q[0]), r2(q[2])] for q in pts]
        if near(xz, 15.0):
            lanes.append({"id": lane_id, "pts": xz, "width": float(edge["lane_width_m"]),
                          "limit_kmh": float(edge["speed_kmh"])})  # fmt: skip
    roads, crosswalks = [], []
    for edge in PLAN.data["edges"]:
        pts = PLAN.centreline(edge)
        if not near([[q[0], q[2]] for q in pts], 40.0):
            continue
        w = float(edge["lane_width_m"])
        if edge.get("oneway"):
            left = right = len(edge["lanes"]) * w / 2.0
        else:
            right = sum(1 for ln in edge["lanes"] if ln["dir"] == "ab") * w
            left = sum(1 for ln in edge["lanes"] if ln["dir"] == "ba") * w
        for a, b in itertools.pairwise(pts):
            ln = math.hypot(b[0] - a[0], b[2] - a[2])
            u = ((b[0] - a[0]) / ln, (b[2] - a[2]) / ln)
            roads.append(rect((a[0], a[2]), u, 0.0, ln, left, right))
    for inter in PLAN.data["intersections"]:
        if not near([list(node_xz(inter["node"]))], 40.0):
            continue
        box = box_of(inter["id"])
        if len(box) >= 3:
            roads.append(box)
        walks = set()
        if inter.get("signal"):
            walks = {c for ph in inter["signal"]["phases"] for c in ph["walk"]}
        for leg in inter["legs"]:
            cw = leg.get("crosswalk")
            if not cw:
                continue
            o, u, left, right = leg_geometry(inter, leg)
            crosswalks.append({
                "id": cw["id"], "intersection": inter["id"], "control": inter["control"],
                "walk_signals": cw["id"] in walks,
                "poly": rect(o, u, float(cw["from_m"]), float(cw["to_m"]), left, right),
            })  # fmt: skip
    blocks = [
        [[r2(x), r2(z)] for x, z in b["poly"]]
        for b in PLAN.data["blocks"]
        if near(b["poly"], 120.0)
    ]
    buildings, rooms = [], []
    for parcel in PLAN.data["parcels"]:
        if not near(parcel["poly"], 60.0):
            continue
        if parcel["zoning"] in BUILT:
            foot = inset(parcel["poly"], float(parcel["setback_m"]))
            buildings.append([[r2(x), r2(z)] for x, z in foot])
            for room in (parcel.get("interior") or {}).get("rooms", []):
                rooms.append([[r2(x), r2(z)] for x, z in room["poly"]])
    return {
        "centre": [cx, cz], "radius_m": radius, "lanes": lanes, "roads": roads,
        "crosswalks": crosswalks, "blocks": blocks, "buildings": buildings, "rooms": rooms,
    }  # fmt: skip


def street_watch(p: Playtest, every: int, near_m: float) -> None:
    """Observe the street: the census with the metadata the street checks read, the
    in-view flag and vehicles' collision boxes; the state report; and the hips of the
    nearest drivers with their vehicles' seat points (FT-10's seated pose)."""
    p.step("observe", {
        "census": {"meta": STREET_META, "view": True, "shapes": ["vehicle"]},
        "state": True, "every": every,
        "bones": {"ids": [{"kind": "npc", "meta": {"seat": 0}, "within_m": near_m, "max": 16}],
                  "names": ["Hips"]},
        "seats": {"ids": [{"kind": "vehicle", "within_m": near_m, "max": 16}]},
    })  # fmt: skip


def intersection_flow() -> Playtest:
    inter = "j_34"
    lines = stop_lines(inter)
    p = Playtest(
        "traffic.intersection_watch/day-flow",
        ["TR-1", "TR-5", "TR-7", "TR-9", "TR-10", "TR-11", "TR-12", "TR-15", "TR-16"],
        "Three minutes of a weekday morning at Downtown's busiest signalised junction "
        "(j_34, four arterials), after a minute for the streets to settle. The player stands "
        "on the corner of approach 0 and watches. QA counts the moving vehicles and the "
        "people on foot within 150 m once a second, watches every stop line, lane, crosswalk "
        "and sidewalk within 75 m of the junction, and reads every vehicle's collision boxes "
        "and the hips of the drivers nearest the player.",
        ["--role=solo", "--variation=12", "--save-dir={save_dir}"],
        limits={"wall_s": 1200, "cpu_s": 2400, "step_s": 120},
    )
    p.raw["shared"] = {"area": street_area(PLAN.intersections[inter]["node"], WATCH_R)}
    area = {"$shared": "area"}
    p.step("observe", {"census": {"meta": STREET_META}, "state": True, "every": 30})
    p.dev(("world.reset", {"variation": 12}))
    p.dev(("player.spawn", {"at": {"corner_of": inter, "approach": 0}}))
    p.step("run", 3600)
    street_watch(p, 12, 60.0)
    p.step("run", 1)
    p.mark("watch_a")
    p.step("run", 10800)
    p.mark("watch_b")
    span = {"from": "watch_a", "to": "watch_b"}
    p.expect(
        "drivers", "drivers",
        {**span, "archetypes": DRIVING, "min_kmh": 1.0, "hips_m": 0.35},
        "TR-16",
        "every NPC vehicle moving faster than 1 km/h has a driver: a person of a driving "
        "archetype whose vehicle metadata names it and whose seat is 0, with the hips within "
        "0.35 m of the driver's seat point where QA reads them; no seat holds two people",
    )  # fmt: skip
    p.expect(
        "density", "density",
        {**span, "within_m": 150.0, "vehicles": [10, 30], "people": [20, 60]},
        "TR-1",
        "in downtown_core by day the median of each minute is 10-30 moving NPC vehicles and "
        "20-60 NPC people on foot within 150 m of the player, counted once a second",
    )  # fmt: skip
    p.expect(
        "no_red_entry", "red_entries",
        {**span, "approaches": lines, "grace_s": 0.5, "amber_mps2": 4.0},
        "TR-5",
        "no NPC vehicle crosses a stop line of j_34 after its light has been red for 0.5 s, "
        "and none crosses at amber when it could have stopped braking at 4 m/s^2 or less",
    )  # fmt: skip
    p.expect(
        "green_flow", "green_flow", {**span, "approaches": lines, "min_vehicles": 3},
        "TR-5", "at least 3 NPC vehicles enter j_34 from each of its four approaches in the three minutes",
    )  # fmt: skip
    p.expect(
        "lane_keeping", "lane_keeping",
        {**span, "area": area, "max_offset_m": 1.0, "max_heading_deg": 15.0,
         "min_share": 0.98, "skip_start_m": 10.0},
        "TR-7",
        "on the lanes within 75 m, NPC vehicles keep within 1.0 m of the lane centre (95th "
        "percentile); past each lane's first 10 m (where turns out of a junction end) they head "
        "within 15 degrees of the lane on 98% of moving samples, and none drives against a "
        "lane's direction",
    )  # fmt: skip
    p.expect(
        "walkable", "walkable", {**span, "area": area, "min_share": 0.95},
        "TR-9",
        "people on foot within 75 m stand on walkable ground (sidewalks, crosswalks, open "
        "parcels, interiors, off-road ground) on at least 95% of samples",
    )  # fmt: skip
    p.expect(
        "crosswalks", "crosswalk_use", {**span, "area": area, "min_share": 0.9, "gap_m": 15.0},
        "TR-10",
        "at least 90% of road crossings start and end on a crosswalk band, and at j_34's "
        "signals people start across only while their crosswalk shows walk",
    )  # fmt: skip
    p.expect(
        "no_ped_hits", "crosswalk_hits", {**span, "area": area, "clear_m": 0.3},
        "TR-11",
        "no NPC vehicle's collision boxes come within 0.3 m of a person on a crosswalk band, "
        "and nobody goes limp there",
    )  # fmt: skip
    p.expect(
        "crash_rate", "vehicle_contacts", {**span, "max_rate": 0.02, "touch_m": 0.02, "apart_s": 1.0},
        "TR-12",
        "NPC vehicles' collision boxes start touching each other at most 0.02 times per "
        "vehicle per minute of moving NPC vehicles",
    )  # fmt: skip
    p.expect(
        "no_pop_in", "no_pop_in", {**span, "near_m": 80.0, "view_m": 200.0},
        "TR-15",
        "no NPC person or vehicle appears or vanishes within 80 m of the player, or within "
        "200 m inside the camera's view",
    )  # fmt: skip
    return p


def stop_junction() -> Playtest:
    inter = "j_45"
    lines = stop_lines(inter)
    box = box_of(inter)
    p = Playtest(
        "traffic.stop_junction/four-way",
        ["TR-6", "TR-10", "TR-16"],
        "Three minutes at the all-way stop j_45 (four streets, downtown_core, morning), with "
        "the city's traffic and people about. QA also sends cars at it, each driven by a "
        "commuter from 30 m before a stop line: four at once, then two on neighbouring "
        "approaches at once, then two 3 s apart, then four 1 s apart. Every NPC vehicle "
        "stops within 4 m before its line, goes in order of arrival (the one on the right "
        "first when two arrive within 1.0 s), no two on crossing paths are in the box at "
        "once, none waits over 30 s, and people start across a crosswalk only with no "
        "vehicle within 15 m coming towards it.",
        ["--role=solo", "--variation=14", "--save-dir={save_dir}"],
        limits={"wall_s": 1200, "cpu_s": 2400, "step_s": 120},
    )
    p.raw["shared"] = {"area": street_area(PLAN.intersections[inter]["node"], 45.0)}
    p.step("observe", {"census": {"meta": STREET_META}, "state": True, "every": 30})
    p.dev(("world.reset", {"variation": 14}))
    p.dev(("player.spawn", {"at": {"corner_of": inter, "approach": 1}}))
    p.step("run", 600)
    street_watch(p, 6, 45.0)
    p.step("run", 1)
    p.mark("watch_a")
    waves = [
        [(0, "sedan"), (1, "sedan"), (2, "sedan"), (3, "sedan")],
        [(0, "hatchback"), (1, "hatchback")],
        [(2, "suv")],
        [(3, "suv")],
        [(0, "sedan")],
        [(1, "taxi")],
        [(2, "hatchback")],
        [(3, "sedan")],
    ]
    gaps = [2100, 2100, 180, 2100, 60, 60, 60, 2400]
    for wave, gap in zip(waves, gaps, strict=True):
        cmds = []
        for k, model in wave:
            at = {"intersection": inter, "approach": k, "before_m": 30.0}
            driver = "taxi_driver" if model == "taxi" else "commuter_driver"
            cmds.append(("vehicle.spawn", {"model": model, "at": at, "driver": driver}))
        p.dev(*cmds)
        p.step("run", gap)
    p.mark("watch_b")
    span = {"from": "watch_a", "to": "watch_b"}
    stop = {**span, "approaches": lines, "box": box, "zone_m": 4.0}
    p.expect(
        "full_stop", "stop_full", stop, "TR-6",
        "every NPC vehicle stands (1 km/h or less) within 4 m before its stop line before it crosses it",
    )  # fmt: skip
    p.expect(
        "order", "stop_order",
        {**stop, "late_s": 1.2, "tie_s": 0.8, "right_of": right_hand(inter)},
        "TR-6",
        "vehicles on crossing paths go in order of arrival, the one on the right first when "
        "two arrive within 1.0 s (pairs 0.8-1.2 s apart, and ties of three or four, may go "
        "either way)",
    )  # fmt: skip
    p.expect(
        "box_clear", "box_clear", stop, "TR-6",
        "no two NPC vehicles on crossing paths are in the junction box at once",
    )  # fmt: skip
    p.expect(
        "no_deadlock", "stop_wait", {**stop, "max_s": 30.0}, "TR-6",
        "no NPC vehicle waits more than 30 s at a stop line",
    )  # fmt: skip
    p.expect(
        "ped_gap", "crosswalk_use",
        {**span, "area": {"$shared": "area"}, "min_share": 0.9, "gap_m": 15.0},
        "TR-10",
        "people cross only on crosswalk bands, starting across one at the all-way stop only "
        "when no vehicle within 15 m is coming towards it",
    )  # fmt: skip
    p.expect(
        "drivers", "drivers", {**span, "archetypes": DRIVING, "min_kmh": 1.0, "hips_m": 0.35},
        "TR-16", "every moving NPC vehicle has a seated driver of a driving archetype",
    )  # fmt: skip
    return p


def obstacle() -> Playtest:
    p = Playtest(
        "traffic.obstacle/lane-blocked",
        ["TR-12", "TR-16"],
        "Traffic and people set to none. Three cars driven by commuters each meet something "
        "standing in their lane: a barrier across the eastbound arterial's right lane 62 m "
        "ahead, a person standing in the westbound right lane, and a van parked in the "
        "southbound right lane. Each car stops before it and never touches it.",
        ["--role=solo", "--variation=15", "--save-dir={save_dir}"],
        limits={"step_s": 60},
    )
    barrier_lane, person_lane, van_lane = "e_44_54:ab1", "e_44_54:ba1", "e_34_35:ab1"
    barrier_at = point({"lane": barrier_lane, "s": 70.0})
    barrier_h = PLAN.lane_point(barrier_lane, 70.0).heading_deg
    barrier = {"p": barrier_at, "size": [3.0, 0.8, 0.4], "heading": round(barrier_h, 3)}
    p.step(
        "observe",
        {
            "census": {"meta": STREET_META, "shapes": ["vehicle"]},
            "state": True,
            "every": 6,
        },
    )
    p.dev(("world.reset", {"variation": 15}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": {"sidewalk": "sw_44", "s": 30.0}}))
    p.dev(("prop.spawn", {"kind": "barrier", "at": barrier_at, "size": [3.0, 0.8, 0.4],
                          "heading": barrier["heading"]}))  # fmt: skip
    person = p.dev(("npc.spawn", {"archetype": "tourist", "at": {"lane": person_lane, "s": 70.0},
                                  "behaviour": "idle"}))  # fmt: skip
    van = p.dev(
        (
            "vehicle.spawn",
            {"model": "van", "at": {"lane": van_lane, "s": 70.0}, "driver": "none"},
        )
    )
    cars = p.dev(
        ("vehicle.spawn", {"model": "sedan", "at": {"lane": barrier_lane, "s": 8.0}, "driver": "commuter_driver"}),
        ("vehicle.spawn", {"model": "hatchback", "at": {"lane": person_lane, "s": 8.0}, "driver": "commuter_driver"}),
        ("vehicle.spawn", {"model": "suv", "at": {"lane": van_lane, "s": 8.0}, "driver": "commuter_driver"}),
    )  # fmt: skip
    p.mark("drive_a")
    p.step("run", 1500)
    p.mark("drive_b")
    drivers = [{"step": cars, "index": k} for k in range(3)]
    p.expect(
        "stop_short", "stop_short",
        {"from": "drive_a", "to": "drive_b", "props": [barrier], "vehicles": [{"step": van, "index": 0}],
         "people": [{"step": person, "index": 0}], "drivers": drivers, "touch_m": 0.02,
         "person_m": 0.3, "stop_within_m": 40.0},
        "TR-12",
        "each car comes to a stand within 40 m before what is in its lane (a barrier, a person, "
        "a parked van), and its collision boxes never come within 0.02 m of the barrier or the "
        "van, nor within 0.3 m of the person",
    )  # fmt: skip
    for k in range(3):
        p.expect(
            f"moves_{k}", "moved",
            {"from": "drive_a", "to": "drive_b", "id_from": {"step": cars, "index": k},
             "min_m": 20.0, "horizontal": True},
            "AC-3",
            "vehicle.spawn with a commuter as driver drives the car in traffic at once: it moves "
            "at least 20 m towards the obstacle",
            "pre",
        )  # fmt: skip
    return p


def speed_limits() -> Playtest:
    centre = PLAN.intersections["j_34"]["node"]
    p = Playtest(
        "traffic.speed/arterials",
        ["TR-8"],
        "Two minutes of morning traffic around j_34, with four more cars sent from the start "
        "of the long arterial lanes nearby. Every NPC vehicle on the lanes within 130 m keeps "
        "to its lane's limit plus 10% (50 km/h on the arterials, 40 km/h on the streets): "
        "its speed over every 6 ticks stays at or under 55 and 44 km/h.",
        ["--role=solo", "--variation=16", "--save-dir={save_dir}"],
        limits={"wall_s": 900, "cpu_s": 1800, "step_s": 120},
    )
    p.raw["shared"] = {"area": street_area(centre, 130.0)}
    p.step("observe", {"census": {"meta": STREET_META}, "state": True, "every": 6})
    p.dev(("world.reset", {"variation": 16}))
    p.dev(("player.spawn", {"at": {"sidewalk": "sw_34", "s": 58.0}}))
    p.dev(
        ("vehicle.spawn", {"model": "sports", "at": {"lane": "e_34_44:ab1", "s": 4.0}, "driver": "commuter_driver"}),
        ("vehicle.spawn", {"model": "sedan", "at": {"lane": "e_34_44:ba1", "s": 4.0}, "driver": "commuter_driver"}),
        ("vehicle.spawn", {"model": "taxi", "at": {"lane": "e_34_35:ab0", "s": 4.0}, "driver": "taxi_driver"}),
        ("vehicle.spawn", {"model": "hatchback", "at": {"lane": "e_32_33:ab1", "s": 4.0}, "driver": "commuter_driver"}),
    )  # fmt: skip
    p.mark("watch_a")
    p.step("run", 7200)
    p.mark("watch_b")
    p.expect(
        "limit", "lane_speeds",
        {"from": "watch_a", "to": "watch_b", "area": {"$shared": "area"}, "window": 6, "share": 1.1},
        "TR-8",
        "on every lane within 130 m, NPC vehicles never go faster than the lane's limit plus "
        "10%, measured over every 6 ticks",
    )  # fmt: skip
    return p


def panic_horn() -> Playtest:
    p = Playtest(
        "traffic.panic_horn/sidewalk-and-horn",
        ["TR-13", "TR-14"],
        "Traffic and people set to none. The player drives a sedan along a sidewalk at 30 km/h "
        "towards two people standing on it, 40 m and 52 m ahead: each steps out of its path "
        "before it comes, and the car never touches them. Then the player waits in an arterial "
        "lane with a person standing in it 15 m ahead and sounds the horn: the person is out "
        "of the lane within 3 s. Last, standing on the plaza block's south sidewalk with people "
        "along it 6-24 m either side, the player fires a pistol round towards the street: they "
        "run.",
        ["--role=solo", "--variation=17", "--save-dir={save_dir}"],
        limits={"step_s": 60},
    )
    walk = "sw_33"
    walk_blocks = [[[r2(x), r2(z)] for x, z in b["poly"]] for b in PLAN.data["blocks"]]
    lane_id = "e_34_44:ab1"
    edge, _ = PLAN.lanes[lane_id]
    length = PLAN.lane_length(lane_id)
    lane = {"id": lane_id, "width": float(edge["lane_width_m"]),
            "pts": [[r2(q.p[0]), r2(q.p[2])] for q in (PLAN.lane_point(lane_id, 0.0), PLAN.lane_point(lane_id, length))]}  # fmt: skip
    p.step(
        "observe",
        {
            "census": {"meta": STREET_META, "shapes": ["vehicle"]},
            "state": True,
            "every": 3,
        },
    )
    p.dev(("world.reset", {"variation": 17}))
    p.dev(("traffic.set", {"density": 0}))
    car = p.dev(
        (
            "vehicle.spawn",
            {"model": "sedan", "at": {"sidewalk": walk, "s": 6.0}, "driver": "player"},
        )
    )
    p.dev(
        ("npc.spawn", {"archetype": "office_worker", "at": {"sidewalk": walk, "s": 46.0}, "behaviour": "idle"}),
        ("npc.spawn", {"archetype": "tourist", "at": {"sidewalk": walk, "s": 58.0}, "behaviour": "idle"}),
    )  # fmt: skip
    p.step("run", 30)
    p.mark("sidewalk_a")
    p.step(
        "cruise",
        {"entity": {"id": {"$answer": [car, "id"]}}, "kmh": 30.0, "ticks": 420},
    )
    p.step("press", {"brake": 1.0})
    p.step("run", 120)
    p.step("release", ["brake"])
    p.mark("sidewalk_b")
    honk_car = p.dev(
        (
            "vehicle.spawn",
            {"model": "sedan", "at": {"lane": lane_id, "s": 10.0}, "driver": "player"},
        )
    )
    walkers = p.dev(
        (
            "npc.spawn",
            {
                "archetype": "shopper",
                "at": {"lane": lane_id, "s": 25.0},
                "behaviour": "idle",
            },
        ),
    )
    p.step("run", 60)
    p.mark("horn_a")
    p.step("press", {"horn": 1.0})
    p.step("run", 2)
    p.step("release", ["horn"])
    p.step("run", 240)
    p.mark("horn_b")
    p.expect(
        "dodge", "sidewalk_dodge",
        {"from": "sidewalk_a", "to": "sidewalk_b", "vehicle": {"step": car, "index": 0},
         "blocks": walk_blocks, "min_kmh": 20.0, "ahead_m": 60.0, "clear_m": 0.3},
        "TR-13",
        "the two people standing in the path of the sedan (within half its width and 0.3 m of "
        "its line of travel, up to 60 m ahead), which drives on the sidewalk at 20 km/h or more, "
        "step out of it in time: its collision boxes never come within 0.3 m of them and none "
        "goes limp",
    )  # fmt: skip
    p.expect(
        "horn_clear", "horn_clear",
        {"from": "horn_a", "to": "horn_b", "vehicle": {"step": honk_car, "index": 0}, "lane": lane,
         "people": [{"step": walkers, "index": 0}], "ahead_m": 20.0, "within_s": 3.0},
        "TR-14",
        "the person standing in the honking car's lane 15 m ahead is out of the lane (more "
        "than 1.75 m, half its 3.5 m width, from its centre line) within 3 s of the horn",
    )  # fmt: skip
    p.expect(
        "sidewalk_drive", "moved",
        {"from": "sidewalk_a", "to": "sidewalk_b", "id_from": {"step": car}, "min_m": 30.0,
         "horizontal": True},
        "TR-13", "the sedan drives along the sidewalk (at least 30 m)", "pre",
    )  # fmt: skip
    # a gunshot: the player stands on the plaza block's south sidewalk and fires one round
    # towards the street; people stand along the sidewalk 6-24 m either side
    mid = 269.0  # sw_33, s at x = 0 on its south side
    p.dev(("player.spawn", {"at": {"sidewalk": walk, "s": mid}, "heading": 180}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 12}))
    near = []
    for k, (d, arch) in enumerate(
        [(6.0, "office_worker"), (-9.0, "shopper"), (14.0, "tourist"), (-17.0, "office_worker"),
         (21.0, "shopper"), (-24.0, "tourist")]
    ):  # fmt: skip
        near.append(p.dev(("npc.spawn", {"archetype": arch, "at": {"sidewalk": walk, "s": mid + d},
                                         "behaviour": "idle" if k % 2 == 0 else "wander"})))  # fmt: skip
    p.step("observe", {"census": {"meta": STREET_META, "kinds": ["player", "npc"]}, "state": True,
                       "every": 3})  # fmt: skip
    p.step("run", 30)
    p.mark("shot_a")
    p.step("press", {"attack": 1.0})
    p.step("run", 1)
    p.step("release", ["attack"])
    p.step("run", 780)
    p.mark("shot_b")
    p.expect(
        "flee", "gunshot_flee",
        {"from": "shot_a", "to": "shot_b", "people": [{"step": s} for s in near], "near_m": 28.0,
         "start_s": 2.0, "end_s": 12.0, "min_mps": 3.0, "min_gain_m": 20.0, "min_share": 0.9,
         "min_people": 4},
        "TR-13",
        "the player fires one pistol round towards the street: from 2 s to 12 s after it, each "
        "person standing or walking on the sidewalk 6-24 m away runs at least 3 m/s on average, "
        "ends at least 20 m farther from where the player stood and gets farther over at least "
        "90% of the half seconds",
    )  # fmt: skip
    return p


def replay_car_ragdoll() -> Playtest:
    p = Playtest(
        "world.replay/car-and-ragdoll",
        ["AC-15", "AC-17", "FT-9"],
        "One input timeline played twice, the second time with a pause between ticks: the "
        "player drives a sedan at 30 km/h into a person standing in the lane, who goes limp "
        "and is thrown. Traffic and people set to none. The game does the same thing tick for "
        "tick, the car and the ragdoll's bones included.",
        ["--role=solo", "--variation=6", "--save-dir={save_dir}"],
        runs=[{"pace_ms": 0}, {"pace_ms": 4}],
        tags=["physics-sensitive"],
    )
    lane_id = "e_44_54:ab1"
    p.step("observe", {"census": {"meta": ["limp"]}, "every": 3})
    p.dev(("world.reset", {"variation": 6}))
    p.dev(("traffic.set", {"density": 0}))
    car = p.dev(
        (
            "vehicle.spawn",
            {"model": "sedan", "at": {"lane": lane_id, "s": 5.0}, "driver": "player"},
        )
    )
    person = p.dev(
        (
            "npc.spawn",
            {
                "archetype": "tourist",
                "at": {"lane": lane_id, "s": 42.0},
                "behaviour": "idle",
            },
        )
    )
    p.step("observe", {"census": {"meta": ["limp"]}, "every": 3,
                       "bones": {"ids": [{"$answer": [person, "id"]}], "names": ["Hips", "Head", "LeftFoot", "RightHand"]}})  # fmt: skip
    p.mark("start")
    p.step(
        "cruise",
        {"entity": {"id": {"$answer": [car, "id"]}}, "kmh": 30.0, "ticks": 480},
    )
    p.step("press", {"brake": 1.0})
    p.step("run", 150)
    p.step("release", ["brake"])
    p.mark("end")
    p.expect(
        "car_moves", "moved", {"from": "start", "to": "end", "id_from": {"step": car},
                               "min_m": 30.0, "horizontal": True},
        "AC-17", "the player drives the sedan at least 30 m during the timeline", "pre",
    )  # fmt: skip
    p.expect(
        "run_into", "ragdoll",
        {"from": "start", "to": "end", "id_from": {"step": person, "index": 0},
         "trigger": {"near_id_from": {"step": car, "index": 0}, "near_m": 2.5},
         "within_ticks": 18, "min_s": 1.0, "below_m": 0.05, "step_m": 1.0, "ground_y": 0.0,
         "boxes": []},
        "FT-9",
        "the person the sedan runs into at 30 km/h goes limp within 0.2 s of the hit (the "
        "sedan's centre within 2.5 m of them, with 0.1 s more for a shorter front) and stays "
        "limp at least 1.0 s",
    )  # fmt: skip
    p.expect("replay", "replay_equal", {}, "AC-17", "both runs give the same trace")
    return p


# Chapter 8: combat. Every number comes from the weapon table and CB-1 to CB-9, FT-11, FT-12 and
# CM-5 (with chapter 17's clarifications of `damaged` and `aim`). Traffic and people are set to
# none so only the people a play puts down are about.
WEAPON_TABLE = {
    "fists": {"damage": 10, "rate": 2.0, "range": 1.5},
    "bat": {"damage": 25, "rate": 1.25, "range": 1.8},
    "pistol": {"damage": 25, "rate": 3.0, "magazine": 12, "reload_s": 1.6, "range": 50.0},
    "smg": {"damage": 14, "rate": 12.0, "magazine": 30, "reload_s": 2.2, "range": 40.0},
    "shotgun": {"damage": 10, "rate": 1.2, "magazine": 6, "reload_s": 3.0, "range": 20.0},
    "rifle": {"damage": 32, "rate": 6.0, "magazine": 30, "reload_s": 2.6, "range": 120.0},
}  # fmt: skip
ARM_BONES = ["RightHand", "RightLowerArm", "RightUpperArm", "Head", "Hips", "Chest"]
FIGHT_META = ["hostile", "limp", "vehicle", "weapon"]
FIGHT_KINDS = ["player", "npc", "prop", "vehicle"]
PLAZA_Y = 0.15  # the plaza's surface (p_16, base_m)


def fight_watch(p: Playtest, ids: list) -> None:
    """Observe every tick: the census of people, props and vehicles with their fight metadata,
    the state report, the camera and the bones of the player and the listed people."""
    p.step(
        "observe",
        {
            "census": {"meta": FIGHT_META, "kinds": FIGHT_KINDS},
            "state": True,
            "camera": True,
            "every": 1,
            "bones": {"ids": ["player", *ids], "names": ARM_BONES},
        },
    )


def person(
    arch: str, at: list[float], heading: float, behaviour: str
) -> tuple[str, dict]:
    return (
        "npc.spawn",
        {"archetype": arch, "at": at, "heading": heading, "behaviour": behaviour},
    )


def ans(step: int) -> dict:
    """The id an earlier command answered with, for observation settings and bot steps."""
    return {"$answer": [step, "id"]}


def tap(p: Playtest, action: str, then: int) -> None:
    """Press an action for one tick, then run `then` ticks more."""
    p.step("press", {action: 1.0})
    p.step("run", 1)
    p.step("release", [action])
    if then > 0:
        p.step("run", then)


def weapons_range() -> Playtest:
    p = Playtest(
        "combat.weapons/range",
        ["CB-1", "CB-2", "CB-3", "FT-11", "CB-7"],
        "A firing range on the plaza and, for the long guns, down the north-south arterial, "
        "with traffic and people set to none. The player owns all six weapons and cycles "
        "through them, raises the pistol and the rifle, then uses each weapon on people "
        "standing in front (lock-on for the guns, 8-10 m away; within reach for the fists and "
        "the bat): what each hit takes, the rate, the magazine, the reload after it runs dry and "
        "a reload by hand, a gun with nothing left; then people just beyond each weapon's "
        "range, and for the pistol, the SMG and the rifle QA's bot aiming by the camera at "
        "people just inside and just beyond it. People shot at run from the gunshots (TR-13); "
        "lock-on follows them.",
        ["--role=solo", "--variation=21", "--save-dir={save_dir}"],
        limits={"wall_s": 900, "cpu_s": 1800, "step_s": 120},
    )
    fight_watch(p, [])
    p.dev(("world.reset", {"variation": 21}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": [-40.0, PLAZA_Y, 30.0], "heading": 0}))
    p.dev(
        ("player.give", {"weapon": "bat"}),
        ("player.give", {"weapon": "pistol", "ammo": 24}),
        ("player.give", {"weapon": "smg", "ammo": 60}),
        ("player.give", {"weapon": "shotgun", "ammo": 12}),
        ("player.give", {"weapon": "rifle", "ammo": 60}),
    )
    p.step("run", 10)
    p.mark("owned")
    p.expect(
        "fists_owned", "state_value", {"mark": "owned", "path": "player.weapons", "contains": "fists"},
        "CB-3", "fists are always owned: the weapons list holds them with the five given",
    )  # fmt: skip
    # CB-3: cycling, wrapping round, each switch done within 0.5 s
    order = ["fists", "bat", "pistol", "smg", "shotgun", "rifle"]
    for k, want in enumerate(order):
        tap(p, "weapon_next", 29)
        p.mark(f"next_{k}")
        p.state_is(
            f"switch_next_{k}", f"next_{k}", "player.weapon", want, "CB-3",
            f"weapon_next from {order[k - 1]} gives the {want} (the next owned weapon in table "
            f"order, wrapping round) within 0.5 s",
        )  # fmt: skip
    tap(p, "weapon_prev", 29)
    p.mark("prev_0")
    p.state_is(
        "switch_prev", "prev_0", "player.weapon", "shotgun", "CB-3",
        "weapon_prev from the rifle gives the shotgun within 0.5 s",
    )  # fmt: skip
    # FT-11: the rifle (a long gun), then the pistol, raised
    tap(p, "weapon_next", 29)
    p.step("press", {"aim": 1.0})
    p.step("run", 30)
    p.mark("aim_rifle_a")
    p.step("run", 60)
    p.mark("aim_rifle_b")
    p.step("release", ["aim"])
    for want in ("fists", "bat", "pistol"):
        tap(p, "weapon_next", 29)
    p.step("press", {"aim": 1.0})
    p.step("run", 30)
    p.mark("aim_pistol_a")
    p.step("run", 60)
    p.mark("aim_pistol_b")
    p.step("release", ["aim"])
    for gun, (lo, hi) in {
        "rifle": ("aim_rifle_a", "aim_rifle_b"),
        "pistol": ("aim_pistol_a", "aim_pistol_b"),
    }.items():
        p.expect(
            f"aim_pose_{gun}", "aim_pose",
            {"from": lo, "to": hi, "hand_m": 0.25, "max_deg": 20.0, "min_frames": 30},
            "FT-11",
            f"holding aim with the {gun}, from 0.5 s after the press: the right hand within "
            f"0.25 m of the height of RightUpperArm, and the forearm (RightLowerArm to "
            f"RightHand) within 20 degrees of the direction from the hand to the aim point",
        )  # fmt: skip

    # each gun on a person 8-10 m ahead: lock on, hold attack through the magazine
    guns = [
        ("pistol", -40.0, 10.0, 340),
        ("smg", -30.0, 10.0, 330),
        ("shotgun", -20.0, 8.0, 470),
        ("rifle", -10.0, 10.0, 480),
    ]
    for gun, x, dist, ticks in guns:
        w = WEAPON_TABLE[gun]
        p.dev(("player.spawn", {"at": [x, PLAZA_Y, 30.0], "heading": 0}))
        p.dev(("player.give", {"weapon": gun}))
        tgt = p.dev(person("tourist", [x, PLAZA_Y, 30.0 - dist], 180, "idle"))
        fight_watch(p, [ans(tgt)])
        p.step("run", 10)
        p.mark(f"{gun}_full")
        p.state_is(
            f"{gun}_magazine", f"{gun}_full", "player.ammo.magazine", w["magazine"], "CB-1",
            f"the {gun}'s magazine holds {w['magazine']} (the table's size)",
        )  # fmt: skip
        p.step("press", {"lock_target": 1.0})
        p.step("run", 30)
        p.mark(f"{gun}_fire_a")
        p.step("press", {"attack": 1.0})
        burst = round(60 / w["rate"]) * (w["magazine"] - 1) + 20
        p.step("run", burst)
        p.mark(f"{gun}_burst_b")
        p.step("run", ticks - burst)
        p.mark(f"{gun}_fire_b")
        p.step("release", ["attack", "lock_target"])
        pellets = gun == "shotgun"
        p.expect(
            f"{gun}_hits", "hits",
            {"from": f"{gun}_fire_a", "to": f"{gun}_fire_b", "targets": [{"step": tgt}],
             "damage": w["damage"], "min_hits": 4, **({"per_round": 8} if pellets else {})},
            "CB-1",
            (f"every pellet that hits the person {dist:g} m ahead takes 10 (eight per round at "
             "most)" if pellets else f"every hit on the person {dist:g} m ahead takes "
             f"{w['damage']}") + "; health falls by each hit's amount and the person dies on "
            "the hit that takes it to 0, with no hit after",
        )  # fmt: skip
        p.expect(
            f"{gun}_rate", "fire_rate",
            {"from": f"{gun}_fire_a", "to": f"{gun}_burst_b", "rate": w["rate"], "tol": 0.05,
             "min_count": 3},
            "CB-1",
            f"with attack held the {gun} fires {w['rate']:g} rounds per second within 5% "
            "(rounds leaving the magazine)",
        )  # fmt: skip
        p.expect(
            f"{gun}_reload", "reload",
            {"from": f"{gun}_fire_a", "to": f"{gun}_fire_b", "start": "empty",
             "reload_s": w["reload_s"], "tol": 0.1, "magazine": w["magazine"]},
            "CB-1",
            f"the empty magazine refills from the reserve {w['reload_s']:g} s later within 10%",
        )  # fmt: skip
        p.expect(
            f"{gun}_ammo", "ammo_flow",
            {"from": f"{gun}_fire_a", "to": f"{gun}_fire_b", "min_rounds": w["magazine"],
             "min_reloads": 1},
            "CB-2",
            "every change of the ammo is a round taken from the magazine or a reload from the "
            "reserve",
        )  # fmt: skip
        if gun == "pistol":
            p.expect(
                "pistol_kill", "ragdoll",
                {"from": "pistol_fire_a", "to": "pistol_fire_b", "id_from": {"step": tgt},
                 "trigger": {"event": "died"}, "within_ticks": 12, "min_s": 1.0,
                 "below_m": 0.05, "step_m": 1.0, "ground_y": PLAZA_Y},
                "CB-7",
                "health 0 is death: the person shot dead has a died event and goes limp within "
                "0.2 s (12 ticks) of it, staying limp at least 1.0 s, no bone more than 0.05 m "
                "under the ground",
            )  # fmt: skip
            # a reload by hand, then everything fired: with nothing left attack does nothing
            tap(p, "attack", 45)
            p.mark("pistol_reload_a")
            tap(p, "reload", 130)
            p.mark("pistol_reload_b")
            p.expect(
                "pistol_reload_hand", "reload",
                {"from": "pistol_reload_a", "to": "pistol_reload_b", "start": "mark",
                 "reload_s": 1.6, "tol": 0.1, "magazine": 12},
                "CB-2",
                "reload with a part-used magazine refills it from the reserve in 1.6 s within "
                "10%",
            )  # fmt: skip
            p.step("press", {"attack": 1.0})
            p.step("run", 600)
            p.mark("dry_a")
            p.step("run", 60)
            p.mark("dry_b")
            p.step("release", ["attack"])
            p.expect(
                "dry_fire", "dry_fire", {"from": "dry_a", "to": "dry_b"}, "CB-2",
                "with the magazine and the reserve empty, attack held does nothing: the ammo "
                "stays empty and nobody takes a hit",
            )  # fmt: skip
        if gun == "shotgun":
            far = p.dev(person("tourist", [x, PLAZA_Y, 5.0], 180, "idle"))
            fight_watch(p, [ans(far)])
            p.step("run", 10)
            p.step("press", {"lock_target": 1.0})
            p.step("run", 30)
            p.mark("shotgun_far_a")
            p.step("press", {"attack": 1.0})
            p.step("run", 110)
            p.mark("shotgun_far_b")
            p.step("release", ["attack", "lock_target"])
            p.expect(
                "shotgun_range", "untouched",
                {"from": "shotgun_far_a", "to": "shotgun_far_b", "targets": [{"step": far}],
                 "min_rounds": 2},
                "CB-1",
                "the person 25 m ahead, beyond the shotgun's 20 m, takes no hit from two rounds "
                "fired at it",
            )  # fmt: skip

    # melee: the fists and the bat on people within reach, then just beyond it
    for k, (weapon, reach_m, near_m, far_m, hold) in enumerate(
        [("fists", 1.5, 1.2, 2.0, 210), ("bat", 1.8, 1.5, 2.3, 170)]
    ):
        w = WEAPON_TABLE[weapon]
        x = 5.0 + 12.0 * k
        p.dev(("player.spawn", {"at": [x, PLAZA_Y, 30.0], "heading": 0}))
        p.dev(("player.give", {"weapon": weapon}))
        near = p.dev(person("office_worker", [x, PLAZA_Y, 30.0 - near_m], 180, "idle"))
        fight_watch(p, [ans(near)])
        p.step("run", 10)
        p.mark(f"{weapon}_a")
        p.step("press", {"attack": 1.0})
        p.step("run", hold)
        p.mark(f"{weapon}_b")
        p.step("release", ["attack"])
        p.expect(
            f"{weapon}_hits", "hits",
            {"from": f"{weapon}_a", "to": f"{weapon}_b", "targets": [{"step": near}],
             "damage": w["damage"], "min_hits": 4},
            "CB-1",
            f"every blow of the {weapon} on the person {near_m:g} m ahead takes {w['damage']}",
        )  # fmt: skip
        p.expect(
            f"{weapon}_rate", "fire_rate",
            {"from": f"{weapon}_a", "to": f"{weapon}_b", "blows": [{"step": near}],
             "rate": w["rate"], "tol": 0.05, "min_count": 4},
            "CB-1",
            f"with attack held the {weapon} lands {w['rate']:g} blows per second within 5%",
        )  # fmt: skip
        p.dev(("player.spawn", {"at": [x + 6.0, PLAZA_Y, 30.0], "heading": 0}))
        far = p.dev(
            person("office_worker", [x + 6.0, PLAZA_Y, 30.0 - far_m], 180, "idle")
        )
        p.step("run", 10)
        p.mark(f"{weapon}_far_a")
        p.step("press", {"attack": 1.0})
        p.step("run", 150)
        p.mark(f"{weapon}_far_b")
        p.step("release", ["attack"])
        p.expect(
            f"{weapon}_range", "untouched",
            {"from": f"{weapon}_far_a", "to": f"{weapon}_far_b", "targets": [{"step": far}],
             "min_rounds": 0},
            "CB-1",
            f"the person {far_m:g} m ahead, beyond the {weapon}'s {reach_m:g} m, takes no blow "
            "in 2.5 s of attack held",
        )  # fmt: skip

    # the long guns' ranges: QA's bot aims with the camera, down the arterial
    lane_z = 160.0
    p.dev(("player.spawn", {"at": [-71.75, 0.0, lane_z], "heading": 0}))
    p.dev(
        ("player.give", {"weapon": "pistol", "ammo": 24}),
        ("player.give", {"weapon": "smg", "ammo": 60}),
        ("player.give", {"weapon": "rifle", "ammo": 60}),
    )
    spots = {
        "pistol": ((-68.25, 45.0), (-64.75, 55.0)),
        "smg": ((-75.25, 35.0), (-71.75, 45.0)),
        "rifle": ((-68.25, 115.0), (-75.25, 125.0)),
    }
    placed = {}
    for gun, ((xi, di), (xo, do)) in spots.items():
        placed[gun] = (
            p.dev(person("tourist", [xi, 0.0, lane_z - di], 180, "idle")),
            p.dev(person("tourist", [xo, 0.0, lane_z - do], 180, "idle")),
        )
    fight_watch(p, [ans(s) for pair in placed.values() for s in pair])
    p.step("run", 10)
    for gun, (s_in, s_out) in placed.items():
        (xi, di), (xo, do) = spots[gun]
        p.dev(("player.give", {"weapon": gun}))
        tap(p, "reload", 180)
        p.step("aim_at", {"entity": {"id": ans(s_in)}, "bone": "Chest", "ticks": 90})
        p.mark(f"{gun}_in_a")
        p.step(
            "aim_at",
            {
                "entity": {"id": ans(s_in)},
                "bone": "Chest",
                "ticks": 60,
                "hold": {"attack": 1.0},
            },
        )
        p.mark(f"{gun}_in_b")
        p.step("aim_at", {"entity": {"id": ans(s_out)}, "bone": "Chest", "ticks": 90})
        p.mark(f"{gun}_out_a")
        p.step(
            "aim_at",
            {
                "entity": {"id": ans(s_out)},
                "bone": "Chest",
                "ticks": 60,
                "hold": {"attack": 1.0},
            },
        )
        p.mark(f"{gun}_out_b")
        rng = WEAPON_TABLE[gun]["range"]
        d_in = round(math.hypot(xi + 71.75, di), 1)
        d_out = round(math.hypot(xo + 71.75, do), 1)
        p.expect(
            f"{gun}_range_inside", "hits",
            {"from": f"{gun}_in_a", "to": f"{gun}_in_b", "targets": [{"step": s_in}],
             "damage": WEAPON_TABLE[gun]["damage"], "min_hits": 1},
            "CB-1",
            f"aimed by the camera at the person {d_in:g} m away, inside the {gun}'s {rng:g} m, "
            "the rounds hit",
            "pre",
        )  # fmt: skip
        p.expect(
            f"{gun}_range", "untouched",
            {"from": f"{gun}_out_a", "to": f"{gun}_out_b", "targets": [{"step": s_out}],
             "min_rounds": 2},
            "CB-1",
            f"aimed the same way at the person {d_out:g} m away, beyond the {gun}'s {rng:g} m, "
            "the rounds do no damage",
        )  # fmt: skip
    return p


def lock_on() -> Playtest:
    p = Playtest(
        "combat.lock_on/targets",
        ["CM-5", "CB-4"],
        "On the plaza with traffic and people set to none. Two people stand ahead, 12 and 18 m "
        "off: lock_target takes the nearer. A hostile person (unarmed) comes at the player from "
        "22 m: lock_target takes it over the nearer one, the camera keeps it in the middle of "
        "the view and the aim point on its Chest while it runs in, and the pistol stops it. "
        "Then single rounds with lock-on at people standing 15 m away, one each: ten from the "
        "pistol, ten from the rifle, ten from the SMG, after a world reset. People near a gunshot "
        "run from it (TR-13).",
        ["--role=solo", "--variation=22", "--save-dir={save_dir}"],
        limits={"wall_s": 600, "cpu_s": 1200, "step_s": 120},
    )
    fight_watch(p, [])
    p.dev(("world.reset", {"variation": 22}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": [-40.0, PLAZA_Y, 10.0], "heading": 0}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 24}))
    near = p.dev(person("office_worker", [-38.0, PLAZA_Y, -2.0], 180, "idle"))
    farther = p.dev(person("shopper", [-44.0, PLAZA_Y, -8.0], 180, "idle"))
    fight_watch(p, [ans(near), ans(farther)])
    p.step("run", 20)
    p.step("press", {"lock_target": 1.0})
    p.step("run", 30)
    p.mark("near_a")
    p.step("run", 60)
    p.mark("near_b")
    p.step("release", ["lock_target"])
    p.expect(
        "lock_nearest", "lock_on",
        {"from": "near_a", "to": "near_b", "target": {"step": near}, "aim_m": 0.3,
         "middle": 0.3, "aspect": ASPECT, "min_frames": 30},
        "CM-5",
        "lock_target takes the nearer of two people ahead (12.2 m, 9 degrees right; the other "
        "18.4 m, 13 degrees left): from 0.5 s after the press its Chest bone stays in the middle "
        "30% of the view and the aim point within 0.3 m of it",
    )  # fmt: skip
    hostile = p.dev(person("shopper", [-30.0, PLAZA_Y, -10.0], 180, "hostile"))
    fight_watch(p, [ans(near), ans(farther), ans(hostile)])
    p.step("run", 10)
    p.step("press", {"lock_target": 1.0})
    p.step("run", 30)
    p.mark("hostile_a")
    p.step("run", 40)
    p.mark("hostile_b")
    p.step("press", {"attack": 1.0})
    p.step("run", 90)
    p.mark("hostile_c")
    p.step("release", ["attack", "lock_target"])
    p.expect(
        "lock_hostile", "lock_on",
        {"from": "hostile_a", "to": "hostile_b", "target": {"step": hostile}, "aim_m": 0.3,
         "middle": 0.3, "aspect": ASPECT, "min_frames": 30},
        "CM-5",
        "with a hostile person coming in from 22 m (27 degrees right) and a nearer one standing, "
        "lock_target takes the hostile one and, from 0.5 s after the press, keeps it in the middle "
        "30% of the view, the aim point within 0.3 m of its Chest, as it runs",
    )  # fmt: skip
    p.expect(
        "hostile_stopped", "event_seen",
        {"after": "hostile_b", "before": "hostile_c", "name": "died", "where": {}},
        "CB-7", "the pistol stops the hostile person: a died event", "pre",
    )  # fmt: skip
    # CB-4: single rounds at people 15 m away, a fresh one for each round; a world reset first,
    # so nobody from the first part runs through (people flee the shots, TR-13, straight away
    # from the player here, so earlier targets never come back into the way)
    p.dev(("world.reset", {"variation": 22}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": [-35.0, PLAZA_Y, -20.0], "heading": 0}))
    for gun in ("pistol", "rifle", "smg"):
        p.dev(("player.give", {"weapon": gun, "ammo": 30}))
        tap(p, "reload", 180)  # a full magazine for the ten rounds
        bursts = []
        for k in range(10):
            heading = (108 * k) % 360
            h = math.radians(heading)
            at = [
                round(-35.0 + 15.0 * math.sin(h), 2),
                PLAZA_Y,
                round(-20.0 - 15.0 * math.cos(h), 2),
            ]
            tgt = p.dev(person("tourist", at, (heading + 180) % 360, "idle"))
            p.dev(("player.spawn", {"at": [-35.0, PLAZA_Y, -20.0], "heading": heading}))
            fight_watch(p, [ans(tgt)])
            p.step("run", 10)
            p.step("press", {"lock_target": 1.0})
            p.step("run", 30)
            p.mark(f"{gun}_{k}_a")
            tap(p, "attack", 20)
            p.mark(f"{gun}_{k}_b")
            p.step("release", ["lock_target"])
            bursts.append(
                {"from": f"{gun}_{k}_a", "to": f"{gun}_{k}_b", "target": {"step": tgt}}
            )
        floor = 0.45 if gun == "smg" else 0.6
        p.expect(
            f"hit_rate_{gun}", "hit_rate",
            {"bursts": bursts, "min_share": floor, "grace_s": 0.5, "min_rounds": 10},
            "CB-4",
            f"with lock-on at 15 m (from 0.5 s after the press), at least {floor:.0%} of {gun} "
            "rounds hit the person standing still in clear view they are fired at (one round at "
            "each of ten people)",
        )  # fmt: skip
    return p


def armour() -> Playtest:
    p = Playtest(
        "combat.armour/hits",
        ["CB-5", "CB-9"],
        "On the plaza with traffic and people set to none. The player stands with 40 armour and "
        "100 health; an armed hostile person 12 m away fires at the player until the player "
        "falls. Every hit's split between armour and health is read from its damaged event.",
        ["--role=solo", "--variation=23", "--save-dir={save_dir}"],
        limits={"wall_s": 300, "cpu_s": 600, "step_s": 120},
    )
    fight_watch(p, [])
    p.dev(("world.reset", {"variation": 23}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": [-40.0, PLAZA_Y, 30.0], "heading": 0}))
    p.dev(("player.give", {"weapon": "fists", "health": 100, "armour": 40}))
    p.step("run", 5)
    p.mark("armour_a")
    shooter = p.dev(person("crew_a_enforcer", [-40.0, PLAZA_Y, 18.0], 180, "hostile"))
    p.step("run", 1800)
    p.mark("armour_b")
    p.expect(
        "absorb", "armour_split",
        {"from": "armour_a", "to": "armour_b", "share": 0.6, "min_armoured": 2, "min_bare": 1},
        "CB-5",
        "armour takes 60% of each hit (rounded, within a point) until it runs out and health "
        "the rest; then health takes whole hits",
    )  # fmt: skip
    p.expect(
        "shooter_fires", "fires_at",
        {"from": "armour_a", "to": "armour_b", "attackers": [{"step": shooter}], "max_m": 40.0,
         "min_hits": 3},
        "CB-9", "the hostile enforcer 12 m away fires at the player and hits", "pre",
    )  # fmt: skip
    return p


def cover_setup(
    p: Playtest, obstacle: dict, spot: list[float], attackers: list[list[float]]
) -> list[int]:
    """The shared start of both cover runs: the low wall, the player 1.4 m behind it standing,
    two armed hostile people 20 m beyond it; returns the attackers' spawn steps."""
    fight_watch(p, [])
    p.dev(("world.reset", {"variation": 24}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("prop.spawn", {"kind": "low_cover", "at": obstacle["p"], "size": obstacle["size"],
                          "heading": obstacle["heading"]}))  # fmt: skip
    p.dev(("player.spawn", {"at": spot, "heading": 0}))
    p.dev(
        ("player.give", {"weapon": "pistol", "ammo": 60, "health": 100, "armour": 100})
    )
    steps = [p.dev(person("crew_b_enforcer", a, 180, "hostile")) for a in attackers]
    fight_watch(p, [ans(s) for s in steps])
    return steps


def cover_window(p: Playtest, label: str) -> None:
    """Fifteen seconds under fire, the player's health and armour topped up every 3 s."""
    p.mark(f"{label}_a")
    for _ in range(5):
        p.step("run", 180)
        p.dev(("player.give", {"health": 100, "armour": 100}))
    p.mark(f"{label}_b")


def cover_firefight() -> Playtest:
    p = Playtest(
        "combat.cover_firefight/low-wall",
        ["FT-12", "CB-6", "CB-7", "CB-8", "CB-9", "FT-9"],
        "On the plaza with traffic and people set to none. Two armed hostile people stand 20 m "
        "beyond a low wall (2.0 x 1.1 x 0.5 m); the player stands 1.4 m behind it. The game is "
        "played twice from that start: first the player stays standing in the open for 15 s, "
        "then (the game started again) the player takes cover behind the wall and stays there "
        "for the same 15 s, health and armour topped up every 3 s both times. In cover the "
        "player leans out and fires, wounds one attacker below 30 health and shoots the other "
        "dead. Then, after a world reset, a person behind a wall and one behind a parked van "
        "are shot at.",
        ["--role=solo", "--variation=24", "--save-dir={save_dir}"],
        limits={"wall_s": 900, "cpu_s": 1800, "step_s": 120},
    )
    obstacle = {"p": [-30.0, PLAZA_Y, 10.0], "size": [2.0, 1.1, 0.5], "heading": 0}
    spot = [-30.0, PLAZA_Y, 11.65]
    attackers = [[-32.0, PLAZA_Y, -9.0], [-27.0, PLAZA_Y, -11.0]]
    # the open run
    open_att = cover_setup(p, obstacle, spot, attackers)
    p.step("run", 120)
    cover_window(p, "open")
    p.step("restart", {})
    # the cover run: the same start, cover taken during the same warm-up
    cover_att = cover_setup(p, obstacle, spot, attackers)
    p.mark("cover_press")
    p.step("press", {"cover": 1.0})
    p.step("run", 1)
    p.step("release", ["cover"])
    p.step("run", 119)
    cover_window(p, "cover")
    p.expect(
        "cover_enter", "cover_enter",
        {"from": "cover_press", "within_s": 1.0, "box": obstacle, "near_m": 0.6, "ratio": 0.75,
         "ground_y": PLAZA_Y},
        "FT-12",
        "pressing cover 1.4 m from the 1.1 m wall puts the player in cover within 1.0 s: cover "
        "true, within 0.6 m of the wall, the hips at most 75% of their standing height",
    )  # fmt: skip
    p.expect(
        "cover_hold", "cover_hold",
        {"from": "cover_a", "to": "cover_b", "box": obstacle, "near_m": 0.6, "ratio": 0.75,
         "ground_y": PLAZA_Y, "standing_mark": "cover_press"},
        "FT-12",
        "staying in cover (aim not held), on every frame cover is true, the player within 0.6 m "
        "of the wall and the hips at most 75% of standing height",
    )  # fmt: skip
    p.expect(
        "cover_cuts", "cover_cuts",
        {"open": {"from": "open_a", "to": "open_b", "attackers": [{"step": s} for s in open_att]},
         "cover": {"from": "cover_a", "to": "cover_b", "attackers": [{"step": s} for s in cover_att]},
         "max_ratio": 0.4, "min_open_hits": 8},
        "CB-8",
        "over the same 15 s from the same start, the two attackers' damage to the player in cover "
        "is at most 40% of their damage to the player standing in the open (with at least 8 hits "
        "in the open)",
    )  # fmt: skip
    p.expect(
        "attackers_fire", "fires_at",
        {"from": "open_a", "to": "open_b", "attackers": [{"step": s} for s in open_att],
         "max_m": 40.0, "min_hits": 1},
        "CB-9",
        "hostile enforcers with the player 21-23 m away and in sight fire at the player: each "
        "lands hits",
    )  # fmt: skip
    # leaning out and firing from cover
    p.step("press", {"aim": 1.0})
    p.mark("lean_a")
    p.step("run", 60)
    p.mark("lean_fire_a")
    p.step("press", {"attack": 1.0})
    p.step("run", 30)
    p.mark("lean_fire_b")
    p.step("release", ["attack"])
    p.step("run", 10)
    p.expect(
        "fire_from_cover", "lean_out",
        {"from": "lean_a", "within_s": 1.0, "rise_m": 0.30, "fire_from": "lean_fire_a",
         "fire_to": "lean_fire_b"},
        "CB-8",
        "in cover, holding aim leans out: the Head bone rises at least 0.30 m within 1.0 s, cover "
        "still true, and attack fires",
    )  # fmt: skip
    # wound one attacker below 30 health, then shoot the other dead: QA's bot aims at each
    p.dev(("player.give", {"health": 100, "armour": 100, "ammo": 24}))
    p.step("release", ["aim"])
    p.step(
        "aim_at", {"entity": {"id": ans(cover_att[0])}, "bone": "Chest", "ticks": 30}
    )
    p.mark("wound_a")
    p.step("aim_at", {"entity": {"id": ans(cover_att[0])}, "bone": "Chest", "ticks": 45,
                      "hold": {"attack": 1.0}})  # fmt: skip
    p.step("run", 30)
    p.dev(("player.give", {"health": 100, "armour": 100}))
    p.step("run", 570)
    p.mark("wound_b")
    p.expect(
        "retreat", "retreat",
        {"from": "wound_a", "to": "wound_b", "enforcers": [{"step": s} for s in cover_att],
         "below": 30, "within_s": 10.0, "min_m": 10.0},
        "CB-9",
        "the attacker hit three times from cover (25 health left) ends at least 10 m farther "
        "from the player within 10 s of dropping below 30",
    )  # fmt: skip
    p.dev(("player.give", {"health": 100, "armour": 100}))
    p.step(
        "aim_at", {"entity": {"id": ans(cover_att[1])}, "bone": "Chest", "ticks": 30}
    )
    p.mark("kill_a")
    p.step("aim_at", {"entity": {"id": ans(cover_att[1])}, "bone": "Chest", "ticks": 80,
                      "hold": {"attack": 1.0}})  # fmt: skip
    p.step("run", 120)
    p.mark("kill_b")
    p.expect(
        "kill_hits", "hits",
        {"from": "kill_a", "to": "kill_b", "targets": [{"step": cover_att[1]}], "damage": 25,
         "min_hits": 4},
        "CB-7",
        "the other attacker, shot four times with the pistol, dies on the hit that takes its "
        "health to 0: its died event",
    )  # fmt: skip
    p.expect(
        "kill_ragdoll", "ragdoll",
        {"from": "kill_a", "to": "kill_b", "id_from": {"step": cover_att[1]},
         "trigger": {"event": "died"}, "within_ticks": 12, "min_s": 1.0, "below_m": 0.05,
         "step_m": 1.0, "ground_y": PLAZA_Y},
        "CB-7",
        "dead, it goes limp within 0.2 s of its died event and stays limp; no bone more than "
        "0.05 m under the ground",
    )  # fmt: skip
    # leaving cover
    p.step("press", {"move_back": 1.0})
    p.mark("leave_a")
    p.step("run", 60)
    p.mark("leave_b")
    p.step("release", ["move_back"])
    p.expect(
        "cover_leave", "cover_leave",
        {"from": "leave_a", "to": "leave_b", "box": obstacle, "within_s": 0.5, "near_m": 0.6},
        "FT-12",
        "moving away from the wall leaves cover: cover false within 0.5 s and the player more "
        "than 0.6 m from it after a second",
    )  # fmt: skip
    # no shots through walls or a car's body
    p.dev(("world.reset", {"variation": 24}))
    p.dev(("traffic.set", {"density": 0}))
    for k, (label, block) in enumerate(
        [("wall", ("prop.spawn", {"kind": "wall", "at": [-10.0, PLAZA_Y, 25.0], "heading": 0})),
         ("van", ("vehicle.spawn", {"model": "van", "at": [2.0, PLAZA_Y, 25.0], "heading": 90,
                                    "driver": "none"}))]
    ):  # fmt: skip
        x = -10.0 if k == 0 else 2.0
        p.dev(block)
        hidden = p.dev(person("tourist", [x, PLAZA_Y, 20.0], 180, "idle"))
        p.dev(("player.spawn", {"at": [x, PLAZA_Y, 30.0], "heading": 0}))
        p.dev(("player.give", {"weapon": "pistol", "ammo": 24}))
        fight_watch(p, [ans(hidden)])
        tap(p, "reload", 120)
        p.step("press", {"lock_target": 1.0})
        p.step("run", 3)
        p.mark(f"{label}_a")
        p.step("press", {"attack": 1.0})
        p.step("run", 50)
        p.mark(f"{label}_b")
        p.step("release", ["attack", "lock_target"])
        p.expect(
            f"through_{label}", "untouched",
            {"from": f"{label}_a", "to": f"{label}_b", "targets": [{"step": hidden}],
             "min_rounds": 3},
            "CB-6",
            "three rounds fired with lock-on at a person 10 m away behind a "
            + ("wall (4.0 x 2.5 m, 5 m ahead)" if k == 0 else "parked van broadside, 5 m ahead")
            + ": nobody is hit through it",
        )  # fmt: skip
    return p


def crew_hostility() -> Playtest:
    p = Playtest(
        "combat.crew_hostility/turf",
        ["CB-9", "AC-5"],
        "On the parking lot inside turf_crew_a, with traffic and people set to none. Two crew_a "
        "lookouts and four enforcers stand guard 20-28 m in front of the player, a low wall "
        "(2.0 x 1.1 x 0.5 m) 4-5 m behind each enforcer. The player raises a pistol and keeps "
        "aiming: after 5 s the crew turns hostile, the lookouts run off and the enforcers take "
        "cover and fire. After a world reset the same crew stands again, and the player punches "
        "a lookout: the whole crew turns hostile.",
        ["--role=solo", "--variation=25", "--save-dir={save_dir}"],
        limits={"wall_s": 600, "cpu_s": 1200, "step_s": 120},
    )
    lookouts = [[-106.0, PLAZA_Y, 88.0], [-93.0, PLAZA_Y, 82.0]]
    enforcers = [[-110.0, PLAZA_Y, 92.0], [-102.0, PLAZA_Y, 90.0], [-96.0, PLAZA_Y, 92.0],
                 [-89.0, PLAZA_Y, 90.0]]  # fmt: skip
    walls = [
        {
            "p": [e[0], PLAZA_Y, e[2] - 5.0 + (k % 2)],
            "size": [2.0, 1.1, 0.5],
            "heading": 0,
        }
        for k, e in enumerate(enforcers)
    ]

    def crew() -> tuple[list[int], list[int]]:
        look = [p.dev(person("crew_a_lookout", at, 180, "guard")) for at in lookouts]
        enf = [p.dev(person("crew_a_enforcer", at, 180, "guard")) for at in enforcers]
        fight_watch(p, [ans(s) for s in look + enf])
        return look, enf

    fight_watch(p, [])
    p.dev(("world.reset", {"variation": 25}))
    p.dev(("traffic.set", {"density": 0}))
    for w in walls:
        p.dev(
            (
                "prop.spawn",
                {"kind": "low_cover", "at": w["p"], "size": w["size"], "heading": 0},
            )
        )
    p.dev(("player.spawn", {"at": [-100.0, PLAZA_Y, 112.0], "heading": 0}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 24, "armour": 100}))
    look, enf = crew()
    p.step("run", 30)
    p.mark("aim_a")
    p.step("press", {"aim": 1.0})
    for _ in range(10):
        p.step("run", 120)
        p.dev(("player.give", {"health": 100, "armour": 100}))
    p.mark("aim_b")
    p.step("release", ["aim"])
    members = [{"step": s} for s in look + enf]
    p.expect(
        "turn_hostile_aim", "turn_hostile",
        {"from": "aim_a", "to": "aim_b", "members": members, "trigger": "aim", "after_s": 5.0,
         "within_s": 2.0},
        "CB-9",
        "with the player aiming a pistol inside turf_crew_a, all six crew members' hostile "
        "metadata turns true after 5.0 s and by 7.0 s, none before",
    )  # fmt: skip
    p.expect(
        "lookouts_flee", "flee_away",
        {"from": "aim_a", "to": "aim_b", "people": [{"step": s} for s in look], "min_m": 20.0,
         "within_s": 10.0},
        "CB-9",
        "each hostile lookout ends at least 20 m farther from the player within 10 s of turning "
        "hostile, its hostile metadata still true",
    )  # fmt: skip
    p.expect(
        "enforcers_cover", "reach_cover",
        {"from": "aim_a", "to": "aim_b", "crew": members, "enforcers": [{"step": s} for s in enf],
         "boxes": walls, "within_s": 10.0, "near_m": 1.0, "min_share": 0.5},
        "CB-9",
        "within 10 s of the crew turning hostile, at least half of the four hostile enforcers "
        "stand within 1.0 m of one of the low walls",
    )  # fmt: skip
    p.expect(
        "enforcers_fire", "fires_at",
        {"from": "aim_a", "to": "aim_b", "attackers": [{"step": s} for s in enf], "max_m": 40.0,
         "min_hits": 1},
        "CB-9",
        "each hostile enforcer, the player 20-30 m away and in sight, fires at the player and "
        "hits",
    )  # fmt: skip
    p.expect(
        "hostile_meta", "meta_value",
        {"mark": "aim_b", "id_from": {"step": enf[0]}, "key": "hostile", "equals": True},
        "AC-5", "an enforcer attacking the player carries hostile metadata true",
    )  # fmt: skip
    # the same crew again; the player punches a lookout
    p.dev(("world.reset", {"variation": 25}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(
        (
            "player.spawn",
            {"at": [lookouts[0][0], PLAZA_Y, lookouts[0][2] + 1.0], "heading": 0},
        )
    )
    p.dev(("player.give", {"weapon": "fists", "health": 100, "armour": 100}))
    look2, enf2 = crew()
    p.step("run", 30)
    p.mark("hit_a")
    p.step("press", {"attack": 1.0})
    p.step("run", 2)
    p.step("release", ["attack"])
    p.step("run", 180)
    p.mark("hit_b")
    p.expect(
        "turn_hostile_hit", "turn_hostile",
        {"from": "hit_a", "to": "hit_b", "members": [{"step": s} for s in look2 + enf2],
         "trigger": "hit", "within_s": 2.0},
        "CB-9",
        "the player punches a lookout: every crew_a member turns hostile within 2.0 s of the hit",
    )  # fmt: skip
    return p


# ------------------------------------------------------------------ crime and the police (chapter 9)
ALERT_META = ["vehicle", "seat", "hostile", "limp", "weapon", "state", "approach"]
ALERT_KINDS = ["player", "npc", "vehicle", "signal", "prop"]
POLICE_TOP_KMH = {
    "police": 210.0,
    "tactical_van": 150.0,
}  # chapter 6's table, the top of each band
SPRINT_MPS = 9.6  # FT-1's sprint, the top of its band
STATION = PLAN.pois["police_station_downtown"]
HOSPITAL = PLAN.pois["hospital_downtown"]


def alert_watch(
    p: Playtest, every: int, shapes: bool = False, ids: list | None = None
) -> None:
    """Observe the census (police and everyone else, with the metadata the alert checks read,
    the in-view flag and, when asked, vehicles' collision boxes), the state report, the camera
    and the bones of the player and the people in `ids` (for QA's aiming bot)."""
    census: dict = {"meta": ALERT_META, "kinds": ALERT_KINDS, "view": True}
    if shapes:
        census["shapes"] = ["vehicle"]
    obs: dict = {"census": census, "state": True, "camera": True, "every": every}
    if ids:
        obs["bones"] = {"ids": ["player", *ids], "names": ARM_BONES}
    p.step("observe", obs)


def on_sidewalk(x: float, z: float) -> dict:
    """The sidewalk anchor nearest to a point (every sidewalk ring sampled every 0.5 m)."""
    best = None
    for sid, sw in PLAN.sidewalks.items():
        ring = sw["ring"]
        total = sum(
            math.dist(ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))
        )
        s = 0.0
        while s < total:
            q = PLAN.sidewalk_point(sid, s).p
            d = math.hypot(q[0] - x, q[2] - z)
            if best is None or d < best[0]:
                best = (d, sid, round(s, 1))
            s += 0.5
    return {"sidewalk": best[1], "s": best[2]}


def buildings() -> list:
    """Every building's footprint as [x, z] corners: each parcel with a height, inset by its
    setback (plan FORMAT.md)."""
    out = []
    for parcel in PLAN.data["parcels"]:
        if float(parcel.get("height_m", 0.0)) <= 0.0:
            continue
        poly = inset(parcel["poly"], float(parcel.get("setback_m", 0.0)))
        out.append([[r2(x), r2(z)] for x, z in poly])
    return out


def road_sections(trim: float = 7.5) -> list:
    """Every road as a section between junction boxes: its centreline from end a to end b
    (trimmed `trim` m at each junction), its carriageway's width."""
    out = []
    for eid, e in PLAN.edges.items():
        if e["class"] == "highway":
            continue
        pts = [[r2(x), r2(z)] for x, _y, z in PLAN.centreline(e)]
        (ax, az), (bx, bz) = pts[0], pts[-1]
        length = math.hypot(bx - ax, bz - az)
        if length <= 2 * trim + 5.0:
            continue
        ux, uz = (bx - ax) / length, (bz - az) / length
        pts = [
            [r2(ax + ux * trim), r2(az + uz * trim)],
            [r2(bx - ux * trim), r2(bz - uz * trim)],
        ]
        width = float(e["lane_width_m"]) * len(e["lanes"])
        out.append({"id": eid, "pts": pts, "width": width})
    return out


def road_reach(starts: list[tuple[str, str]], limit: float = 450.0) -> dict:
    """{"edge|dir": {edge: [metres from the far end of that edge, the way it is driven, to the
    entry end of the other edge, "a" or "b"]}} by road (shortest, along the plan's edges in
    their directions of travel; every turn but a U-turn onto the same edge), up to `limit`."""

    def ends(eid: str, d: str) -> tuple[str, str]:
        e = PLAN.edges[eid]
        return (e["a"], e["b"]) if d == "ab" else (e["b"], e["a"])

    def length(eid: str) -> float:
        pts = PLAN.centreline(PLAN.edges[eid])
        return sum(
            math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][2] - pts[i][2])
            for i in range(len(pts) - 1)
        )

    out = {}
    for eid, d in starts:
        far = ends(eid, d)[1]
        best: dict = {}
        todo = [(0.0, far, eid)]
        while todo:
            todo.sort()
            dist, node, came = todo.pop(0)
            for oid, o in PLAN.edges.items():
                if o["class"] == "highway" or oid == came:
                    continue
                for od in ("ab", "ba"):
                    if o["oneway"] and od == "ba":
                        continue
                    start, end = ends(oid, od)
                    if start != node:
                        continue
                    if oid in best and best[oid][0] <= dist:
                        continue
                    best[oid] = [round(dist, 1), "a" if od == "ab" else "b"]
                    nxt = dist + length(oid)
                    if nxt <= limit:
                        todo.append((nxt, end, oid))
        out[f"{eid}|{d}"] = best
    return out


def alert_story(p: Playtest, police: list | None = None) -> None:
    p.expect(
        "honest", "alert_honest", {"from": "start", "to": "end", "police": police or []},
        "AL-4",
        "every rise of the level follows a crime a police officer saw at most 1.0 s before, or "
        "one others saw 10-11 s before, to the level AL-4 gives; it drops only to 0, on an "
        "escape, an arrest or a death",
    )  # fmt: skip


def crime_table() -> Playtest:
    me = [-3.0, PLAZA_Y, 4.0]
    p = Playtest(
        "alert.crime_table/on-foot",
        ["AL-1", "AL-2", "AL-4"],
        "On the plaza with traffic and people set to none, a police officer stands 14 m ahead "
        "of the player, watching. The player punches a tourist standing in front of them "
        "(assault), then shoots a second tourist 10 m away dead with the pistol (a burst of "
        "shots fired, an assault and a murder).",
        ["--role=solo", "--variation=41", "--save-dir={save_dir}"],
        limits={"wall_s": 300, "cpu_s": 600, "step_s": 120},
    )
    alert_watch(p, 1)
    p.dev(("world.reset", {"variation": 41}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": me, "heading": 0}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 24}))
    p.dev(("player.give", {"weapon": "fists"}))
    cop = p.dev(person("police_officer", [me[0], PLAZA_Y, me[2] - 14.0], 180, "idle"))
    first = p.dev(person("tourist", [me[0], PLAZA_Y, me[2] - 1.1], 180, "idle"))
    second = p.dev(person("tourist", [me[0] + 6.0, PLAZA_Y, me[2] - 8.0], 225, "idle"))
    alert_watch(p, 1, ids=[ans(second)])
    p.step("run", 30)
    p.mark("start")
    p.mark("punch")
    tap(p, "attack", 90)
    p.mark("after_punch")
    p.dev(("player.give", {"weapon": "pistol"}))
    p.step("run", 20)
    p.mark("shoot")
    p.step(
        "aim_at",
        {
            "entity": {"id": ans(second)},
            "bone": "Chest",
            "ticks": 150,
            "hold": {"attack": 1.0},
        },
    )
    p.step("run", 60)
    p.mark("after_kill")
    p.mark("end")
    p.expect(
        "assault_event", "crime_event",
        {"from": "punch", "to": "after_punch", "type": "assault", "seen_by": [{"step": cop}], "within_s": 1.0,
         "count": 1},
        "AL-1",
        "punching the tourist is one assault, its crime event within 1.0 s, the watching officer "
        "among its witnesses",
    )  # fmt: skip
    p.expect(
        "police_report", "alert_rise",
        {"from": "punch", "to": "after_punch", "type": "assault", "level": 1, "max_s": 1.0},
        "AL-2", "seen by a police officer, the assault raises the level to 1 within 1.0 s",
    )  # fmt: skip
    p.expect(
        "burst_event", "crime_event",
        {"from": "shoot", "to": "after_kill", "type": "shots_fired", "seen_by": [{"step": cop}], "count": 1},
        "AL-1", "the rounds at the second tourist, less than 3 s apart, are one shots_fired",
    )  # fmt: skip
    p.expect(
        "murder_event", "crime_event",
        {"from": "shoot", "to": "after_kill", "type": "murder", "seen_by": [{"step": cop}], "count": 1,
         "within_s": 3.0},
        "AL-1", "killing the second tourist is one murder, seen by the officer",
    )  # fmt: skip
    p.expect(
        "levels", "alert_levels", {"at": {"after_punch": 1, "after_kill": 4}},
        "AL-4",
        "the level is 1 after the assault (0 below its level 1), and 4 after the shooting: "
        "shots fired takes 1 to 2 (below 2), the assault on the second tourist 2 to 3 (at or "
        "above 1, one more), the murder 3 to 4 (at or above 2, one more)",
    )  # fmt: skip
    alert_story(p, [{"step": cop}])
    del first
    return p


def phone_in() -> Playtest:
    me = [-3.0, PLAZA_Y, 4.0]
    p = Playtest(
        "alert.phone_in/civilian",
        ["AL-1", "AL-2"],
        "On the plaza with traffic and people set to none and no police about. The player "
        "punches a tourist while a shopper watches from 12 m: the shopper phones it in. After "
        "a world reset, the player punches another tourist with a second shopper watching, "
        "then shoots both dead within 10 s: nobody is left to phone it in.",
        ["--role=solo", "--variation=42", "--save-dir={save_dir}"],
        limits={"wall_s": 300, "cpu_s": 600, "step_s": 120},
    )
    alert_watch(p, 2)
    p.dev(("world.reset", {"variation": 42}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": me, "heading": 0}))
    p.dev(("player.give", {"weapon": "fists"}))
    p.dev(person("tourist", [me[0], PLAZA_Y, me[2] - 1.1], 180, "idle"))
    watcher = p.dev(person("shopper", [me[0] + 8.0, PLAZA_Y, me[2] - 9.0], 220, "idle"))
    p.step("run", 30)
    p.mark("start")
    p.mark("punch")
    tap(p, "attack", 780)
    p.mark("after_call")
    p.dev(("world.reset", {"variation": 43}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": me, "heading": 0}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 36}))
    p.dev(("player.give", {"weapon": "fists"}))
    victim = p.dev(person("tourist", [me[0], PLAZA_Y, me[2] - 1.1], 180, "idle"))
    second = p.dev(person("shopper", [me[0] + 8.0, PLAZA_Y, me[2] - 9.0], 220, "idle"))
    alert_watch(p, 2, ids=[ans(victim), ans(second)])
    p.step("run", 30)
    p.mark("punch2")
    tap(p, "attack", 30)
    p.dev(("player.give", {"weapon": "pistol"}))
    p.step("run", 20)
    p.step(
        "aim_at",
        {
            "entity": {"id": ans(victim)},
            "bone": "Chest",
            "ticks": 120,
            "hold": {"attack": 1.0},
        },
    )
    p.step(
        "aim_at",
        {
            "entity": {"id": ans(second)},
            "bone": "Chest",
            "ticks": 150,
            "hold": {"attack": 1.0},
        },
    )
    p.step("run", 720)
    p.mark("silent_end")
    p.mark("end")
    p.expect(
        "witnessed", "crime_event",
        {"from": "punch", "to": "after_call", "type": "assault", "seen_by": [{"step": watcher}]},
        "AL-1", "the shopper watching from 12 m is among the assault's witnesses",
    )  # fmt: skip
    p.expect(
        "phoned_in", "alert_rise",
        {"from": "punch", "to": "after_call", "type": "assault", "level": 1, "min_s": 10.0, "max_s": 11.0},
        "AL-2",
        "seen only by a civilian, the assault raises the level 10 s (within 1 s) after it, to 1",
    )  # fmt: skip
    p.expect(
        "dead_witness", "alert_steady", {"from": "punch2", "to": "silent_end", "level": 0},
        "AL-2",
        "with both witnesses shot dead within 10 s of each crime, nobody phones anything in: "
        "the level stays 0 for 12 s after the last of them",
    )  # fmt: skip
    alert_story(p)
    return p


def red_light() -> Playtest:
    stop = next(s for s in stop_lines("j_34") if s["approach"] == "j_34<e_33_34")
    (x0, z0), (x1, z1) = stop["line"]
    lane = "e_33_34:ab1"
    start = PLAN.lane_point(lane, PLAN.lane_length(lane) - 70.0)
    kerb_x = min(x0, x1) - 2.5
    watcher_at = point(on_sidewalk(kerb_x, z0 - 6.0))
    junction = PLAN.nodes["j_34"]["p"]
    p = Playtest(
        "alert.red_light/patrol",
        ["AL-2", "AL-6", "AL-7"],
        "Morning, traffic and people set to none. The player drives south on the arterial into "
        "j_34 against its red light, with a police officer standing on the corner beside the "
        "stop line; then drives on 120 m and stops. Police respond to level 1.",
        ["--role=solo", "--variation=44", "--save-dir={save_dir}"],
        limits={"wall_s": 600, "cpu_s": 1200, "step_s": 200},
    )
    p.raw["shared"] = {"buildings": buildings()}
    alert_watch(p, 6)
    p.dev(("world.reset", {"variation": 44}))
    p.dev(("traffic.set", {"density": 0}))
    cop = p.dev(person("police_officer", watcher_at, 90, "idle"))
    car = p.dev(("vehicle.spawn", {"model": "sedan", "at": {"lane": lane, "s": round(PLAN.lane_length(lane) - 70.0, 2)},
                             "driver": "player"}))  # fmt: skip
    p.step("run", 30)
    for state in ("green", "red"):  # the light just turned red
        p.step("wait_for", {"near": {"kind": "signal", "p": [junction[0], 0.0, junction[2]], "within_m": 40.0,
                                     "meta": {"approach": "j_34<e_33_34", "state": state}}, "max_ticks": 5400})  # fmt: skip
    p.mark("start")
    p.mark("drive")
    p.step("cruise", {"entity": {"id": ans(car)}, "kmh": 40.0, "ticks": 900})
    p.step("cruise", {"entity": {"id": ans(car)}, "kmh": 0.0, "ticks": 240})
    p.mark("stopped")
    p.step("run", 3600)
    p.mark("end")
    del start, x1, z1
    p.expect(
        "red_light_event", "crime_event",
        {"from": "drive", "to": "stopped", "type": "red_light", "seen_by": [{"step": cop}], "within_s": 15.0,
         "count": 1},
        "AL-1", "crossing j_34's stop line on red is one red_light, seen by the officer on the corner",
    )  # fmt: skip
    p.expect(
        "police_report", "alert_rise",
        {"from": "drive", "to": "end", "type": "red_light", "level": 1, "max_s": 1.0},
        "AL-2", "seen by the police officer, the red light raises the level to 1 within 1.0 s",
    )  # fmt: skip
    p.expect(
        "arrival", "police_arrival",
        {"from": "drive", "to": "end", "within_s": 60.0, "reach_m": 25.0, "ignore": [{"step": cop}],
         "clear_m": 100.0},
        "AL-6",
        "at level 1 the first police unit (a police vehicle, or an officer on foot, other than "
        "the officer on the corner) gets within 25 m of the player within 60 s",
    )  # fmt: skip
    p.expect(
        "origin", "police_origin", {"from": "drive", "to": "end", "min_m": 100.0},
        "AL-7",
        "every police unit new to the world first appears at least 100 m from the player and "
        "outside the camera's view",
    )  # fmt: skip
    p.expect(
        "kinematics", "police_kinematics",
        {"from": "drive", "to": "end", "top_kmh": POLICE_TOP_KMH, "foot_mps": SPRINT_MPS,
         "buildings": {"$shared": "buildings"}},
        "AL-7",
        "police units move at most 1.1 times their model's top speed (210 km/h for police, 150 "
        "km/h for the tactical van) or, on foot, 1.1 times the sprint's 9.6 m/s, and never stand "
        "inside a building",
    )  # fmt: skip
    alert_story(p, [{"step": cop}])
    return p


def roadblock() -> Playtest:
    lane = "e_04_14:ab1"
    begin = PLAN.lane_point(lane, 12.0).p
    eastbound = ["e_04_14", "e_14_24", "e_24_34", "e_34_44"]
    p = Playtest(
        "alert.roadblock/arterial",
        ["AL-8", "CB-10"],
        "Morning, traffic and people set to none. At the west end of the long east-west "
        "arterial, the player shoots a police officer standing 10 m away (level 3), is put in "
        "a sedan on the arterial's eastbound lane 10 s later and drives east at 15 km/h for 100 s.",
        ["--role=solo", "--variation=45", "--save-dir={save_dir}"],
        limits={"wall_s": 900, "cpu_s": 1800, "step_s": 300},
    )
    p.raw["shared"] = {
        "roads": road_sections(),
        "reach": road_reach([(e, "ab") for e in eastbound]),
    }
    alert_watch(p, 6, shapes=True)
    p.dev(("world.reset", {"variation": 45}))
    p.dev(("traffic.set", {"density": 0}))
    me = on_sidewalk(begin[0] + 6.0, begin[2] + 6.0)
    here = point(me)
    p.dev(("player.spawn", {"at": me, "heading": 90}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 24, "armour": 100}))
    cop = p.dev(
        person("police_officer", [here[0] + 10.0, here[1], here[2]], 270, "idle")
    )
    p.step("run", 30)
    p.mark("start")
    p.step("aim_at", {"entity": {"id": ans(cop)}, "bone": "Chest", "ticks": 40})
    p.step(
        "aim_at",
        {
            "entity": {"id": ans(cop)},
            "bone": "Chest",
            "ticks": 2,
            "hold": {"attack": 1.0},
        },
    )
    p.step("run", 60)
    p.mark("level3")
    p.step("run", 600)
    p.mark("fought")
    car = p.dev(
        (
            "vehicle.spawn",
            {"model": "sedan", "at": {"lane": lane, "s": 12.0}, "driver": "player"},
        )
    )
    p.step("run", 30)
    p.mark("drive")
    p.step("cruise", {"entity": {"id": ans(car)}, "kmh": 15.0, "ticks": 6000})
    p.mark("end")
    p.expect(
        "roadblock", "roadblock",
        {"from": "start", "to": "end", "within_s": 90.0, "ahead_m": 300.0, "roads": {"$shared": "roads"},
         "reach": {"$shared": "reach"}},
        "AL-8",
        "within 90 s of level 3, while the player drives, at least two police vehicles stand "
        "below 1 km/h across a road ahead (each within 30 degrees of square, together covering "
        "70% of the carriageway) within 300 m by road along lanes the player can reach",
    )  # fmt: skip
    p.expect(
        "fight_back", "police_force",
        {"from": "start", "to": "fought", "fight": True, "within_s": 15.0},
        "CB-10",
        "from level 3 the police fight: the officer 10 m away, with a clear line to the player, "
        "lands a hit within 15 s",
    )  # fmt: skip
    del begin
    alert_story(p, [{"step": cop}])
    return p


def arrest() -> Playtest:
    me = [-3.0, PLAZA_Y, 4.0]
    p = Playtest(
        "alert.arrest/standing",
        ["AL-9", "CB-10"],
        "On the plaza with traffic and people set to none. The player, holding a pistol and "
        "$1,200, punches a tourist with a police officer watching from 3.0 m (level 1) and "
        "stands still for 6 s; then the player is put 1.0 m from the officer and stands still.",
        ["--role=solo", "--variation=46", "--save-dir={save_dir}"],
        limits={"wall_s": 300, "cpu_s": 600, "step_s": 120},
    )
    alert_watch(p, 1)
    p.dev(("world.reset", {"variation": 46}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": me, "heading": 0}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 24, "money": 700}))
    p.dev(("player.give", {"weapon": "fists"}))
    cop = p.dev(person("police_officer", [me[0] + 3.0, PLAZA_Y, me[2]], 270, "idle"))
    p.dev(person("tourist", [me[0], PLAZA_Y, me[2] - 1.1], 180, "idle"))
    p.step("run", 30)
    p.mark("start")
    tap(p, "attack", 360)
    p.mark("kept_off")
    p.dev(("player.spawn", {"at": [me[0] + 2.0, PLAZA_Y, me[2]], "heading": 90}))
    p.step("run", 2)
    p.mark("beside")
    p.step("run", 900)
    p.mark("end")
    p.expect(
        "no_arrest_at_3m", "arrest",
        {"from": "start", "to": "kept_off", "officer": {"step": cop}, "expect": False},
        "AL-9", "with the officer 3.0 m off the player is not arrested",
    )  # fmt: skip
    p.expect(
        "arrested", "arrest",
        {"from": "beside", "to": "end", "officer": {"step": cop}, "near_m": 2.0, "min_s": 3.0, "max_s": 3.5},
        "AL-9",
        "at level 1, standing still with the officer 1.0 m away, the player is arrested 3.0 s "
        "(to 3.5 s) after the officer stood within 2.0 m",
    )  # fmt: skip
    p.expect(
        "came_back", "came_back",
        {"from": "beside", "to": "end", "after": "arrested", "poi": STATION["id"], "respawn": STATION["respawn"],
         "within_s": 10.0, "fine": 500, "weapons": ["fists"]},
        "AL-9",
        "within 10 s of the arrest the player comes back (a teleport and a respawned event) "
        "within 2 m of the police station's respawn point, at level 0, with only fists and "
        "$500 less",
    )  # fmt: skip
    p.expect(
        "no_force", "police_force", {"from": "start", "to": "end"},
        "CB-10", "at level 1 the officer arrests: it never hits the player nor turns hostile",
    )  # fmt: skip
    alert_story(p, [{"step": cop}])
    return p


def death() -> Playtest:
    me = [-3.0, PLAZA_Y, 4.0]
    p = Playtest(
        "alert.death/during-alert",
        ["AL-10"],
        "On the plaza with traffic and people set to none. The player, holding a pistol, 30 "
        "armour and $180, punches a tourist with a police officer watching from 25 m (level "
        "1); two seconds later the player's health is set to 0.",
        ["--role=solo", "--variation=47", "--save-dir={save_dir}"],
        limits={"wall_s": 300, "cpu_s": 600, "step_s": 120},
    )
    alert_watch(p, 2)
    p.dev(("world.reset", {"variation": 47}))
    p.dev(("traffic.set", {"density": 0}))
    p.dev(("player.spawn", {"at": me, "heading": 0}))
    p.dev(("player.give", {"weapon": "pistol", "ammo": 24, "armour": 30}))
    p.dev(("player.give", {"weapon": "fists"}))
    cop = p.dev(person("police_officer", [me[0], PLAZA_Y, me[2] - 25.0], 180, "idle"))
    p.dev(person("tourist", [me[0], PLAZA_Y, me[2] - 1.1], 180, "idle"))
    p.step("run", 30)
    p.mark("start")
    tap(p, "attack", 120)
    p.mark("before")
    p.dev(("player.give", {"health": 0}))
    p.step("run", 900)
    p.mark("end")
    p.expect(
        "came_back", "came_back",
        {"from": "before", "to": "end", "after": "died", "poi": HOSPITAL["id"], "respawn": HOSPITAL["respawn"],
         "within_s": 10.0, "fine": 250, "health": 100, "armour": 0, "weapons": ["fists", "pistol"]},
        "AL-10",
        "within 10 s of dying the player comes back (a teleport and a respawned event) within "
        "2 m of the hospital's respawn point with 100 health, 0 armour, level 0, $250 less, "
        "keeping the pistol",
    )  # fmt: skip
    alert_story(p, [{"step": cop}])
    return p


def interior_point(parcel_id: str) -> list[float]:
    """The middle of the far half of a parcel's main room, away from its door."""
    parcel = next(pc for pc in PLAN.data["parcels"] if pc["id"] == parcel_id)
    room = parcel["interior"]["rooms"][0]
    xs = [q[0] for q in room["poly"]]
    zs = [q[1] for q in room["poly"]]
    door = parcel["interior"]["door"]["p"]
    cx, cz = (min(xs) + max(xs)) / 2.0, (min(zs) + max(zs)) / 2.0
    fx = cx + (cx - door[0]) * 0.5
    fz = cz + (cz - door[1]) * 0.5
    return [r2(fx), float(room["floor_m"]), r2(fz)]


def escape() -> Playtest:
    me = [-3.0, PLAZA_Y, 4.0]
    hides = []
    for pc in PLAN.data["parcels"]:
        if pc.get("interior") and pc["interior"].get("rooms"):
            q = interior_point(pc["id"])
            hides.append((math.hypot(q[0] - me[0], q[2] - me[2]), pc["id"], q))
    hides.sort()
    hide = next(q for d, _pid, q in hides if d > 140.0)
    seen_at = [me[0] - 60.0, PLAZA_Y, me[2] + 20.0]
    seen_spot = on_sidewalk(seen_at[0], seen_at[2])
    seen_pt = point(seen_spot)
    hide2 = next(
        q
        for d, _pid, q in [
            (math.hypot(h[2][0] - seen_pt[0], h[2][2] - seen_pt[2]), h[1], h[2])
            for h in hides
        ]
        if d > 140.0
    )
    p = Playtest(
        "alert.escape/hide",
        ["AL-11"],
        "On the plaza with traffic and people set to none and no police about. The player "
        "punches a tourist with only a shopper watching; once the shopper's call raises the "
        "level to 1, the player is put indoors far away and waits. After a world reset the same "
        "again, but before hiding the player stands 5 s on a sidewalk with a police officer "
        "watching from 20 m, then is put indoors far from there.",
        ["--role=solo", "--variation=48", "--save-dir={save_dir}"],
        limits={"wall_s": 600, "cpu_s": 1200, "step_s": 200},
    )
    alert_watch(p, 6)
    for run, (vari, see) in enumerate(((48, False), (49, True))):
        p.dev(("world.reset", {"variation": vari}))
        p.dev(("traffic.set", {"density": 0}))
        p.dev(("player.spawn", {"at": me, "heading": 0}))
        p.dev(("player.give", {"weapon": "fists"}))
        p.dev(person("tourist", [me[0], PLAZA_Y, me[2] - 1.1], 180, "idle"))
        p.dev(person("shopper", [me[0] + 8.0, PLAZA_Y, me[2] - 9.0], 220, "idle"))
        p.step("run", 30)
        if run == 0:
            p.mark("start")
        p.mark(f"crime_{run}")
        tap(p, "attack", 0)
        p.step("wait_for", {"event": "alert_changed", "max_ticks": 900})
        p.step("run", 6)
        if see:
            p.dev(("player.spawn", {"at": seen_spot, "heading": 0}))
            p.dev(
                person(
                    "police_officer",
                    [seen_pt[0], seen_pt[1], seen_pt[2] - 20.0],
                    180,
                    "idle",
                )
            )
            p.step("run", 300)
            p.dev(("player.spawn", {"at": hide2, "heading": 0}))
        else:
            p.dev(("player.spawn", {"at": hide, "heading": 0}))
        p.mark(f"hidden_{run}")
        p.step("run", 1800)
        p.mark(f"waited_{run}")
    p.mark("end")
    p.expect(
        "escape_from_crime", "escape",
        {"from": "crime_0", "to": "waited_0", "anchor": "hidden_0", "cooling_s": 20.0, "slack_s": 3.0},
        "AL-11",
        "with no unit having seen the player, the zone is centred on the crime: put indoors "
        "more than 140 m away, the player has escaped after level 1's cooling-off time, 20 s "
        "(the level drops to 0 from 20 s to 23 s after the move, not before)",
    )  # fmt: skip
    p.expect(
        "escape_from_sighting", "escape",
        {"from": "crime_1", "to": "waited_1", "anchor": "hidden_1", "cooling_s": 20.0, "slack_s": 3.0},
        "AL-11",
        "seen by an officer on the sidewalk, the zone re-centres there: put indoors more than 140 "
        "m from that spot, the level drops to 0 from 20 s to 23 s after the move, not before",
    )  # fmt: skip
    alert_story(p)
    return p


BUILDERS = (
    bad_input, commands, state_report, new_game, server_role, same_start, replay,
    same_tick, clock_rate, weather_hold, kill_after_save, damaged_slot, realtime,
    plan_compliance, paces, camera, lineup, feet, crouch, jump_climb_vault, falls,
    intersection_watch, handling_cars, handling_service, vehicle_entry, crash,
    intersection_flow, stop_junction, obstacle, speed_limits, panic_horn, replay_car_ragdoll,
    weapons_range, lock_on, armour, cover_firefight, crew_hostility,
    crime_table, phone_in, red_light, roadblock, arrest, death, escape,
)  # fmt: skip


def _scalar(v: object) -> bool:
    return not isinstance(v, (dict, list))


def render(obj: object, level: int = 0) -> str:
    """JSON with one key per line (one space per level), short lists on one line, and long
    lists of values or points ten to a line."""
    pad = " " * (level + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [
            f"{pad}{json.dumps(k)}: {render(v, level + 1)}" for k, v in obj.items()
        ]
        return "{\n" + ",\n".join(items) + "\n" + " " * level + "}"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        if all(
            _scalar(v) or (isinstance(v, list) and all(map(_scalar, v))) for v in obj
        ):
            parts = [json.dumps(v) for v in obj]
            if len(parts) <= 10:
                return "[" + ", ".join(parts) + "]"
            rows = [", ".join(parts[i : i + 10]) for i in range(0, len(parts), 10)]
            return "[\n" + ",\n".join(pad + r for r in rows) + "\n" + " " * level + "]"
        items = [pad + render(v, level + 1) for v in obj]
        return "[\n" + ",\n".join(items) + "\n" + " " * level + "]"
    return json.dumps(obj)


def main() -> int:
    """Write (or compare) every playtest file."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    differ = []
    for build in BUILDERS:
        p = build()
        parse_play(p.raw)  # the kit's own validation
        text = render(p.raw) + "\n"
        assert json.loads(text) == p.raw
        path = a.out / (p.name.replace("/", ".") + ".json")
        if a.check:
            if not path.is_file() or path.read_text() != text:
                differ.append(path.name)
        else:
            path.write_text(text)
    if a.check:
        print("\n".join(differ) or "playtests up to date")
        return 1 if differ else 0
    print(f"wrote {len(BUILDERS)} playtests to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
