"""Recover active payload attachment under the native cell interlock."""

from collections.abc import Callable
import os
from pathlib import Path
from uuid import uuid4

import numpy as np

from .dispatch_native import READY_RAD_S, authority, checked_packet, choose, counter, encoded, locked_journal
from .grasp_observations import collect_grasp_observations, fit_grasp
from .native_cell import number
from .plan_native import Problem


def checked_survey(packet: dict) -> None:
    """Check fixed survey limits and the observation envelope before using the journal.

    Args:
        packet: Stage 8 packet whose Stage 7 fields have already been decoded.

    Raises:
        ValueError: The camera settings or observation envelope are invalid.
    """
    counter(packet["grasp_epoch"], 0)
    survey = packet["survey"]
    if (type(survey) is not dict or counter(survey["max_age_ticks"], 1) > 200
            or type(packet["observations"]) is not list):
        raise ValueError("invalid camera survey configuration")
    number(survey["position_tolerance_m"], positive=True)
    number(survey["rotation_tolerance_rad"], positive=True)


def can_accept_epoch(previous: dict | None, packet: dict, problem: Problem, receipt: str) -> bool:
    """Fence survey configuration and require a settled interlock to start a new epoch.

    Args:
        previous: Most recent accepted packet for the mission, if any.
        packet: New packet whose ordinary drive receipt has been checked.
        problem: Native window providing measured joint speeds.
        receipt: Stage 7 authority classification for the settled command or free slot.

    Returns:
        Whether the new packet can change survey state.
    """
    epoch = packet["grasp_epoch"]
    if previous is None:
        return epoch == 0
    if encoded(packet["survey"]) != encoded(previous["survey"]):
        return False
    prior_epoch = previous["grasp_epoch"]
    return (epoch == prior_epoch or (epoch == prior_epoch + 1
                                    and packet["revision"] > previous["revision"]
                                    and receipt in ("new", "completed")
                                    and np.all(np.abs(problem.velocity) <= READY_RAD_S)))


def recovered_decision(
    existing: dict | None, packet: dict, problem: Problem, receipt: str
) -> tuple[str, dict | None, dict | None, dict]:
    """Apply current survey evidence and plan one primitive under the recovered attachment.

    Args:
        existing: Prior accepted journal entry, or None for a new mission.
        packet: Authorized controller and camera packet.
        problem: Decoded commissioned geometry and measured cell.
        receipt: Stage 7 ordinary command authority classification.

    Returns:
        Status, command or None, accepted survey receipt or None, and new survey journal.
    """
    epoch = packet["grasp_epoch"]
    history = existing["survey_state"] if existing is not None else {}
    corrections = dict(history.get("corrections", {}))
    start_tick = history.get("start_tick", problem.tick)
    samples = history.get("samples", {})
    grasp = existing["reply"]["grasp"] if existing is not None else None
    if existing is not None and epoch != existing["packet"]["grasp_epoch"]:
        start_tick, samples, grasp = problem.tick, {}, None

    if epoch > 0 and grasp is None:
        survey = packet["survey"]
        samples = collect_grasp_observations(samples, packet["observations"], epoch=epoch, owner=problem.owner,
                                             first_tick=start_tick, now_tick=problem.tick,
                                             max_age_ticks=survey["max_age_ticks"],
                                             joint_limits=problem.geometry.cell.ranges)
        fit = fit_grasp(samples, problem.geometry, problem.owner, minimum_captures=3,
                        position_tolerance_m=survey["position_tolerance_m"],
                        rotation_tolerance_rad=survey["rotation_tolerance_rad"])
        if fit is None:
            status = "surveying" if problem.tick < problem.deadline else "blocked"
            return status, None, None, dict(start_tick=start_tick, samples=samples, corrections=corrections)
        offset, captures = fit
        grasp = dict(owner=problem.owner, epoch=epoch, object_from_grasp=offset, captures=captures)
        corrections[problem.owner] = offset
        samples = {}

    if corrections:
        window = packet["window"]
        payload = window["payload"]
        corrected = {**window, "payload": {**payload, "object_from_grasp": {
            **payload["object_from_grasp"], **corrections}}}
        status, command = choose({**packet, "window": corrected}, Problem.read(corrected), receipt)
    else:
        status, command = choose(packet, problem, receipt)
    return status, command, grasp, dict(start_tick=start_tick, samples=samples, corrections=corrections)


def dispatch_grasp_recovery(packet: dict, state_path: Path, publish: Callable[[Path, dict], None]) -> dict:
    """Recover or dispatch under one durable mission transaction.

    Args:
        packet: Native Stage 7 packet with grasp epoch and camera observations.
        state_path: Journal independent of the Stage 7 command's state path.
        publish: Atomic JSON writer to commit before a reply is returned.

    Returns:
        An accepted, idempotent, or rejected decision with a survey receipt.
    """
    identity, problem = checked_packet(packet)
    checked_survey(packet)
    with locked_journal(state_path) as (state, lock):
        mission = identity["mission"]
        existing = state.get(mission)
        previous = existing["packet"] if existing is not None else None
        if previous is not None and encoded(previous) == encoded(packet):
            return existing["reply"]
        receipt = authority(existing, packet, problem)
        if receipt is None or not can_accept_epoch(previous, packet, problem, receipt):
            return dict(identity, status="rejected", command=None, command_id=None, grasp=None)
        status, command, grasp, survey_state = recovered_decision(existing, packet, problem, receipt)
        reply = dict(identity, status=status, command=command, command_id=uuid4().hex if command else None,
                     grasp=grasp)
        state[mission] = dict(packet=packet, reply=reply, survey_state=survey_state)
        publish(state_path, state)
        os.fsync(lock)
        return reply
