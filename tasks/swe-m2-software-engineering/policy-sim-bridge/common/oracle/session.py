"""Timed observation history, neutral watchdog and paired trace diagnosis."""

from itertools import zip_longest
from typing import Iterator

from .model import Contract, Record, execute, frame, integer, mapping


def start(contract: Contract, origin: int = 0) -> Record:
    """Create a fresh active session at the provided clock origin."""
    width = len(contract.mean)
    return {"history": [[0.0] * width for _ in range(contract.history)],
            "last_action": [0.0] * len(contract.commanded), "control": contract.neutral.copy(),
            "origin": origin, "previous": None, "reply": None, "latched": False}


def result(status: str, control: list[float], observation: list[float] | None = None,
           action: list[float] | None = None, target: list[float] | None = None) -> Record:
    """Construct a bus and diagnostic response for one accepted or rejected event."""
    return {"status": status, "control": control, "observation": observation,
            "action": action, "target": target}


def decide(contract: Contract, state: Record, incoming: object) -> tuple[Record, Record, bool]:
    """Validate one packet and return the response and, if needed, the next state."""
    packet = mapping(incoming)
    tick = integer(packet["tick"], 0)
    kind = packet["kind"]
    if kind not in ("step", "arm"):
        raise ValueError("unknown packet kind")
    healthy = packet.get("healthy", True)
    if type(healthy) is not bool:
        raise ValueError("invalid health flag")
    current = frame(contract, packet, state["last_action"]) if kind == "step" and healthy else None
    previous = state["previous"]
    if previous is not None and tick <= previous["tick"]:
        if tick == previous["tick"] and packet == previous:
            return state["reply"], state, False
        return result("rejected", contract.neutral), state, False
    if kind == "arm":
        state = start(contract, tick)
        response = result("armed", contract.neutral)
    else:
        timed_out = (contract.watchdog is not None and previous is not None
                     and tick - previous["tick"] > contract.watchdog)
        if state["latched"] or timed_out or not healthy:
            state["latched"] = True
            state["control"] = contract.neutral
            response = result("latched", contract.neutral)
        elif (tick - state["origin"]) % contract.period == 0:
            stack = state["history"][1:] + [current]
            observation = [value for row in stack for value in row]
            action, target, control = execute(contract, observation)
            state.update(history=stack, last_action=action, control=control)
            response = result("updated", control, observation, action, target)
        else:
            response = result("held", state["control"])
    state.update(previous=packet, reply=response)
    return response, state, True


def updates(contract: Contract, packets: Iterator[object]) -> Iterator[tuple[int, Record]]:
    """Replay an independent stream, yielding only actual actor evaluations."""
    state = start(contract)
    for packet in packets:
        response, state, changed = decide(contract, state, packet)
        if changed and response["status"] == "updated":
            yield packet["tick"] * contract.dt, response


def first(left: list[tuple[int, Record]], right: list[tuple[int, Record]], eps: float) -> Record:
    """Find the earliest mismatch by policy time and named comparison stage."""
    compared = 0
    for a, b in zip_longest(left, right):
        ta = a[0] if a is not None else None
        tb = b[0] if b is not None else None
        if ta != tb:
            return mismatch(compared, "time_ns", None, ta, tb)
        for field in ("observation", "action", "target"):
            for channel, (x, y) in enumerate(zip_longest(a[1][field], b[1][field])):
                if x is None or y is None or abs(x - y) > eps:
                    return mismatch(compared, field, channel, x, y)
        compared += 1
    return {"status": "match", "compared": compared, "first": None}


def mismatch(index: int, field: str, channel: int | None, a: float | None, b: float | None) -> Record:
    """Return precise witness values for the first unmatched policy stage."""
    return {"status": "mismatch", "compared": index,
            "first": {"index": index, "field": field, "channel": channel, "left": a, "right": b}}
