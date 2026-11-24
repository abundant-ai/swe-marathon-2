"""Private exercises for mixed routing, obstruction, and crash recovery."""

import hashlib
import json

from fleet_world import Transport, World, require


def make_site(key, *, bypass=True, escape=False, eligibility=False):
    def opaque(name):
        return hashlib.sha256(f"{key}/{name}".encode()).hexdigest()[:9]

    names = {name: opaque(name) for name in
             ("a", "throat", "exit", "goal", "bypass", "l0", "l1", "l2", "l3",
              "f0", "f1", "drive", "loop", "free", "shared", "outlet")}
    name = names.__getitem__
    nodes = {name(node): [] for node in ("a", "throat", "exit", "goal",
                                          "l0", "l1", "l2", "l3", "f0", "f1")}
    nodes[name("throat")] = [name("shared")]
    nodes[name("l1")] = [name("shared")]
    if bypass:
        nodes[name("bypass")] = []
    if escape:
        nodes[name("a")] = [name("outlet")]

    def edge(source, target, ticks, *resources):
        return {"from": name(source), "to": name(target), "ticks": ticks,
                "resources": [name(resource) for resource in resources]}

    lanes = [
        edge("a", "throat", 3, "shared"), edge("throat", "a", 3, "shared"),
        edge("throat", "exit", 2, "shared"), edge("exit", "throat", 2, "shared"),
        edge("exit", "goal", 1), edge("goal", "exit", 1),
        edge("l0", "l1", 2, "shared"), edge("l1", "l2", 2, "shared"),
        edge("l2", "l3", 1), edge("l3", "l0", 1), edge("l0", "l3", 1),
        edge("f0", "f1", 3), edge("f1", "f0", 3),
    ]
    if bypass:
        lanes.extend([edge("a", "bypass", 4), edge("bypass", "exit", 4),
                      edge("exit", "bypass", 4), edge("bypass", "a", 4)])
    robots = {
        name("drive"): {"start": name("a"), "mode": "route"},
        name("loop"): {"start": name("l0"), "mode": "loop",
                       "loop": [name(node) for node in ("l0", "l1", "l2", "l3")]},
        name("free"): {"start": name("f0"), "mode": "route"},
    }
    if eligibility:
        # Present the incapable loop before the route-capable fleet.
        robots = dict(reversed(list(robots.items())))
    return {"nodes": nodes, "lanes": lanes, "robots": robots}, name


def exercise(app, root, scenario, **options):
    root.mkdir(mode=0o755)
    state = root / "state"
    state.mkdir(mode=0o777)
    state.chmod(0o777)
    site, name = make_site(scenario.__name__, **options)
    site_file = root / "site.json"
    site_file.write_text(json.dumps(site))
    transport = Transport(app, site_file, state)
    try:
        return scenario(World(transport, site), name)
    finally:
        transport.close()


def mixed_deliveries(world, n):
    world.job("dispatch", n("a"), n("goal"), [n("drive")])
    world.job("patrol", n("l0"), n("l3"), [n("loop")])
    world.job("annex", n("f0"), n("f1"), [n("free")])
    world.run_until(0, 23)
    jobs = ("dispatch", "patrol", "annex")
    require(all(world.delivered(job) for job in jobs), "three simultaneous jobs did not all deliver")
    require(sum(tick == 0 and c["kind"] == "pickup" for tick, c in world.history) == 3,
            "three compatible pickups were available on the first tick")
    return {job: world.jobs[job]["dropped_at"] for job in jobs}


def routes_and_egress(world, n):
    world.closure(n("shared"), True)
    world.closure(n("outlet"), True)
    world.job("diversion", n("a"), n("goal"), [n("drive")])
    world.job("wait", n("l0"), n("l3"), [n("loop")])
    world.job("outside", n("f0"), n("f1"), [n("free")])
    world.run_until(0, 11)
    require(world.delivered("diversion"), "the route robot did not complete the open detour")
    require(world.delivered("outside"), "the closure stopped unrelated work")
    require(not world.delivered("wait"), "the loop ran before its corridor reopened")
    require(any(c.get("to") == n("bypass") for _, c in world.history),
            "the route robot did not use the bypass")
    world.advance(12)
    world.closure(n("shared"), False)
    world.apply(world.send("tick"))
    world.run_until(13, 24)
    require(world.delivered("wait"), "the loop did not resume on reopening")
    return {job: world.jobs[job]["dropped_at"] for job in ("diversion", "outside", "wait")}


def priority_and_order(world, n):
    for job, priority in (("routine", 0), ("urgent-first", 8), ("urgent-second", 8)):
        world.job(job, n("a"), n("exit"), [n("drive")], priority=priority)
    world.run_until(0, 38)
    require(all(world.delivered(job) for job in world.jobs), "prioritized jobs did not all deliver")
    order = [c["job"] for _, c in world.history if c["kind"] == "pickup"]
    require(order == ["urgent-first", "urgent-second", "routine"],
            f"pickup priority or equal-priority order was wrong: {order}")
    return {"pickup_order": order}


