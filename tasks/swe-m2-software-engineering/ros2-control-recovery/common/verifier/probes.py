"""Independent closed-loop probes for controller and command-mode recovery."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any, Callable

Record = dict[str, Any]
Run = Callable[..., Record]


class Mismatch(Exception):
    """Observed controller behavior violated the published contract."""


def expect(test: bool, message: str) -> None:
    """Fail the current isolated behavioral probe with a precise reason."""
    if not test:
        raise Mismatch(message)


def controller(requires: list[str] | None = None, device: str | None = None,
               mode: str | None = None, interfaces: tuple[str, ...] = ()) -> Record:
    """Build one controller's prerequisite graph and hardware interface claims."""
    claims = {} if device is None else {device: {"mode": mode, "interfaces": list(interfaces)}}
    return {"requires": [] if requires is None else requires, "claims": claims}


def snapshot(modes: dict[str, tuple[int, str, str]], active: list[str]) -> Record:
    """Describe independently observed hardware mode, readiness and running controllers."""
    return {"devices": {
        name: {"generation": generation, "mode": mode, "state": state}
        for name, (generation, mode, state) in modes.items()
    }, "active": active}


def closure(controllers: dict[str, Record], roots: list[str]) -> set[str]:
    """Walk the fixture's dependency graph without assuming an ordering."""
    found: set[str] = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name not in found:
            found.add(name)
            pending.extend(controllers[name]["requires"])
    return found


def hardware_claims(spec: Record, chosen: set[str],
                    unavailable: set[tuple[str, int, str]]) -> dict[str, str] | None:
    """Return conflict-free device modes for a chosen controller set."""
    interfaces: set[tuple[str, str]] = set()
    desired: dict[str, str] = {}
    for name in chosen:
        for device, claim in spec["controllers"][name]["claims"].items():
            observed = spec["snapshot"]["devices"][device]
            mode = claim["mode"]
            if (observed["state"] != "ready" or
                    (device, observed["generation"], mode) in unavailable or
                    (device in desired and desired[device] != mode)):
                return None
            qualified_interfaces = {(device, item) for item in claim["interfaces"]}
            if interfaces & qualified_interfaces:
                return None
            interfaces |= qualified_interfaces
            desired[device] = mode
    return desired


def optimum(spec: Record, unavailable: set[tuple[str, int, str]]) -> tuple[Record, set[str], dict[str, str]]:
    """Derive the optimal requested groups by direct exhaustive enumeration."""
    groups = spec["groups"]
    controllers = spec["controllers"]
    choices = [range(len(group["options"]) + 1) for group in groups]
    best_rank: tuple[int, tuple[int, ...]] | None = None
    best = ({}, set(), {})
    for indexes in product(*choices):
        selection: Record = {}
        required: list[str] = []
        for group, index in zip(groups, indexes, strict=True):
            options = group["options"]
            selection[group["id"]] = None if index == len(options) else index
            if index < len(options):
                required.extend(options[index])
        target = closure(controllers, required)
        claimed = hardware_claims(spec, target, unavailable)
        if claimed is None:
            continue
        rank = (sum(index is None for index in selection.values()), indexes)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best = selection, target, claimed
    return best


def usable_active(spec: Record) -> set[str]:
    """Compute closed readback validity using pairwise exclusive claims."""
    active = set(spec["snapshot"]["active"])
    controllers = spec["controllers"]
    observed = spec["snapshot"]["devices"]
    unusable = {
        name for name in active
        if not set(controllers[name]["requires"]).issubset(active)
        or any(observed[device]["state"] != "ready" or observed[device]["mode"] != claim["mode"]
               for device, claim in controllers[name]["claims"].items())
    }
    for name in active:
        claims = controllers[name]["claims"]
        for other in active - {name}:
            for device, peer in controllers[other]["claims"].items():
                own = claims.get(device)
                if own and (own["mode"] != peer["mode"]
                            or set(own["interfaces"]) & set(peer["interfaces"])):
                    unusable.update((name, other))
    return {name for name in active if not closure(controllers, [name]) & unusable}


