"""Score actual native delivery, fixture avoidance and restarted authority."""

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import mujoco
import numpy as np
from native_scenarios import (
    SIDES,
    NativePlant,
    animate,
    record,
    site,
    staging_case,
    success,
    unroll,
)


def load_robot(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def transfer(run, spec, *, plant_spec=None):
    """Require a lawful 12-axis trajectory with one observed, settled handoff."""
    result = run("plan-native", spec)
    if (
        not isinstance(result, dict)
        or result.get("status") != "ready"
        or not isinstance(result.get("commands"), list)
    ):
        return False
    native = NativePlant(plant_spec or spec)
    kinds = [step["kind"] for step in result["commands"]]
    if kinds.count("transfer") != 1 or kinds.count("move") < 2:
        return False
    return all(animate(native, item, spec) for item in result["commands"]) and success(
        native, spec
    )


def calibrated_transfer(run, xml):
    """Require the same fitted metrology to drive the separate true physical rig."""
    truth = staging_case(xml, variant=2)
    candidate = deepcopy(truth)
    native = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(native)
    detector = native.site("attachment_site").id
    frames = truth["calibration"]["calibration"]
    command = {
        "robot_xml": xml,
        "captures": {},
        "min_inliers": 10,
        "fit_threshold_m": 0.007,
        "fit_threshold_rad": 0.022,
        "validation_threshold_m": 0.006,
        "validation_threshold_rad": 0.022,
    }
    rng = np.random.default_rng(703)
    for arm in SIDES:
        readings = []
        for index in range(24):
            q = rng.uniform(-1.6, 1.6, 6)
            data.qpos[:] = q
            mujoco.mj_kinematics(native, data)
            sample = (
                unroll(frames[arm]["world_from_base"])
                @ site(data, detector)
                @ unroll(frames[arm]["flange_from_marker"])
            )
            sample[:3, 3] += rng.normal(0.0, 0.00024, 3)
            if index in (4, 13, 16):
                sample[:3, 3] += [0.11, -0.05, 0.07]
            readings.append({"q": q.tolist(), "marker": record(sample)})
        command["captures"][arm] = {"fit": readings[:18], "validation": readings[18:]}
    commissioned = run("commission-native", command)
    if not status(commissioned, "ok"):
        return False
    candidate["calibration"] = commissioned
    return transfer(run, candidate, plant_spec=truth)


def native_plan_checks(run, xml):
    cases = {
        "native_handoff_12_axis_shape": lambda: transfer(
            run, staging_case(xml, variant=0)
        ),
        "native_transfer_shifted_bases_and_tools": lambda: calibrated_transfer(
            run, xml
        ),
        "native_raise_object_around_fixture": lambda: transfer(
            run, staging_case(xml, variant=2, blocker=True)
        ),
        "native_block_outside_arm_workspace": lambda: (
            run("plan-native", staging_case(xml, variant=1, blocked=True))
            == {"status": "blocked", "commands": []}
        ),
    }
    wrong = staging_case(xml)
    wrong["payload"]["half_size_m"][1] = 0.0
    results = {
        "malformed_native_payload_preserves_report": bool(
            run("plan-native", wrong, invalid=True)
        )
    }
    for name, probe in cases.items():
        try:
            results[name] = bool(probe())
        except (
            AttributeError,
            KeyError,
            IndexError,
            ValueError,
            OverflowError,
            TypeError,
        ):
            results[name] = False
    return results


def request(window, mission):
    return {
        "mission": mission,
        "sequence": 1,
        "revision": 51,
        "window": deepcopy(window),
        "previous": None,
    }


def status(reply, expected):
    return isinstance(reply, dict) and reply.get("status") == expected


def finish(reply, old, readback, *, confirmed=False):
    packet = deepcopy(old)
    packet["sequence"] += 1
    packet["window"]["measured"] = readback
    packet["previous"] = {"id": reply["command_id"], "outcome": "completed"}
    if reply["command"]["kind"] == "transfer":
        packet["previous"]["receiver_confirmed"] = confirmed
    return packet


def execute(run, state, plant, packet, reply, *, known_ids=()):
    """Drive physical actuators and reject transfer completion without matching custody."""
    issued = set(known_ids)
    # Each successful primitive advances at least one plant tick before the public deadline.
    while True:
        if status(reply, "ready"):
            return success(plant, packet["window"])
        if (
            not status(reply, "issued")
            or not isinstance(reply.get("command_id"), str)
            or reply["command_id"] in issued
        ):
            return False
        issued.add(reply["command_id"])
        command = reply["command"]
        window = packet["window"]
        # Replanned primitives are anchored to correlated measured readback.
        if command["kind"] == "move":
            plant.target = plant.data.qpos[plant.joints].copy()
        if not animate(plant, command, window):
            return False
        next_packet = finish(reply, packet, plant.readback(), confirmed=True)
        if command["kind"] == "transfer":
            rejected = deepcopy(next_packet)
            rejected["previous"]["receiver_confirmed"] = False
            if not status(run("dispatch-native", rejected, state=state), "rejected"):
                return False
        packet = next_packet
        reply = run("dispatch-native", packet, state=state)


def recovered_lost_reply(run, root, xml):
    spec = staging_case(xml, variant=2)
    state = root / "lost-state.json"
    packet = request(spec, "loaded-arm-transfer")
    if run("dispatch-native", packet, state=state, lost_reply=True) is not True:
        return False
    original = run("dispatch-native", packet, state=state)
    repeated = run("dispatch-native", dict(reversed(list(packet.items()))), state=state)
    if original != repeated or not status(original, "issued"):
        return False
    rogue = deepcopy(packet)
    rogue["revision"] += 1
    if not status(run("dispatch-native", rogue, state=state), "rejected"):
        return False
    return execute(run, state, NativePlant(spec), packet, original)


def recover_revocation(
    run: Callable[..., dict[str, Any] | bool | None], root: Path, xml: str
) -> bool:
    """Execute a loaded withdrawal, restart the dispatcher, and verify delivery.

    Args:
        run: Isolated candidate command runner.
        root: Writable journal directory for the native dispatch cases.
        xml: Model XML text for the supplied single arm.

    Returns:
        Whether the candidate retained custody, braked and recovered on the plant.
    """
    spec = staging_case(xml, variant=2)
    state = root / "revoked-state.json"
    packet = request(spec, "withdrawn-loaded-motion")
    plant = NativePlant(spec)
    reply = run("dispatch-native", packet, state=state)
    issued = set()
    while status(reply, "issued") and reply["command"]["kind"] == "move":
        command_id = reply["command_id"]
        if not isinstance(command_id, str) or not command_id or command_id in issued:
            return False
        issued.add(command_id)
        primitive = reply["command"]
        first_tick = primitive["start"] + max(
            1, (primitive["end"] - primitive["start"]) // 5
        )

        def moving(cell: NativePlant, first_tick=first_tick) -> bool:
            """Select a tick after the move has entered its measured motion."""
            peak_rate = float(np.max(abs(cell.data.qvel[cell.dofs])))
            return cell.tick >= first_tick and peak_rate > 0.025

        plant.target = plant.data.qpos[plant.joints].copy()
        if not animate(plant, primitive, spec, withdraw_at=moving):
            return False
        if plant.tick < primitive["end"]:
            break
        # A short or slow prefix can finish before there is a moving interior tick.
        packet = finish(reply, packet, plant.readback())
        reply = run("dispatch-native", packet, state=state)
    else:
        return False
    amended = staging_case(xml, variant=2, blocker=True)
    shape = unroll(amended["fixtures"][0]["world_from_box"])
    geom = plant.model.geom("fixture_0").id
    plant.model.geom_pos[geom] = shape[:3, 3]
    mujoco.mj_forward(plant.model, plant.data)
    revised = deepcopy(packet)
    revised["window"]["fixtures"] = amended["fixtures"]
    revised["window"]["measured"] = plant.readback()
    revised["sequence"] += 1
    revised["revision"] += 1
    revised["previous"] = {"id": reply["command_id"], "outcome": "withdrawn"}
    fake = deepcopy(revised)
    fake["window"]["measured"]["owner"] = "right"
    if not status(run("dispatch-native", fake, state=state), "rejected"):
        return False
    answer = run("dispatch-native", revised, state=state)
    if not status(answer, "issued") or answer["command"]["kind"] != "brake":
        return False
    if run("dispatch-native", revised, state=state) != answer:
        return False
    return execute(run, state, plant, revised, answer, known_ids=issued)


def never_fake_custody(run, root, xml):
    spec = staging_case(xml, variant=2)
    state = root / "corrupt-custody.json"
    packet = request(spec, "guarded-custody")
    reply = run("dispatch-native", packet, state=state)
    if not status(reply, "issued"):
        return False
    fake = deepcopy(packet)
    fake["sequence"] = 2
    fake["revision"] += 1
    fake["previous"] = {"id": reply["command_id"], "outcome": "withdrawn"}
    fake["window"]["measured"]["tick"] += 1
    fake["window"]["measured"]["owner"] = "right"
    return (
        status(run("dispatch-native", fake, state=state), "rejected")
        and run("dispatch-native", packet, state=state) == reply
    )


def native_dispatch_checks(run, root, xml):
    checks = {
        "native_resume_after_lost_authority_reply": recovered_lost_reply,
        "native_revocation_brake_and_alternate_fixture": recover_revocation,
        "native_reject_forged_payload_owner": never_fake_custody,
    }
    result = {}
    for name, probe in checks.items():
        try:
            result[name] = bool(probe(run, root, xml))
        except (
            AttributeError,
            KeyError,
            IndexError,
            ValueError,
            OverflowError,
            TypeError,
        ):
            result[name] = False
    return result
