"""Independent observation, timing, restart and qualification missions."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np

from fixtures import Physical, Record, TruthPolicy, export, manifest, physical, standard_frame
from transport import Stream, batch, dump, require, writable


def equal_vector(actual: object, expected: list[float], field: str) -> None:
    """Require a finite vector with the independently derived numerical result."""
    require(type(actual) is list and len(actual) == len(expected)
            and all(type(x) in (int, float) for x in actual), f"bad shape/type for {field}")
    require(bool(np.allclose(actual, expected, rtol=3e-9, atol=3e-9)),
            f"incorrect {field} channel values")


def verify(actual: Record, expected: Record) -> None:
    """Match physical output and update diagnostics without prescribing the code path."""
    require(actual.get("status") == expected["status"],
            f"expected {expected['status']}, got {actual.get('status')}")
    for field in ("control", "observation", "action", "target"):
        target = expected[field]
        if target is None:
            require(field in actual and actual[field] is None, f"{field} should be explicitly null")
        else:
            equal_vector(actual.get(field), target, field)


def observation_case(app: Path, root: Path, *, layout: int, count: int, seed: int) -> Record:
    """Compare nontrivial exported channels against direct physical truth."""
    outputs = writable(root / "out")
    spec = manifest(seed, layout, count=count)
    truth = physical(spec, seed * 0.23, shift=0.18 if layout % 2 else -0.30)
    signal = [0.12 * i * (-1)**i - 0.14 for i in range(count)]
    packet = export(spec, truth, 7, sign_flip=bool(layout % 2)) | {"last_action": signal}
    spec_file = dump(root / "manifest.json", spec)
    input_file = dump(root / "sample.json", packet)
    command = ["observe", "--spec", str(spec_file), "--input", str(input_file)]
    observed = batch(app, command, outputs / "report.json")
    expected = standard_frame(spec, truth, signal)
    equal_vector(observed.get("observation"), expected, "first normalized frame")
    return {"channels": len(expected), "joints": count, "quaternion": spec["model"]["quaternion"]}


def malformed_case(app: Path, root: Path) -> Record:
    """Exercise malformed joint references, repeated names and invalid orientation."""
    outputs = writable(root / "out")
    spec = manifest(21, 1)
    samples = export(spec, physical(spec, 5), 0) | {"last_action": [0.0] * len(spec["action_order"])}
    invalid = []
    zero = samples | {"orientation": [0, 0, 0, 0]}
    invalid.append((spec, zero))
    duplicate = deepcopy(spec)
    duplicate["model"]["joint_order"][0] = duplicate["model"]["joint_order"][1]
    invalid.append((duplicate, samples))
    missing = deepcopy(spec)
    missing["joints"][missing["observation_order"][0]]["sensor"] = "unknown-joint-slot"
    invalid.append((missing, samples))
    bad_width = samples | {"last_action": [0]}
    invalid.append((spec, bad_width))
    for index, (bad_spec, bad_sample) in enumerate(invalid):
        args = ["observe", "--spec", str(dump(root / f"spec-{index}.json", bad_spec)),
                "--input", str(dump(root / f"sample-{index}.json", bad_sample))]
        batch(app, args, outputs / "existing.json", invalid=True)
    return {"invalid_transactions": len(invalid)}


def cadence_case(app: Path, root: Path, *, skip: bool) -> Record:
    """Use multi-layer actor and verify skipped ticks never fill history."""
    spec = manifest(174 if skip else 62, 3 if skip else 2, count=8 if skip else 6,
                    history=4 if skip else 3, period=3 if skip else 4)
    truth_policy = TruthPolicy(spec)
    ticks = [1, 2, 3, 4, 5, 8, 9, 12, 14, 15, 18] if skip else list(range(21))
    ticks = [t for t in ticks if t % 3 != 0 or t != 12] if skip else ticks
    clipped = 0
    updates = 0
    with Stream(app, root / "run", spec) as actor:
        for tick in ticks:
            state = physical(spec, tick + 0.8, shift=0.12 * (-1)**tick)
            if tick % spec["policy_period_ticks"] == 0:
                expected = truth_policy.evaluate(state)
                updates += 1
                clipped += sum(abs(action) >= clip - 1e-12 for action, clip in
                               zip(expected["action"], spec["policy"]["action_clip"], strict=True))
            else:
                expected = truth_policy.quiet("held")
            verify(actor.push(export(spec, state, tick, sign_flip=tick % 2 == 0)), expected)
    require(updates >= 4 and clipped > 0, "reference exercise did not saturate a frozen actor action")
    return {"policy_updates": updates, "samples": len(ticks), "clipped_components": int(clipped)}


def watchdog_case(app: Path, root: Path) -> Record:
    """Check both immediate watchdog causes and phase-aligned explicit rearming."""
    spec = manifest(69, 4, count=5, history=3, period=4)
    policy = TruthPolicy(spec)
    with Stream(app, root / "run", spec) as actor:
        for tick in range(5):
            motion = physical(spec, tick)
            desired = policy.evaluate(motion) if tick in (0, 4) else policy.quiet("held")
            verify(actor.push(export(spec, motion, tick)), desired)
        packet = export(spec, physical(spec, 12), 12)
        verify(actor.push(packet), policy.quiet("latched"))
        actor.restart()
        verify(actor.push(packet), policy.quiet("latched"))
        verify(actor.push(export(spec, physical(spec, 13), 13)), policy.quiet("latched"))
        verify(actor.push({"kind": "arm", "tick": 17}), policy.quiet("armed"))
        policy = TruthPolicy(spec)
        for tick in range(18, 23):
            movement = physical(spec, tick)
            desired = policy.evaluate(movement) if tick == 21 else policy.quiet("held")
            verify(actor.push(export(spec, movement, tick)), desired)
        verify(actor.push({"kind": "step", "healthy": False, "tick": 23}), policy.quiet("latched"))
        verify(actor.push(export(spec, physical(spec, 24), 24)), policy.quiet("latched"))
    return {"watchdog_gap_latched": True, "unhealthy_latched": True, "rephased_first_update_tick": 21}


def replay_case(app: Path, root: Path) -> Record:
    """Lose outputs at updates/holds and compare all future history with the uninterrupted actor."""
    spec = manifest(51, 3, count=7, history=5, period=3)
    policy = TruthPolicy(spec)
    previous = None
    with Stream(app, root / "run", spec) as actor, Stream(app, root / "uninterrupted", spec) as continuous:
        for tick in range(27):
            motion = physical(spec, 0.7 * tick, shift=-0.14 if tick >= 16 else 0.0)
            packet = export(spec, motion, tick)
            expected = policy.evaluate(motion) if tick % 3 == 0 else policy.quiet("held")
            reply = actor.push(packet)
            verify(reply, expected)
            verify(continuous.push(packet), expected)
            if tick in (6, 8, 15):
                actor.restart()
                altered = deepcopy(packet)
                altered["command"][1] += 0.7
                verify(actor.push(altered), policy.quiet("rejected"))
                verify(actor.push(previous), policy.quiet("rejected"))
                require(actor.push(packet) == reply, "exact tick retry did not replay previous output")
            previous = packet
    return {"restart_ticks": [6, 8, 15], "policy_updates": 9, "same_as_uninterrupted": True}


def lines(path: Path, packets: list[Record]) -> Path:
    """Write a full backend trace in the public input syntax."""
    path.write_text("".join(json.dumps(packet, allow_nan=False) + "\n" for packet in packets))
    return path


def compare_case(app: Path, root: Path, mode: str) -> Record:
    """Compare differently sampled exports and demand a precise first witness."""
    a = manifest(85, 0, count=6, dt=5_000_000, period=4)
    b = manifest(85, 5, count=6, dt=10_000_000, period=2)
    left = [export(a, physical(a, tick / 2), tick) for tick in range(25)]
    right = [export(b, physical(b, tick), tick, sign_flip=bool(tick % 2)) for tick in range(13)]
    first = None
    compared = 7
    if mode == "observation":
        right[6] = deepcopy(right[6])
        right[6]["command"][2] += 0.29
        policy = TruthPolicy(b)
        for tick in (0, 2, 4):
            policy.evaluate(physical(b, tick))
        original = deepcopy(policy)
        physical_a = physical(b, 6)
        physical_b = Physical(physical_a.q, physical_a.dq, physical_a.quaternion, physical_a.body_gyro,
                              right[6]["command"])
        before, after = original.evaluate(physical_a)["observation"], policy.evaluate(physical_b)["observation"]
        channel = next(i for i, (x, y) in enumerate(zip(before, after)) if abs(x - y) > 1e-8)
        compared = 3
        first = {"index": compared, "field": "observation", "channel": channel,
                 "left": before[channel], "right": after[channel]}
    elif mode == "time":
        right = right[:-1]
        compared = 6
        first = {"index": 6, "field": "time_ns", "channel": None, "left": 120_000_000, "right": None}
    elif mode == "action":
        b["policy"]["layers"][-1]["bias"][1] += 0.20
        original = TruthPolicy(a).evaluate(physical(a, 0))["action"]
        disturbed = TruthPolicy(b).evaluate(physical(b, 0))["action"]
        require(abs(original[1] - disturbed[1]) > 1e-8, "test actor action was already saturated")
        compared = 0
        first = {"index": 0, "field": "action", "channel": 1, "left": original[1], "right": disturbed[1]}
    elif mode == "target":
        a_policy = TruthPolicy(a)
        original = a_policy.evaluate(physical(a, 0))["target"]
        joint = b["action_order"][2]
        b["actions"][joint]["minimum"] = original[2] + 0.026
        b["actions"][joint]["maximum"] = original[2] + 0.026
        compared = 0
        first = {"index": 0, "field": "target", "channel": 2, "left": original[2], "right": original[2] + 0.026}
    if mode == "equal":
        right.insert(3, deepcopy(right[2]))
    outputs = writable(root / "out")
    response = batch(app, ["compare", "--left-spec", str(dump(root / "a.json", a)),
                           "--right-spec", str(dump(root / "b.json", b)),
                           "--left", str(lines(root / "left.ndjson", left)),
                           "--right", str(lines(root / "right.ndjson", right)),
                           "--tolerance", "1e-8"], outputs / "qualification.json")
    require(response.get("status") == ("match" if first is None else "mismatch")
            and response.get("compared") == compared, "incorrect count or export qualification result")
    emitted = response.get("first")
    if first is None:
        require("first" in response and emitted is None, "a matching pair should have a null difference")
    else:
        require(isinstance(emitted, dict), "comparison difference is absent")
        for key in ("index", "channel", "field"):
            require(emitted.get(key) == first[key], f"incorrect first divergence {key}")
        for key in ("left", "right"):
            if first[key] is None:
                require(key in emitted and emitted[key] is None, "a missing value must be null")
            else:
                require(type(emitted.get(key)) in (int, float) and abs(emitted[key] - first[key]) <= 1e-8,
                        "first divergence value does not match physical fixture")
    return {"compared_updates": compared, "first_divergence": first}


def native_case(app: Path, root: Path) -> Record:
    """Check real articulated dynamics through differently named sensor and motor buses."""
    from native import shadow_rollout
    return shadow_rollout(app, root, verify)
