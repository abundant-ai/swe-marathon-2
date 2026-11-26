"""Observe native payload reseating, survey authority and physical redelivery."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import cos, sin
from pathlib import Path
from typing import Any, Protocol

import mujoco
import numpy as np
from native_plan_checks import finish, request
from native_scenarios import (
    SIDES,
    NativePlant,
    animate,
    distance_pose,
    group,
    quaternion,
    record,
    site,
    staging_case,
    success,
    unroll,
    xform,
)

COMMAND = "dispatch-grasp-recovery"
SURVEY = {
    "max_age_ticks": 48,
    "position_tolerance_m": 0.006,
    "rotation_tolerance_rad": 0.020,
}
Record = dict[str, Any]


class Run(Protocol):
    """Run one isolated command with a durable state directory."""

    def __call__(
        self, command: str, spec: Record, *, state: Path, lost_reply: bool = False
    ) -> Record | bool | None:
        """Execute a native request and read its reply when publication succeeds."""


def require(condition: Any, detail: str) -> None:
    """Fail a native witness as soon as a measured or protocol invariant breaks."""
    if not condition:
        raise ValueError(detail)


def one_holder(plant: NativePlant) -> bool:
    """Inspect the actual native welds for exactly the named current holder."""
    return [arm for arm in SIDES if plant.data.eq_active[plant.weld[arm]]] == [
        plant.owner
    ]


def roll(angle: float) -> np.ndarray:
    """Return an object-axis roll matrix for a commanded reseating angle in radians."""
    c, s = cos(angle), sin(angle)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def reseat(plant: NativePlant, spec: Record) -> np.ndarray:
    """Apply and measure a rigid reseating under the safety interlock.

    The event falls on the same boundary as a settled drive receipt. Sweep the
    reseating between those two event states, then leave the actual free body and
    site weld at their new pose for all subsequent native time integration.

    Args:
        plant: Stopped native cell with one active payload weld.
        spec: Mission window containing the original commissioned offsets.

    Returns:
        True object-from-grasp transform after the slip, private to the fixture.
    """
    owner = plant.owner
    old = unroll(spec["payload"]["object_from_grasp"][owner])
    angle, offset = (
        (0.154, [0.0, 0.012, 0.006])
        if owner == "left"
        else (-0.169, [0.0, -0.011, 0.004])
    )
    mujoco.mj_forward(plant.model, plant.data)
    grip = site(plant.data, plant.grippers[owner])
    part = plant.asset_idx
    holder_site = plant.payload_sites[owner]
    before = plant.object_pose()
    require(one_holder(plant), "part reseated without a single physical holder")
    for fraction in np.linspace(0.0, 1.0, 17)[1:]:
        slipped = old @ xform(fraction * np.array(offset), roll(fraction * angle))
        world_part = grip @ np.linalg.inv(slipped)
        plant.model.site_pos[holder_site] = slipped[:3, 3]
        plant.model.site_quat[holder_site] = quaternion(slipped[:3, :3])
        plant.data.qpos[part : part + 3] = world_part[:3, 3]
        plant.data.qpos[part + 3 : part + 7] = quaternion(world_part[:3, :3])
        plant.data.qvel[plant.asset_dof : plant.asset_dof + 6] = 0.0
        mujoco.mj_forward(plant.model, plant.data)
        separation = min(
            mujoco.mj_geomDistance(plant.model, plant.data, a, b, 0.8, None)
            for a, b in plant.distances
        )
        plant.clearance_seen = min(plant.clearance_seen, float(separation))
        plant.contact_peak = max(plant.contact_peak, int(plant.data.ncon))
        require(
            separation >= spec["clearance_m"] - 1e-7 and plant.data.ncon == 0,
            "unsafe native clearance during the physical slip",
        )
    _, turn = distance_pose(before, plant.object_pose())
    require(
        turn > 0.11 and one_holder(plant),
        "slip did not invalidate the nominal geometry",
    )
    return old @ xform(np.array(offset), roll(angle))


def continue_survey(previous: Record, cell: NativePlant, rows: list[Record]) -> Record:
    """Form the next interlocked survey tick after a command-null reply."""
    return {
        **previous,
        "sequence": previous["sequence"] + 1,
        "previous": None,
        "window": {**previous["window"], "measured": cell.readback()},
        "observations": rows,
    }


@dataclass
class Mission:
    """Own a single candidate journal and physical execution history."""

    run: Run
    journal: Path
    window: Record
    plant: NativePlant
    packet: Record
    issued: set[str] = field(default_factory=set)
    moves: int = 0
    transfers: int = 0
    receipt: Record | None = None

    def response(self, *, recover_lost_reply: bool = False) -> Record:
        """Fetch the durable response with exact mission, sequence and revision."""
        if recover_lost_reply:
            require(
                self.run(COMMAND, self.packet, state=self.journal, lost_reply=True)
                is True,
                "reply publication failure did not exercise the accepted survey",
            )
        result = self.run(COMMAND, self.packet, state=self.journal)
        require(
            isinstance(result, dict)
            and all(
                result.get(key) == self.packet[key]
                for key in ("mission", "sequence", "revision")
            ),
            "missing or unrelated authority response",
        )
        return result

    def execute(self, reply: Record) -> Record:
        """Drive a newly issued command and return its independently measured receipt."""
        command = reply.get("command")
        identity = reply.get("command_id")
        require(
            reply.get("status") == "issued"
            and isinstance(command, dict)
            and isinstance(identity, str)
            and bool(identity)
            and identity not in self.issued,
            "expected a fresh motion authority command",
        )
        self.issued.add(identity)
        if command["kind"] == "move":
            self.plant.target = self.plant.data.qpos[self.plant.joints].copy()
        require(
            animate(self.plant, command, self.window) and one_holder(self.plant),
            f"unsafe {command['kind']} or incorrect physical possession at tick {self.plant.tick}",
        )
        self.moves += command["kind"] == "move"
        self.transfers += command["kind"] == "transfer"
        following = finish(reply, self.packet, self.plant.readback(), confirmed=True)
        following["observations"] = []
        return following

    def hold_until(self, tick: int) -> None:
        """Let the native interlock hold a fixed joint target until a survey tick."""
        while self.plant.tick < tick:
            require(
                self.plant.step(self.plant.target, np.zeros(12))
                and one_holder(self.plant),
                f"unsafe interlock hold at tick {self.plant.tick}",
            )

    def expect_wait(self, *, blocked: bool = False) -> None:
        """Require a non-authorizing response while the survey is unresolved."""
        reply = self.response()
        require(
            reply.get("status") == ("blocked" if blocked else "surveying")
            and all(
                key in reply and reply[key] is None
                for key in ("command", "command_id", "grasp")
            ),
            f"unqualified survey released authority at tick {self.plant.tick}",
        )

    def replay(self, reply: Record) -> None:
        """Check object-key-order independence and rejection of altered sequence contents."""
        reversed_packet = dict(reversed(list(self.packet.items())))
        require(
            self.run(COMMAND, reversed_packet, state=self.journal) == reply,
            "exact retry did not preserve survey authority and command identity",
        )
        altered = {**self.packet, "observations": []}
        fake = self.run(COMMAND, altered, state=self.journal)
        require(
            isinstance(fake, dict)
            and fake.get("status") == "rejected"
            and all(
                key in fake and fake[key] is None
                for key in ("command", "command_id", "grasp")
            ),
            "changed packet at the same sequence was accepted",
        )
        require(
            self.response() == reply, "a rejected packet changed the accepted command"
        )

    def prefix(self, trigger_holder: str) -> None:
        """Reach the interlock event after a loaded prefix or confirmed handoff."""
        start = self.plant.data.qpos[self.plant.joints].copy()
        while True:
            reply = self.response()
            require(
                "grasp" in reply and reply["grasp"] is None,
                "epoch zero invented a recovered grasp",
            )
            self.packet = self.execute(reply)
            travelled = float(
                np.max(np.abs(start - self.plant.data.qpos[self.plant.joints]))
            )
            speed = float(np.max(np.abs(self.plant.data.qvel[self.plant.dofs])))
            eligible = self.moves > 0 and travelled > 0.08 and speed <= 0.025
            if self.plant.owner == trigger_holder and eligible:
                return
            require(
                self.plant.tick < self.window["deadline_tick"]
                and self.plant.owner == "left",
                "native mission did not exercise the stopped slip event",
            )

    def finish(self, first_reply: Record) -> None:
        """Complete the mission under recovered geometry and verify actual delivery."""
        reply = first_reply
        while reply.get("status") != "ready":
            require(
                reply.get("grasp") == self.receipt,
                "accepted grasp receipt changed while executing recovery",
            )
            self.packet = self.execute(reply)
            reply = self.response()
        require(
            reply.get("grasp") == self.receipt
            and all(
                key in reply and reply[key] is None for key in ("command", "command_id")
            ),
            "terminal decision lost the recovered pose",
        )
        require(
            self.transfers == 1
            and one_holder(self.plant)
            and success(self.plant, self.window),
            "recovery failed to physically deliver with confirmed custody",
        )


def capture(
    mission: Mission, tick: int, rng: np.random.Generator, *, wrong: bool = False
) -> tuple[Record, np.ndarray]:
    """Sample independently tracked payload pose and matching captured encoders.

    Args:
        mission: Interlocked cell, physically integrated up through earlier samples.
        tick: Requested acquisition on the native 5 ms clock.
        rng: Sensor noise stream dedicated to the current mission.
        wrong: Introduce an alternate camera pose hypothesis keeping valid metadata.

    Returns:
        Public observation and the implied transform recomputed from the private
        native hand site at the same captured joints.
    """
    mission.hold_until(tick)
    mujoco.mj_forward(mission.plant.model, mission.plant.data)
    pose = mission.plant.object_pose()
    pose[:3, 3] += rng.normal(0.0, 0.00045, 3)
    pose[:3, :3] = pose[:3, :3] @ roll(float(rng.normal(0.0, 0.0017)))
    if wrong:
        pose[:3, 3] += [0.034, -0.019, 0.013]
        pose[:3, :3] = pose[:3, :3] @ roll(0.093)
    owner = mission.plant.owner
    q = group(mission.plant.data.qpos[mission.plant.joints])
    hand = site(mission.plant.data, mission.plant.grippers[owner])
    row = {
        "capture_tick": tick,
        "epoch": 1,
        "owner": owner,
        "q": q,
        "world_from_object": record(pose),
    }
    return row, np.linalg.solve(pose, hand)


def assess_receipt(
    reply: Record, holder: str, captured: Mapping[int, np.ndarray]
) -> Record:
    """Check support and physical agreement while allowing different valid pose fits.

    Args:
        reply: Decision after the final inlier arrives.
        holder: Physical owner of the part at observation time.
        captured: Eligible independent support transforms indexed by capture tick.

    Returns:
        Candidate receipt after verifying its support and fitted SE(3) pose.
    """
    recovered = reply.get("grasp")
    require(
        isinstance(recovered, dict)
        and recovered.get("owner") == holder
        and recovered.get("epoch") == 1,
        "new grasp did not identify the holder and source epoch",
    )
    ticks = recovered.get("captures")
    require(
        isinstance(ticks, list)
        and all(type(tick) is int for tick in ticks)
        and ticks == sorted(captured),
        "fit used stale, duplicate, or incompatible survey evidence",
    )
    estimate = unroll(recovered["object_from_grasp"])
    for expected in captured.values():
        position, angle = distance_pose(estimate, expected)
        require(
            position <= SURVEY["position_tolerance_m"]
            and angle <= SURVEY["rotation_tolerance_rad"],
            f"fitted frame disagrees with independent pose, error {position:.4f} m / {angle:.4f} rad",
        )
    return recovered


def survey_scene(mission: Mission, *, contradictory: bool) -> dict[int, np.ndarray]:
    """Exercise freshness, deduplication and independent agreement at native timestamps.

    Generates two valid captures first, waits for them to expire, then supplies
    a new pair and a named outlier. The delayed third good observation arrives
    last. A conflicting scene also supplies two readings supporting the other
    hypothesis, producing equally sized incompatible groups.
    """
    zero = mission.plant.tick
    owner = mission.plant.owner
    other_owner = next(arm for arm in SIDES if arm != owner)
    rng = np.random.default_rng(8723 if owner == "left" else 5261)
    early, _ = capture(mission, zero + 7, rng)
    later, _ = capture(mission, zero + 13, rng)
    mission.hold_until(zero + 16)
    stale_labels = [
        {**early, "epoch": 0, "capture_tick": zero + 6},
        {**early, "owner": other_owner, "capture_tick": zero + 11},
        {**early, "capture_tick": zero - 1},
        {**later, "capture_tick": zero + 27},
    ]
    mission.packet = continue_survey(
        mission.packet, mission.plant, [later, *stale_labels, early, early]
    )
    mission.expect_wait()

    first, first_truth = capture(mission, zero + 64, rng)
    outlier, _ = capture(mission, zero + 65, rng, wrong=True)
    bad_second, _ = capture(mission, zero + 66, rng, wrong=True)
    delayed, delayed_truth = capture(mission, zero + 67, rng)
    bad_third, _ = capture(mission, zero + 68, rng, wrong=True)
    newest, newest_truth = capture(mission, zero + 70, rng)
    mission.hold_until(zero + 72)
    duplicate = {**first, "world_from_object": outlier["world_from_object"]}
    mission.packet = continue_survey(
        mission.packet, mission.plant, [newest, first, duplicate, early, later, outlier]
    )
    mission.expect_wait()
    mission.hold_until(zero + 85)
    final_delivery = [delayed, bad_second, bad_third] if contradictory else [delayed]
    mission.packet = continue_survey(mission.packet, mission.plant, final_delivery)
    return {
        first["capture_tick"]: first_truth,
        delayed["capture_tick"]: delayed_truth,
        newest["capture_tick"]: newest_truth,
    }


def episode(
    run: Run, root: Path, xml: str, name: str, holder: str, *, contradictory: bool
) -> Record:
    """Run one native grasp recovery and return the independently witnessed measurements."""
    window = staging_case(xml, variant=2, drawn=True)
    window["handoff_object_poses"] = window["handoff_object_poses"][:1]
    window["layout"]["stations"] = ["H1"]
    window["deadline_tick"] = 1500 if contradictory else 3600
    packet = {
        **request(window, name),
        "grasp_epoch": 0,
        "survey": SURVEY,
        "observations": [],
    }
    mission = Mission(run, root / f"{name}.json", window, NativePlant(window), packet)
    mission.prefix(holder)
    mujoco.mj_forward(mission.plant.model, mission.plant.data)
    before = mission.plant.object_pose()
    truth = reseat(mission.plant, window)
    shift_m, turn_rad = distance_pose(before, mission.plant.object_pose())
    slip_tick = mission.plant.tick
    mission.packet["revision"] += 1
    mission.packet["grasp_epoch"] = 1
    mission.packet["window"]["measured"] = mission.plant.readback()
    mission.expect_wait()
    support = survey_scene(mission, contradictory=contradictory)
    identified_tick = None
    fit_error_m, fit_error_rad = None, None
    if contradictory:
        mission.expect_wait()
        mission.hold_until(window["deadline_tick"])
        mission.packet = continue_survey(mission.packet, mission.plant, [])
        mission.expect_wait(blocked=True)
        require(
            mission.plant.owner == holder and mission.transfers == 0,
            "ambiguous grasp lost the original custody",
        )
    else:
        identified_tick = mission.plant.tick
        agreed = mission.response(recover_lost_reply=True)
        mission.receipt = assess_receipt(agreed, holder, support)
        fit_error_m, fit_error_rad = distance_pose(
            unroll(mission.receipt["object_from_grasp"]), truth
        )
        mission.replay(agreed)
        mission.finish(agreed)
    return {
        "initial_holder": holder,
        "slip_tick": slip_tick,
        "identified_tick": identified_tick,
        "measured_shift_m": shift_m,
        "measured_turn_rad": turn_rad,
        "fit_error_m": fit_error_m,
        "fit_error_rad": fit_error_rad,
        "minimum_clearance_m": mission.plant.clearance_seen,
        "contact_peak": mission.plant.contact_peak,
        "final_holder": mission.plant.owner,
        "final_tick": mission.plant.tick,
        "moves": mission.moves,
        "transfers": mission.transfers,
        "support_ticks": sorted(support) if not contradictory else [],
        "ended_interlocked": contradictory,
    }


def grasp_recovery_checks(
    run: Run, root: Path, xml: str, *, observations: dict[str, Record] | None = None
) -> dict[str, bool]:
    """Evaluate measured recovery before and after handoff plus ambiguous-survey rejection.

    Args:
        run: Isolated candidate subprocess runner used by the checkpoint verifier.
        root: Writable directory for independent durable mission journals.
        xml: The licensed and commissioned single-arm model text.
        observations: Optional destination for native observations or failure diagnostics.

    Returns:
        Pass flags keyed by the authored simulator scenario.
    """
    cases = (
        ("native_relocalize_giver_grasp", "left", False),
        ("native_relocalize_receiver_grasp", "right", False),
        ("native_hold_unconfirmed_grasp", "left", True),
    )
    checks = {}
    for name, side, contradictory in cases:
        try:
            evidence = episode(run, root, xml, name, side, contradictory=contradictory)
            checks[name] = True
        except (
            AttributeError,
            IndexError,
            KeyError,
            OverflowError,
            TypeError,
            ValueError,
        ) as error:
            evidence = {"failure": str(error)}
            checks[name] = False
        if observations is not None:
            observations[name] = evidence
    return checks
