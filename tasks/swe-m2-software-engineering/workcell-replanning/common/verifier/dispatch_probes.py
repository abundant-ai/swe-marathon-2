"""Execute timed primitives and controller retransmissions in independent processes."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from uuid import uuid4

from geometry import Json
from missions import missions
from timed_checks import run_command, valid_plan, valid_prefix


def matches(packet: Json, reply: object, status: str) -> bool:
    """Validate the acknowledgement envelope and the pending command identity."""
    if not isinstance(reply, dict) or reply.get("status") != status:
        return False
    for key in ("mission_id", "sequence", "revision"):
        if type(reply.get(key)) is not type(packet[key]) or reply[key] != packet[key]:
            return False
    if "command" not in reply or "command_id" not in reply:
        return False
    command, token = reply["command"], reply["command_id"]
    if command is None:
        return token is None
    return status != "rejected" and isinstance(command, dict) and isinstance(token, str) and bool(token)


def at_rest(window: Json, tick: int, node: str) -> Json:
    """Issue a new request from a completed measured controller position."""
    return dict(
        window, measured={"tick": tick, "q": window["nodes"][node], "dq": [0, 0, 0]},
        start_node=node, brake_ticks=0,
    )


def next_packet(
    packet: Json, reply: Json, window: Json, *,
    revision: int | None = None, outcome: str = "completed",
) -> Json:
    """Construct the next ordered packet and acknowledge its preceding command."""
    return dict(
        packet, sequence=packet["sequence"] + 1,
        revision=packet["revision"] if revision is None else revision,
        window=window, previous={"command_id": reply["command_id"], "outcome": outcome},
    )


def retry_packets(exchange, packet: Json, reply: Json) -> bool:
    """Test altered duplicate rejection before confirming the original response."""
    conflict = dict(packet, revision=packet["revision"] + 1)
    return (matches(conflict, exchange(conflict), "rejected")
            and exchange(dict(reversed(tuple(packet.items())))) == reply)


def invalid_acknowledgements(exchange, following: Json) -> bool:
    """Exercise stale authority, false acknowledgement and sequence holes."""
    previous, window = following["previous"], following["window"]
    measured = window["measured"]
    other_pose = next(name for name, q in window["nodes"].items() if q != measured["q"])
    early = dict(window, measured=dict(measured, tick=measured["tick"] - 1))
    wrong_pose = at_rest(window, measured["tick"], other_pose)
    packet_cases = (
        dict(following, revision=following["revision"] - 1),
        dict(following, sequence=following["sequence"] + 1),
        dict(following, previous=dict(previous, command_id=uuid4().hex)),
        dict(following, previous=None),
        dict(following, window=early),
        dict(following, window=wrong_pose),
        dict(following, revision=following["revision"] + 1,
             previous=dict(previous, outcome="cancelled")),
    )
    return all(matches(packet, exchange(packet), "rejected") for packet in packet_cases)


def initial_exchange(exchange, packet: Json, competing: Json | None) -> tuple[Json, Json]:
    """Open two independent missions and replay the primary start concurrently."""
    if competing is None:
        return exchange(packet), {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(exchange, packet)
        duplicate = pool.submit(exchange, packet)
        other = pool.submit(exchange, competing)
        reply, other_reply = first.result(), other.result()
        if duplicate.result() != reply or not matches(competing, other_reply, "ready"):
            return {}, {}
    return reply, other_reply


def interrupted_window(
    prior: Json, revised: Json, command: Json, interrupt: Json,
) -> Json:
    """Read position and speed during an issued transfer and commission its brake node."""
    edge = next(item for item in prior["edges"] if item["id"] == command["edge"])
    tick = interrupt["tick"]
    fraction = (tick - command["start"]) / edge["ticks"]
    seconds = edge["ticks"] * prior["tick_seconds"]
    q_start, q_end = prior["nodes"][edge["source"]], prior["nodes"][edge["target"]]
    position_scale = fraction * fraction * (3 - 2 * fraction)
    speed_scale = 6 * fraction * (1 - fraction) / seconds
    position = [a + (b - a) * position_scale for a, b in zip(q_start, q_end, strict=True)]
    velocity = [(b - a) * speed_scale for a, b in zip(q_start, q_end, strict=True)]
    deceleration_time = interrupt["brake_ticks"] * revised["tick_seconds"]
    stop = [q + dq * deceleration_time / 2 for q, dq in zip(position, velocity, strict=True)]
    brake_node, resume_edge = "interruption-stop", "resume-approach"
    return dict(
        revised, start_node=brake_node, brake_ticks=interrupt["brake_ticks"],
        measured={"tick": tick, "q": position, "dq": velocity},
        nodes=dict(revised["nodes"], **{brake_node: stop}),
        edges=[*revised["edges"], {"id": resume_edge, "source": brake_node,
                                  "target": interrupt["resume_node"], "ticks": interrupt["resume_ticks"]}],
    )


def forecast_update(
    packet: Json, reply: Json, revised: Json, cursor: tuple[int, str],
) -> Json:
    """Advance controller telemetry to the first forecast update boundary."""
    if reply["command"]["kind"] == "move":
        return next_packet(
            packet, reply, at_rest(revised, *cursor), revision=packet["revision"] + 1,
        )
    return next_packet(packet, reply, revised, revision=packet["revision"] + 1, outcome="cancelled")


def complete_mission(exchange, case: Json) -> bool:
    """Run a whole job, verifying commands independently and exercising journal recovery."""
    window = case["spec"]
    status = "ready" if case["expect_ready"] else "blocked"
    prior, interrupt = case.get("prior"), case.get("interrupt")
    if interrupt:
        prior = dict(prior, deadline=16)
    restart = case["family"] == "restart"
    packet = {"mission_id": uuid4().hex, "sequence": 1, "revision": 19,
              "previous": None, "window": prior or window}
    competing = None
    if restart:
        competing = dict(packet, mission_id=uuid4().hex, window=missions()[0]["spec"])
    reply, other_reply = initial_exchange(exchange, packet, competing)
    if not matches(packet, reply, "ready" if prior else status):
        return False
    if not retry_packets(exchange, packet, reply):
        return False

    issued_ids = set()
    if prior is not None:
        cursor = valid_prefix(prior, [reply["command"]])
        if cursor is None or cursor[1] is None:
            return False
        issued_ids.add(reply["command_id"])
        if interrupt:
            command = reply["command"]
            if (command.get("edge") != interrupt["edge"]
                    or not command["start"] < interrupt["tick"] < command["end"]):
                return False
            window = interrupted_window(prior, window, command, interrupt)
            update = next_packet(
                packet, reply, window, revision=packet["revision"] + 1, outcome="cancelled",
            )
        else:
            update = forecast_update(packet, reply, window, cursor)
        false_authority = dict(update, revision=packet["revision"])
        if not matches(false_authority, exchange(false_authority), "rejected"):
            return False
        stale = packet
        packet, reply = update, exchange(update)
        if not matches(stale, exchange(stale), "rejected"):
            return False

    checked_ack = False
    for _ in range(window["deadline"] - window["measured"]["tick"] + 1):
        current = packet["window"]
        if not matches(packet, reply, status):
            return False
        tick, node = current["measured"]["tick"], current["start_node"]
        command = reply["command"]
        if command is None:
            result = {"status": status, "commands": []}
            if not valid_plan(current, result, expect_ready=case["expect_ready"]):
                return False
            if competing is not None:
                if other_reply != exchange(competing):
                    return False
            return True

        if reply["command_id"] in issued_ids or (status == "blocked" and command.get("kind") == "move"):
            return False
        issued_ids.add(reply["command_id"])
        if status == "ready" and node == current["goal_node"] and not current["brake_ticks"]:
            return False
        cursor = run_command(current, command, tick, None if current["brake_ticks"] else node)
        if cursor is None:
            return False
        following = next_packet(packet, reply, at_rest(current, *cursor))
        if not checked_ack:
            if not invalid_acknowledgements(exchange, following):
                return False
            if restart:
                if exchange(following, lose_output=True) is not True:
                    return False
                conflict = dict(following, revision=following["revision"] + 1)
                if not matches(conflict, exchange(conflict), "rejected"):
                    return False
            checked_ack = True
        stale = packet
        packet, reply = following, exchange(following)
        if restart and not matches(stale, exchange(stale), "rejected"):
            return False
    return False


def dispatch_checks(run) -> Json:
    """Use a fresh journal per mission and only expose public request data."""
    evidence = {}
    for case in missions():
        with tempfile.TemporaryDirectory(prefix="controller-", dir=run.scratch) as location:
            directory = Path(location)
            directory.chmod(0o777)
            state = directory / "commands.json"

            def exchange(packet, *, lose_output=False):
                return run("dispatch", packet, state=state, lose_output=lose_output)

            evidence[case["id"]] = complete_mission(exchange, case)
    return evidence