def apply_command(spec: Record, decision: Record, unavailable: set[tuple[str, int, str]]) -> bool:
    """Validate and apply any safe primitive on the independent simulation snapshot."""
    wanted, goal, effective_modes = optimum(spec, unavailable)
    expect(decision.get("selected") == wanted,
           f"selected options {decision.get('selected')!r}; independent optimum is {wanted!r}")
    command = decision.get("command")
    snap = spec["snapshot"]
    active = set(snap["active"])
    controllers = spec["controllers"]
    if command is None:
        expect(active == goal and all(snap["devices"][device]["mode"] == mode
                                      for device, mode in effective_modes.items()),
               "reported completion before the optimum was achieved")
        return False
    expect(isinstance(command, dict), "command must be an object or null")
    kind = command.get("kind")
    required_stops = (active - goal) | (active - usable_active(spec))
    if kind == "stop":
        name = command.get("controller")
        expect(name in required_stops, "stopped an active, usable target or an already stopped controller")
        expect(not any(name in closure(controllers, [other]) for other in active - {name}),
               "stopped a controller while a dependent was still active")
        active.remove(name)
    elif kind == "start":
        expect(not required_stops, "started before completing the required stops")
        name = command.get("controller")
        expect(name in goal - active, "started an already active controller or one outside the optimum")
        expect(set(controllers[name]["requires"]).issubset(active), "started before dependencies were active")
        modes = hardware_claims(spec, active | {name}, unavailable)
        expect(modes is not None and all(snap["devices"][device]["mode"] == mode
                                         for device, mode in modes.items()),
               "started a controller before observed hardware readiness and mode")
        active.add(name)
    elif kind == "mode":
        expect(not required_stops, "requested a mode change before completing the required stops")
        device, mode = command.get("device"), command.get("mode")
        expect(device in effective_modes and effective_modes[device] == mode,
               "mode command did not serve the selected options")
        observed = snap["devices"][device]
        expect(observed["state"] == "ready" and observed["mode"] != mode
               and command.get("generation") == observed["generation"],
               "mode change used an unavailable device, stale generation or already active mode")
        expect(not any(device in controllers[name]["claims"] for name in active),
               "device mode changed while its command interface was active")
        observed["mode"] = mode
    else:
        raise Mismatch(f"unexpected command kind {kind!r}")
    snap["active"] = sorted(active)
    return True


def inspection_fixture() -> Record:
    """Construct active claims with independently identifiable failure causes."""
    return {
        "hardware": {
            "carriage": {"modes": {"position": ["left", "right"]}},
            "elevate": {"modes": {"velocity": ["motor"]}},
            "tilt": {"modes": {"velocity": ["target"], "position": ["target"]}},
            "bracket": {"modes": {"hold": ["clamp", "indicator"]}},
        },
        "controllers": {
            "carriage-a": controller(device="carriage", mode="position", interfaces=("left",)),
            "carriage-b": controller(device="carriage", mode="position", interfaces=("left",)),
            "indirect-carriage": controller(["carriage-a"]),
            "carriage-right": controller(device="carriage", mode="position", interfaces=("right",)),
            "elevator": controller(device="elevate", mode="velocity", interfaces=("motor",)),
            "nested-elevator": controller(["elevator"]),
            "top": controller(["nested-elevator"]),
            "tilt": controller(device="tilt", mode="velocity", interfaces=("target",)),
            "parent-absent": controller(["not-started"]),
            "not-started": controller(),
            "grip": controller(device="bracket", mode="hold", interfaces=("clamp",)),
            "grip-indicator": controller(device="bracket", mode="hold", interfaces=("indicator",)),
            "grip-client": controller(["grip", "grip-indicator"]),
        },
        "groups": [],
        "snapshot": snapshot({
            "carriage": (4, "position", "ready"), "elevate": (12, "velocity", "fault"),
            "tilt": (8, "position", "ready"), "bracket": (2, "hold", "ready"),
        }, ["top", "nested-elevator", "carriage-a", "carriage-b", "carriage-right",
            "indirect-carriage", "elevator", "tilt", "parent-absent",
            "grip", "grip-indicator", "grip-client"]),
    }


