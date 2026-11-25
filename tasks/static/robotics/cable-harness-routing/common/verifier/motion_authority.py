"""Trusted command receipts for one live harness workcell."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Literal

from harness_contract import MotionLimits, ObservationRef, Response, identifier, integer, parse_response

ReceiptStatus = Literal["applied", "interrupted", "rejected"]


@dataclass(frozen=True)
class Receipt:
    """Outcome reported by the plant, including the generation that authorized it."""

    command_id: str
    generation: int
    status: ReceiptStatus


@dataclass
class _IssuedMotion:
    """Original motion authority and its outcome, once the actuator returns."""

    response: Response
    observation: ObservationRef
    limits: MotionLimits
    receipt: Receipt | None = None


class MotionAuthority:
    """Own command authority while a controller process starts and stops.

    The trusted workcell processes a serial stream and stays alive across
    controller restarts. Its executor advances the physical plant and can
    stop before the requested motion ends. Only this ledger issues receipts.
    """

    def __init__(self, observation: ObservationRef, limits: MotionLimits) -> None:
        """Start with the plant's first observed state and active recipe limits."""
        self._observation = observation
        self._limits = limits
        self._issued: dict[str, _IssuedMotion] = {}
        self._used_observations: set[str] = set()
        self._last_receipt: Receipt | None = None

    @property
    def last_receipt(self) -> Receipt | None:
        """Return the last physical outcome to include in an observation.

        A revised board may carry a receipt from the previous generation.
        """
        return self._last_receipt

    def publish(self, observation: ObservationRef, limits: MotionLimits) -> None:
        """Install trusted authority for a new capture and its recipe limits.

        Call this with newly acquired plant state. Replaying an old packet to
        the controller does not change the plant's current authority. A newer
        generation retires prior observation authority and retains command IDs.
        Regressions raise ValueError.
        """
        if observation.generation < self._observation.generation:
            raise ValueError("Board generation cannot move backwards")
        if observation.generation > self._observation.generation:
            self._used_observations.clear()
        self._observation = observation
        self._limits = limits

    def _retry(self, raw: Mapping[str, object], issued: _IssuedMotion) -> Receipt:
        """Return a prior result for an unchanged action on a valid retry envelope.

        Validate the action against its original point detections and bounds.
        A new camera observation may no longer contain the acquired point.
        """
        observation_id = identifier(raw.get("observation_id"), "observation_id")
        if observation_id not in (issued.observation.observation_id, self._observation.observation_id):
            raise ValueError("A retry must refer to its original or the current observation")
        observed = replace(issued.observation, observation_id=observation_id)
        response = parse_response(raw, observed, issued.limits)
        if response.action != issued.response.action or response.status != issued.response.status:
            raise ValueError("Command ID was reused with a different decision")
        if issued.receipt is None:
            raise RuntimeError("The original motion outcome is unknown")
        return issued.receipt

    def submit(self, raw: object, execute: Callable[[Response], ReceiptStatus]) -> Receipt:
        """Apply one current decision or return the outcome of its exact retry.

        Args:
            raw: Untrusted decoded JSON response with observation and command IDs.
            execute: Trusted actuator callback. It returns only after it has
                applied, interrupted or rejected the decision.

        Returns:
            Plant receipt. Retries return the same receipt without motion.

        Raises:
            ValueError: Malformed input, stale authority or conflicting reuse.
            RuntimeError: An issued motion has no known outcome, including an
                executor failure that could have partially moved the plant.
                Such failures invalidate the run. Retrying never applies it again.
        """
        if not isinstance(raw, Mapping):
            raise ValueError("Response must be an object")
        generation = integer(raw.get("generation"), "generation")
        if generation != self._observation.generation:
            raise ValueError("Response does not belong to the current board generation")
        identity = identifier(raw.get("command_id"), "command_id")
        existing = self._issued.get(identity)
        if existing is not None:
            if existing.response.generation != generation:
                raise ValueError("Command ID belongs to an earlier board generation")
            return self._retry(raw, existing)

        response = parse_response(raw, self._observation, self._limits)
        if response.observation_id in self._used_observations:
            raise ValueError("The observation already authorized a decision")
        issued = _IssuedMotion(response, self._observation, self._limits)
        self._issued[identity] = issued
        self._used_observations.add(response.observation_id)

        try:
            status = execute(response)
        except Exception as error:
            raise RuntimeError("The actuator failed after accepting the motion") from error
        if status not in ("applied", "interrupted", "rejected"):
            raise RuntimeError("The actuator returned an invalid motion outcome")
        issued.receipt = Receipt(identity, generation, status)
        self._last_receipt = issued.receipt
        return issued.receipt
