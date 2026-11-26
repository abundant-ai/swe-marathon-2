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
import json
import math
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))

from qakit.plan import Plan
from qakit.play import parse_play

sys.path.insert(0, str(TASK / "scripts"))
from plan_probes import Probes

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


BUILDERS = (
    bad_input, commands, state_report, new_game, server_role, same_start, replay,
    same_tick, clock_rate, weather_hold, kill_after_save, damaged_slot, realtime,
    plan_compliance, paces, camera, lineup, feet, crouch, jump_climb_vault, falls,
    intersection_watch, handling_cars, handling_service, vehicle_entry, crash,
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