def inspect_case(run: Run) -> None:
    """Check fault propagation, mode mismatches and per-interface exclusivity."""
    report = run("inspect", inspection_fixture())
    usable = ["carriage-right", "grip", "grip-client", "grip-indicator"]
    deactivate = sorted(["carriage-a", "carriage-b", "indirect-carriage", "elevator",
                         "nested-elevator", "top", "tilt", "parent-absent"])
    expect(report.get("usable") == usable and report.get("deactivate") == deactivate,
           "inspection missed a conflict, missing dependency, fault, mode mismatch or safe peer")


def planning_fixture() -> Record:
    """Build competing optional routes and a protected independent controller."""
    return {
        "hardware": {
            "gantry": {"modes": {"velocity": ["left", "right"], "position": ["left", "right"]}},
            "tool": {"modes": {"hold": ["clamp"]}},
            "lift": {"modes": {"hold": ["lock"]}},
        },
        "controllers": {
            "gantry-vel": controller(device="gantry", mode="velocity", interfaces=("left",)),
            "gantry-vel-root": controller(["gantry-vel"]),
            "gantry-pos": controller(device="gantry", mode="position", interfaces=("left",)),
            "gantry-pos-root": controller(["gantry-pos"]),
            "position-monitor": controller(device="gantry", mode="position", interfaces=("right",)),
            "gripper": controller(device="tool", mode="hold", interfaces=("clamp",)),
            "gripper-root": controller(["gripper"]),
            "lift": controller(device="lift", mode="hold", interfaces=("lock",)),
        },
        "groups": [
            {"id": "manipulator", "options": [["gantry-vel-root"], ["gantry-pos-root"]]},
            {"id": "position-service", "options": [["position-monitor"]]},
            {"id": "hold-load", "options": [["gripper-root"]]},
            {"id": "elevation-lock", "options": [["lift"]]},
        ],
        "snapshot": snapshot({"gantry": (7, "velocity", "ready"), "tool": (29, "hold", "ready"),
                              "lift": (2, "hold", "fault")},
                             ["gantry-vel", "gantry-vel-root", "gripper", "gripper-root"]),
    }


def quality_case(run: Run) -> None:
    """Force a non-greedy assignment, then replay every actual transition."""
    spec = planning_fixture()
    for _ in range(16):
        response = run("plan", deepcopy(spec))
        moved = apply_command(spec, response, set())
        if not moved:
            return
    raise Mismatch("repeated planning calls never reached the optimal active set")


def priority_case(run: Run) -> None:
    """Verify that equal-size group selections honor the documented option order."""
    spec = planning_fixture()
    spec["groups"][1] = {"id": "position-service", "options": [["position-monitor"], ["gantry-vel-root"]]}
    response = run("plan", spec)
    expect(response.get("selected") == {
        "manipulator": 0, "position-service": 1, "hold-load": 0, "elevation-lock": None,
    } and response.get("command") is None,
           "option order or shared dependency handling was incorrect")


def recovery_fixture() -> Record:
    """Put the less preferred but functioning velocity chain online."""
    spec = planning_fixture()
    spec["groups"] = [spec["groups"][0], spec["groups"][2]]
    spec["groups"][0]["options"].reverse()
    return spec


def request(task: Record, run_id: str, sequence: int, previous: Record | None = None) -> Record:
    """Create one immutable recovery envelope from the observed hardware state."""
    return deepcopy(task) | {"run_id": run_id, "sequence": sequence, "previous": previous}