def settlement_after_restart(world, n):
    drive = n("drive")
    world.job("abort", n("exit"), n("goal"), [drive])
    world.job("suspended", n("l0"), n("l3"), [n("loop")])
    world.job("unaffected", n("f0"), n("f1"), [n("free")])
    first_tick = world.event("tick")
    first_reply = world.transport.exchange(first_tick)
    launch = next((c for c in first_reply["commands"]
                   if isinstance(c, dict) and c.get("robot") == drive and c.get("kind") == "move"), None)
    require(launch is not None and launch.get("to") == n("throat"),
            "missing original drive command into the shared passage")
    world.transport.restart()
    retry_reply = world.transport.exchange(first_tick)
    require(retry_reply == first_reply, "retried tick returned a different response after restart")

    def abandon(command, due, target):
        if command == launch:
            return 14, n("a")
        return None

    world.fault = abandon
    world.apply(retry_reply)
    world.advance(1)
    world.cancel("abort")
    world.report(drive, False, None)
    world.report(drive, True, n("a"), launch["command"], stale=True)
    world.apply(world.send("tick"))
    world.tick(2)
    world.advance(3)
    world.report(drive, True, n("a"), "unrelated-move-id", observation_only=True)
    world.apply(world.send("tick"))
    world.run_until(4, 6)
    world.transport.restart()
    world.advance(7)
    world.report(drive, True, None)
    world.apply(world.send("tick"))
    world.run_until(8, 13)
    require(world.delivered("unaffected"), "unaffected fleet failed to deliver during uncertainty")
    require(not world.delivered("suspended"), "blocked fleet recorded an impossible early delivery")
    world.run_until(14, 28)
    require(world.delivered("suspended"), "forward progress did not resume after confirmed return")
    require(sum(c["job"] == "abort" for _, c in world.history) == 1,
            "the canceled task was commanded again after its move returned")
    last_reply = world.transport.exchange(first_tick)
    require(last_reply == first_reply, "late retry lost the original tick response")
    world.apply(last_reply, replay=True)
    return {"confirmed_return_at": 14, "unaffected_drop_at": world.jobs["unaffected"]["dropped_at"],
            "suspended_drop_at": world.jobs["suspended"]["dropped_at"]}


def interrupted_loaded_job(world, n):
    drive = n("drive")
    world.job("loaded", n("a"), n("goal"), [drive])
    world.job("annex", n("f0"), n("f1"), [n("free")])
    world.tick(0)
    world.cancel("loaded")
    world.tick(1)
    world.cancel("loaded")
    pending = world.occupancy.get(drive)
    require(pending is not None and pending["command"]["kind"] == "move",
            "cancel while pickup was pending or after pickup aborted parcel delivery")
    world.report(drive, False, None)
    world.transport.restart()
    world.run_until(2, 20)
    require(world.delivered("loaded"), "assigned parcel did not deliver after restart")
    require(world.delivered("annex"), "restart caused an unrelated job to be lost")
    return {job: world.jobs[job]["dropped_at"] for job in ("loaded", "annex")}


def cross_fleet_eligibility(world, n):
    # Listing an alternate fleet as eligible does not make the fixed loop
    # capable of reaching stations off that loop.
    world.job("remote", n("exit"), n("goal"), [n("free"), n("loop"), n("drive")])
    world.job("circuit", n("l0"), n("l2"), [n("loop")])
    world.job("annex", n("f0"), n("f1"), [n("free")])
    world.run_until(0, 24)
    require(all(world.delivered(job) for job in world.jobs),
            "graph capabilities and mixed eligibility did not yield complete deliveries")
    require(world.jobs["remote"]["owner"] == n("drive"),
            "the cross-listed job was dispatched to a fleet without a route")
    return {job: world.jobs[job]["dropped_at"] for job in world.jobs}


def unresolved_station_after_restart(world, n):
    drive, loop = n("drive"), n("loop")
    world.job("park", n("a"), n("throat"), [drive])
    world.run_until(0, 6)
    require(world.delivered("park"), "drive robot never reached the shared-resource berth")
    world.advance(7)
    world.report(drive, False, None)
    world.job("exit_after_restore", n("throat"), n("goal"), [drive])
    world.job("blocked_at_gate", n("l0"), n("l3"), [loop])
    world.job("continue_elsewhere", n("f0"), n("f1"), [n("free")])
    world.transport.restart()
    world.apply(world.send("tick"))
    world.run_until(8, 14)
    require(world.delivered("continue_elsewhere"), "offline berth interrupted unrelated work")
    require(not world.delivered("blocked_at_gate"), "offline berth was treated as vacant")
    world.advance(15)
    world.report(drive, True, n("throat"))
    world.apply(world.send("tick"))
    world.run_until(16, 31)
    require(world.delivered("exit_after_restore") and world.delivered("blocked_at_gate"),
            "robot at confirmed berth or the waiting loop failed to resume")
    return {job: world.jobs[job]["dropped_at"] for job in world.jobs}


CHECKS = (
    ("mixed_deliveries", 1, mixed_deliveries, {}),
    ("cross_fleet_eligibility", 1, cross_fleet_eligibility, {"eligibility": True}),
    ("closures_reroute_egress_and_reopen", 2, routes_and_egress, {"escape": True}),
    ("priority_and_fifo", 2, priority_and_order, {}),
    ("replayed_grant_and_confirmed_return", 3, settlement_after_restart, {"bypass": False}),
    ("picked_parcel_survives_restart", 3, interrupted_loaded_job, {}),
    ("uncertain_station_keeps_resource", 3, unresolved_station_after_restart, {}),
)
