"""Bounded information smoother with exact local Schur elimination."""

import json
from dataclasses import dataclass

import numpy as np

from .contract import (
    Array,
    Config,
    Event,
    Factor,
    Json,
    integer,
    load_factor,
    matrix,
    vector,
)


@dataclass(frozen=True)
class Revision:
    """Latest active revision, with no factor for a retraction tombstone."""

    event: Json
    factor: Factor | None

    def encoded(self) -> Json:
        """Encode sufficient revision and measurement data for the next process."""
        return {
            "event": self.event,
            "factor": self.factor.encoded() if self.factor is not None else None,
        }


def canonical(data: object) -> str:
    """Serialize JSON contents independently of object key order."""
    return json.dumps(data, sort_keys=True, allow_nan=False, separators=(",", ":"))


def add_factor(information: Array, eta: Array, factor: Factor, origin: int) -> None:
    """Accumulate the canonical Gaussian contribution in its tick block."""
    block = slice(2 * (factor.first - origin), 2 * (factor.last + 1 - origin))
    whitened = np.linalg.solve(factor.noise, factor.design)
    information[block, block] += factor.design.T @ whitened
    eta[block] += whitened.T @ factor.value


class Smoother:
    """Track active factors and a canonical prior summarizing every expired tick."""

    def __init__(self, config: Config, stored: Json | None = None) -> None:
        """Start from a new survey prior or restore an accepted bounded state."""
        self.config = config
        self.process_precision = np.linalg.inv(config.process)
        self.first = self.watermark = config.start
        self.precision = np.linalg.inv(config.prior)
        self.eta = self.precision @ config.mean
        self.factors: list[Factor] = []
        self.revisions: dict[tuple[int, int, str], Revision] = {}
        if stored is not None:
            self.watermark = integer(stored["watermark"], config.start)
            self.first = max(config.start, self.watermark - config.lag)
            self.precision = matrix(stored["precision"], 2, 2)
            self.eta = vector(stored["eta"])
            self.factors = [load_factor(row) for row in stored["factors"]]
            for row in stored["revisions"]:
                event = row["event"]
                key = revision_key(event)
                factor = (
                    load_factor(row["factor"]) if row["factor"] is not None else None
                )
                self.revisions[key] = Revision(event, factor)

    def encoded(self) -> Json:
        """Serialize only the summarized prior and bounded active graph."""
        return {
            "watermark": self.watermark,
            "precision": self.precision.tolist(),
            "eta": self.eta.tolist(),
            "factors": [factor.encoded() for factor in self.factors],
            "revisions": [revision.encoded() for revision in self.revisions.values()],
        }

    def support(self, first: int, last: int) -> str | None:
        """Give expired precedence over future for observations outside the live graph."""
        if first < self.first:
            return "expired"
        if last > self.watermark:
            return "future"
        return None

    def advance(self, tick: int, initial: int) -> None:
        """Advance within this request's budget and summarize the expelled prefix."""
        if tick <= self.watermark or tick - initial > 4096:
            raise ValueError("advance must be increasing and within 4096 ticks")
        self.watermark = tick
        target = max(self.config.start, tick - self.config.lag)
        while self.first < target:
            self.marginalize_first()

    def marginalize_first(self) -> None:
        """Eliminate the oldest pose, updating only its neighbour's boundary message."""
        Q = self.process_precision
        local = np.block([[self.precision + Q, -Q], [-Q, Q.copy()]])
        moments = np.concatenate((self.eta, np.zeros(2)))
        kept = []
        for factor in self.factors:
            if factor.first == self.first:
                add_factor(local, moments, factor, self.first)
            else:
                kept.append(factor)
        self.factors = kept
        for key in list(self.revisions):
            if key[0] == self.first:
                revision = self.revisions.pop(key)
                if revision.factor is not None:
                    add_factor(local, moments, revision.factor, self.first)
        cross = local[:2, 2:]
        solved = np.linalg.solve(local[:2, :2], np.column_stack((cross, moments[:2])))
        self.precision = local[2:, 2:] - cross.T @ solved[:, :2]
        self.precision = (self.precision + self.precision.T) / 2
        self.eta = moments[2:] - cross.T @ solved[:, 2]
        self.first += 1

    def snapshot(self) -> Json:
        """Compute the full retained pose marginals without modifying graph state."""
        size = (self.watermark - self.first + 1) * 2
        information = np.zeros((size, size))
        moments = np.zeros(size)
        information[:2, :2] = self.precision
        moments[:2] = self.eta
        Q = self.process_precision
        for i in range(0, size - 2, 2):
            a, b = slice(i, i + 2), slice(i + 2, i + 4)
            information[a, a] += Q
            information[b, b] += Q
            information[a, b] -= Q
            information[b, a] -= Q
        for factor in self.factors:
            add_factor(information, moments, factor, self.first)
        for revision in self.revisions.values():
            if revision.factor is not None:
                add_factor(information, moments, revision.factor, self.first)
        mean = np.linalg.solve(information, moments)
        covariance = np.linalg.inv(information)
        states = []
        for offset in range(0, size, 2):
            block = slice(offset, offset + 2)
            states.append(
                {
                    "tick": self.first + offset // 2,
                    "mean": mean[block].tolist(),
                    "covariance": covariance[block, block].tolist(),
                }
            )
        return {"watermark": self.watermark, "states": states}

    def revise(self, event: Event) -> str:
        """Apply a conditional upsert or retraction to a retained factor identity."""
        data = event.data
        key = revision_key(data)
        support = self.support(*key[:2])
        if support is not None:
            return support
        prior = self.revisions.get(key)
        revision = data["revision"]
        if prior is not None:
            last = prior.event["revision"]
            if revision < last:
                return "stale"
            if revision == last:
                return (
                    "duplicate"
                    if canonical(data) == canonical(prior.event)
                    else "conflict"
                )
        else:
            last = 0
        if revision != last + 1:
            return "conflict"
        if event.op == "retract":
            if prior is None or prior.factor is None:
                return "conflict"
            self.revisions[key] = Revision(data, None)
            return "retracted"
        factor = event.observation.factor
        if factor is None:
            return "invalid"
        self.revisions[key] = Revision(data, factor)
        return "accepted"

    def execute(self, events: list[Event]) -> Json:
        """Execute a parsed array, returning outcomes and posterior snapshots."""
        starting_tick = self.watermark
        outcomes = []
        snapshots = []
        for event in events:
            if event.op == "advance":
                self.advance(event.data["tick"], starting_tick)
                status = "advanced"
            elif event.op == "snapshot":
                snapshots.append({"label": event.data["label"], **self.snapshot()})
                status = "snapshot"
            elif event.op in ("upsert", "retract"):
                status = self.revise(event)
            else:
                obs = event.observation
                status = self.support(obs.first, obs.last)
                if status is None:
                    if obs.factor is None:
                        status = "invalid"
                    else:
                        self.factors.append(obs.factor)
                        status = "accepted"
            outcomes.append({"status": status})
        return {"outcomes": outcomes, "snapshots": snapshots, "final": self.snapshot()}


def revision_key(event: Json) -> tuple[int, int, str]:
    """Return the acquisition extent and producer key for a revision."""
    return event["first_tick"], event["last_tick"], event["id"]
