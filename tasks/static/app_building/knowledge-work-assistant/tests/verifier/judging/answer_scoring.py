"""Validate criterion coverage and calculate factual correctness without rounding."""

from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pydantic_ai import ModelRetry, RunContext

from verifier.config import AnswerScoringConfig
from verifier.contracts import AnswerJudgment, CriterionAssessment, HeldOutCase
from verifier.judging.schemas import AnswerRating


@dataclass(frozen=True)
class AnswerInputs:
    """Immutable trusted question and candidate text for output validation."""

    case: HeldOutCase
    answer: str


def validate_answer_rating(rating: AnswerRating, inputs: AnswerInputs) -> AnswerRating:
    """Check the model's decisions against this request before computing credit.

    Used by the PydanticAI output validator and the final scoring adapter. This
    validates identities and evidence provenance; semantic decisions still need
    calibration against source-reviewed examples.

    Args:
        rating: Strict structured provider output.
        inputs: Trusted criterion partition and exact candidate answer.

    Returns:
        Unchanged output after every decision has been checked.

    Raises:
        ValueError: A point is missing, duplicated, inapplicable when required,
            supported by invented candidate text, or incorrectly deduplicated.
    """
    indices = [item.rubric_index for item in rating.criteria]
    if sorted(indices) != list(range(len(inputs.case.rubric))):
        raise ValueError("Assess every rubric index exactly once")
    required = set(inputs.case.required_rubric_indices)
    if not required or not required.issubset(indices):
        raise ValueError("Trusted rubric requires a nonempty valid mandatory core")
    by_index = {item.rubric_index: item for item in rating.criteria}
    for item in rating.criteria:
        mandatory = item.rubric_index in required
        if mandatory and item.status == "not_applicable":
            raise ValueError("A required point cannot be not_applicable")
        if item.candidate_quote and item.candidate_quote not in inputs.answer:
            raise ValueError(
                "Candidate evidence must be an exact excerpt from this answer"
            )
        if (
            item.status == "passed" or (item.status == "failed" and not mandatory)
        ) and not item.candidate_quote.strip():
            raise ValueError(
                "Passed points and optional violations need candidate evidence"
            )
        if item.duplicate_of is not None:
            earlier = by_index.get(item.duplicate_of)
            if (
                mandatory
                or item.status != "failed"
                or earlier is None
                or earlier.rubric_index >= item.rubric_index
                or earlier.status != "failed"
                or earlier.duplicate_of is not None
                or earlier.candidate_quote != item.candidate_quote
            ):
                raise ValueError(
                    "A duplicate must reference one earlier failed point for the same candidate excerpt"
                )
    if any(
        not claim.strip() or claim not in inputs.answer
        for claim in rating.unverified_claims
    ):
        raise ValueError("Unverified claims must quote the candidate exactly")
    return rating


def retry_invalid_answer(
    ctx: RunContext[AnswerInputs], rating: AnswerRating
) -> AnswerRating:
    """Request a bounded structured-output repair for request-specific violations.

    Registered on the answer agent; its configured retry budget applies to these
    failures as well as Pydantic schema failures.

    Args:
        ctx: Current immutable question and candidate dependencies.
        rating: Parsed provider output awaiting contextual validation.

    Returns:
        The validated output.

    Raises:
        ModelRetry: Coverage or evidence provenance needs repair.
    """
    try:
        return validate_answer_rating(rating, ctx.deps)
    except ValueError as error:
        raise ModelRetry(str(error)) from error


def finalize_answer_judgment(
    rating: AnswerRating,
    inputs: AnswerInputs,
    response_id: str,
    config: AnswerScoringConfig,
) -> AnswerJudgment:
    """Combine separately normalized required and applicable conditional scores.

    Used after output validation by live judges and calibration adapters. Zero
    required successes force zero credit. When no condition applies, use only
    the required fraction. Otherwise use the configured weighted mean. Every
    applicable rubric item counts, including items sharing a false assertion;
    duplicate references remain audit metadata. No rounding precedes the gate.

    Args:
        rating: Provider decisions with complete criterion coverage.
        inputs: Trusted criterion kinds and original candidate answer.
        response_id: Provider trace identifier retained for audit.
        config: Validated weights supplied by the trusted startup adapter.

    Returns:
        Percentage, derived verdict, immutable decisions, and exact count inputs.

    Raises:
        ValueError: Contextual validation fails.
    """
    validate_answer_rating(rating, inputs)
    required = set(inputs.case.required_rubric_indices)
    passed = sum(
        item.rubric_index in required and item.status == "passed"
        for item in rating.criteria
    )
    conditional = [
        item for item in rating.criteria if item.rubric_index not in required
    ]
    passed_conditional = sum(item.status == "passed" for item in conditional)
    applicable = sum(item.status != "not_applicable" for item in conditional)
    violated = sum(item.status == "failed" for item in conditional)
    required_fraction = passed / len(required)
    conditional_fraction = passed_conditional / applicable if applicable else None
    if passed == 0:
        fraction = 0.0
    elif conditional_fraction is None:
        fraction = required_fraction
    else:
        fraction = (
            config.required_weight * required_fraction
            + config.conditional_weight * conditional_fraction
        ) / (config.required_weight + config.conditional_weight)
    score = 100 * fraction
    verdict = "incorrect" if score == 0 else "correct" if score == 100 else "partial"
    reason = (
        f"{passed}/{len(required)} required points passed; "
        f"{passed_conditional}/{applicable} applicable conditional points passed."
    )
    assessments = tuple(
        CriterionAssessment(**item.model_dump())
        for item in sorted(rating.criteria, key=attrgetter("rubric_index"))
    )
    return AnswerJudgment(
        score=score,
        reason=reason,
        verdict=verdict,
        response_id=response_id,
        criteria=assessments,
        passed_required=passed,
        required_count=len(required),
        violated_optional=violated,
        unverified_claims=tuple(rating.unverified_claims),
        passed_conditional=passed_conditional,
        conditional_count=len(conditional),
        not_applicable_conditional=len(conditional) - applicable,
        required_fraction=required_fraction,
        conditional_fraction=conditional_fraction,
    )