def call_and_validate(run: Run, state: Path, req: Record,
                      seen: set[str]) -> Record:
    """Check echoes and identifiers before applying a recovery decision."""
    result = run("recover", req, state=state)
    expect(result.get("run_id") == req["run_id"] and result.get("sequence") == req["sequence"],
           "recovery reply did not identify its request")
    command = result.get("command")
    authority = result.get("command_id")
    if command is None:
        expect(result.get("status") == "settled" and authority is None,
               "no-command reply was not a settled decision")
    else:
        expect(result.get("status") == "issued" and isinstance(authority, str)
               and authority and authority not in seen, "issued command identity was invalid or reused")
        seen.add(authority)
    return result


def acknowledge(reply: Record, outcome: str) -> Record:
    """Create a receipt for the command identified by the previous response."""
    return {"id": reply["command_id"], "outcome": outcome}


def rejection(result: Record) -> None:
    """Require an explicit null-command rejection without hidden progress."""
    expect(result.get("status") == "rejected" and result.get("selected") == {}
           and result.get("command") is None and result.get("command_id") is None,
           "stale, altered or invalid request was accepted")


def mission_journal(run: Run, name: str) -> Path:
    """Give the unprivileged controller one writable directory for a journal."""
    directory = run.scratch / name
    directory.mkdir()
    directory.chmod(0o777)
    return directory / "journal.json"


def fallback_case(run: Run) -> None:
    """Apply a failed same-generation mode switch and later replace the device."""
    state = mission_journal(run, "mode-fallback")
    spec = recovery_fixture()
    name = "recover-gantry-and-tool"
    unavailable: set[tuple[str, int, str]] = set()
    seen: set[str] = set()
    current = None
    failed_epoch = False
    renewed_epoch = False
    rejected_readback = False
    tried_obsolete = False
    for sequence in range(1, 34):
        req = request(spec, name, sequence, current)
        result = call_and_validate(run, state, req, seen)
        command = result.get("command")
        old_snapshot = deepcopy(spec["snapshot"])
        progressed = apply_command(spec, result, unavailable)
        if not progressed:
            if not renewed_epoch:
                expect(failed_epoch and result["selected"]["manipulator"] == 1,
                       "did not reselect the safe velocity option after a rejected mode")
                spec["snapshot"]["devices"]["gantry"]["generation"] += 1
                renewed_epoch = True
                current = None
                continue
            expect(tried_obsolete and rejected_readback and result["selected"]["manipulator"] == 0,
                   "new generation failed to recover the preferred mode after reconciliation")
            return
        if command["kind"] == "mode" and not failed_epoch:
            spec["snapshot"] = old_snapshot
            unavailable.add((command["device"], command["generation"], command["mode"]))
            current = acknowledge(result, "failed")
            failed_epoch = True
        elif command["kind"] == "mode" and renewed_epoch and not tried_obsolete:
            spec["snapshot"] = old_snapshot
            spec["snapshot"]["devices"]["gantry"]["generation"] += 1
            current = acknowledge(result, "obsolete")
            tried_obsolete = True
        else:
            current = acknowledge(result, "applied")
            if command["kind"] == "mode" and tried_obsolete and not rejected_readback:
                stale = request(spec, name, sequence + 1, current)
                stale["snapshot"] = old_snapshot
                rejection(run("recover", stale, state=state))
                rejected_readback = True
    raise Mismatch("hardware recovery did not settle after fallback, reinsertion and valid readback")


