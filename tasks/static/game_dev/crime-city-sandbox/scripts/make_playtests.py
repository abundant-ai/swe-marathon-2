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
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))

from qakit.plan import Plan
from qakit.play import parse_play

OUT = TASK / "common" / "kit" / "playtests"
PLAN = Plan.load(TASK / "common" / "design" / "plan" / "downtown.json")
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
    lane = {"lane": "e_00_01:ab0", "s": 20.0}
    walk = {"sidewalk": "sw_11", "s": 15.0}
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


BUILDERS = (
    bad_input, commands, state_report, new_game, server_role, same_start, replay,
    same_tick, clock_rate, weather_hold, kill_after_save, damaged_slot, realtime,
)  # fmt: skip


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
        text = json.dumps(p.raw, indent=1) + "\n"
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
