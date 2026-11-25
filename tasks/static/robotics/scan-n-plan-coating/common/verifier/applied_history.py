"""Track measured, disjoint half-open controller receipts by motion identity."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from trajectory import Knot, parse_knots


@dataclass(frozen=True)
class Motion:
    """Authority published before a controller accepted one motion."""

    command_id: str
    scene_revision: int
    issued_ns: int


@dataclass(frozen=True)
class Receipt:
    """All publicly reported samples for one measured half-open interval."""

    receipt_id: str
    command_id: str
    scene_revision: int
    samples: tuple[Knot, ...]

    @property
    def start_ns(self) -> int:
        """Return the first included sample time."""
        return self.samples[0].t_ns

    @property
    def end_ns(self) -> int:
        """Return the exclusive end time, with a sample for interpolation."""
        return self.samples[-1].t_ns


def parse_receipt(
    record: Mapping[str, Any], authority: Mapping[str, Motion], period_ns: int, max_flow_ml_s: float,
) -> Receipt:
    """Bind measured rows to the known command and registration generation.

    Args:
        record: Controller-provided interval in the published receipt format.
        authority: Trusted histories of issued motion IDs.
        period_ns: Control period from the job, in nanoseconds.
        max_flow_ml_s: Inclusive maximum material flow.

    Returns:
        Immutable interval ready for order-independent reconciliation.

    Raises:
        ValueError: Invalid identity, start, cadence, or material values.
    """
    if not isinstance(record, Mapping):
        raise ValueError("Receipt must be an object")
    receipt_id = record.get("receipt_id")
    command_id = record.get("command_id")
    revision = record.get("scene_revision")
    if (not isinstance(receipt_id, str) or not receipt_id or not isinstance(command_id, str)
            or command_id not in authority or type(revision) is not int):
        raise ValueError("Receipt has no valid motion identity")
    motion = authority[command_id]
    if revision != motion.scene_revision:
        raise ValueError("Receipt revision differs from issued motion")
    samples = parse_knots(record.get("samples"), period_ns, max_flow_ml_s, finish_disabled=False)
    if samples[0].t_ns < motion.issued_ns or (samples[0].t_ns - motion.issued_ns) % period_ns:
        raise ValueError("Receipt starts outside the motion clock")
    if any(right.t_ns - left.t_ns != period_ns for left, right in zip(samples, samples[1:])):
        raise ValueError("Receipt cannot interpolate over unobserved controller samples")
    return Receipt(receipt_id, command_id, revision, samples)


@dataclass(frozen=True)
class AppliedHistory:
    """An immutable collection of physical intervals, independent of delivery order."""

    receipts: tuple[Receipt, ...] = ()

    def extend(self, receipts: Iterable[Receipt]) -> "AppliedHistory":
        """Reconcile a batch atomically, preserving exact duplicates once.

        Raises:
            ValueError: One ID has conflicting content or distinct intervals
                overlap in the same issued motion.
        """
        known = {entry.receipt_id: entry for entry in self.receipts}
        for entry in receipts:
            previous = known.get(entry.receipt_id)
            if previous is not None and previous != entry:
                raise ValueError("Conflicting duplicate receipt identity")
            known[entry.receipt_id] = entry
        ordered = tuple(sorted(known.values(), key=lambda item: (item.command_id, item.start_ns)))
        for left, right in zip(ordered, ordered[1:]):
            if left.command_id == right.command_id and right.start_ns < left.end_ns:
                raise ValueError("Distinct measured intervals overlap")
        return AppliedHistory(ordered)

    def complete(self, motion: Motion, trace_through_ns: int) -> tuple[Receipt, ...] | None:
        """Return the physical prefix once every interval through the stop is known.

        Args:
            motion: Issued motion whose stopped trace is being reconciled.
            trace_through_ns: Last measured sample promised by the controller.

        Returns:
            Intervals in chronological order, or None if earlier material or
            the complete stated stop record is missing.
        """
        boundary = motion.issued_ns
        selected = []
        for receipt in self.receipts:
            if receipt.command_id != motion.command_id:
                continue
            if receipt.start_ns != boundary or receipt.end_ns > trace_through_ns:
                return None
            selected.append(receipt)
            boundary = receipt.end_ns
        return tuple(selected) if boundary == trace_through_ns else None