def replay_case(run: Run) -> None:
    """Check identical retransmission, altered/stale receipts, and mission isolation."""
    state = mission_journal(run, "replay-shared")
    spec = recovery_fixture()
    seen: set[str] = set()
    first = request(spec, "alpha", 1)
    expect(run("recover", first, state=state, lost_reply=True) is True,
           "could not observe a failed reply publication")
    tampered = deepcopy(first)
    tampered["snapshot"]["devices"]["tool"]["generation"] += 1
    rejection(run("recover", tampered, state=state))
    reply = call_and_validate(run, state, first, seen)
    expect(reply["command"] is not None, "fixture requires an issued first command")
    expect(run("recover", deepcopy(first), state=state) == reply, "restart did not preserve identical reply")
    alternate = request(spec, "beta", 1)
    call_and_validate(run, state, alternate, set())
    expect(run("recover", deepcopy(first), state=state) == reply, "new mission overwrote prior mission state")
    expect(apply_command(spec, reply, set()), "first command unexpectedly settled")
    second = request(spec, "alpha", 2, acknowledge(reply, "applied"))
    skipped = second | {"sequence": 3}
    rejection(run("recover", skipped, state=state))
    wrong_id = second | {"previous": {"id": "unknown-command", "outcome": "applied"}}
    rejection(run("recover", wrong_id, state=state))
    result = call_and_validate(run, state, second, seen)
    apply_command(spec, result, set())
    rejection(run("recover", first, state=state))
    expect(run("recover", second, state=state) == result, "rejected requests advanced or rewrote replay state")
    spec["groups"] = [spec["groups"][1]]
    third = request(spec, "alpha", 3, acknowledge(result, "applied"))
    bad = deepcopy(third)
    bad["snapshot"]["active"].append("unknown-controller")
    before = state.read_bytes()
    expect(run("recover", bad, state=state, invalid=True) is True and state.read_bytes() == before,
           "malformed recovery request changed the journal or reply")
    updated = call_and_validate(run, state, third, seen)
    expect(not apply_command(spec, updated, set()), "updated service groups failed to preserve active tool")


def concurrent_case(run: Run) -> None:
    """Require serializable decisions for both disjoint and conflicting runs."""
    state = mission_journal(run, "journal-concurrent")
    assignment = recovery_fixture()
    inputs = [request(assignment, f"cell-controller-{i}", 1) for i in range(6)]
    left = request(assignment, "same-controller", 1)
    right = deepcopy(left)
    right["groups"] = [right["groups"][1]]
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = [pool.submit(run, "recover", packet, state=state) for packet in [*inputs, left, right]]
        replies = [future.result() for future in pending]
    for packet, response in zip(inputs, replies[:6], strict=True):
        expect(isinstance(response, dict) and response.get("status") == "issued",
               "a disjoint concurrent request failed to issue")
        expect(run("recover", packet, state=state) == response, "a concurrent update lost another run's decision")
    contested = replies[6:]
    winners = [i for i, reply in enumerate(contested)
               if isinstance(reply, dict) and reply.get("status") in ("issued", "settled")]
    expect(len(winners) == 1, "conflicting requests at the same sequence did not serialize")
    winner = winners[0]
    rejection(contested[1 - winner])
    expect(run("recover", [left, right][winner], state=state) == contested[winner],
           "concurrent winner was not durably replayable")


def checks(run: Run, level: int) -> dict[str, bool]:
    """Run the independent checks enabled at a cumulative checkpoint."""
    cases = [("faults_propagate_to_active_dependents", inspect_case)]
    if level >= 2:
        cases += [
            ("joint_group_optimum_and_safe_transition_order", quality_case),
            ("equal_quality_uses_declared_preferences", priority_case),
        ]
    if level >= 3:
        cases += [
            ("failed_mode_fallback_and_generation_recovery", fallback_case),
            ("durable_replay_rejects_invalid_requests", replay_case),
            ("serializable_concurrent_recovery", concurrent_case),
        ]
    results = {}
    for name, check in cases:
        try:
            check(run)
        except (Mismatch, AttributeError, KeyError, TypeError, ValueError) as error:
            print(f"{name}: {error}")
            results[name] = False
        else:
            results[name] = True
    return results
