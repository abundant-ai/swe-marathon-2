"""Exercise deterministic criterion scoring and request-specific output validation."""

from __future__ import annotations

from dataclasses import replace
import tomllib

from task_paths import TASK_ROOT
from verifier.config import load_answer_scoring_config

import pytest
from pydantic import ValidationError

from verifier.contracts import HeldOutCase
from verifier.judging.answer_scoring import AnswerInputs, finalize_answer_judgment
from verifier.judging.schemas import AnswerRating, CriterionRating


POLICY = load_answer_scoring_config(tomllib.loads((TASK_ROOT / "task.toml").read_text())["verifier"]["env"])

def decision(index: int, status: str, quote: str = "", duplicate_of: int | None = None) -> CriterionRating:
    """Create a controlled assessment for pure arithmetic and validation tests.

    Args:
        index: Rubric position assessed by the provider double.
        status: Passed, failed, or not_applicable classification.
        quote: Exact synthetic candidate evidence, or empty for an omission.
        duplicate_of: Earlier failed criterion for an identical false assertion.

    Returns:
        Strict typed assessment; semantic correctness is not tested by this helper.
    """
    return CriterionRating.model_validate({"rubric_index": index, "status": status, "candidate_quote": quote,
                                           "duplicate_of": duplicate_of, "reason": "Controlled decision"})


def rubric_inputs(required_count: int, guard_count: int) -> AnswerInputs:
    """Build a trusted synthetic rule partition with exact available candidate text.

    Args:
        required_count: Number of substantive criteria in the denominator.
        guard_count: Conditional items scored when they apply.

    Returns:
        Immutable inputs used only by these pure scoring tests.
    """
    case = HeldOutCase("q", "Who approved, and when?", "Mira approved Friday.",
                       rubric=tuple(f'must establish "fact {i}".' for i in range(required_count + guard_count)),
                       required_rubric_indices=tuple(range(required_count)))
    return AnswerInputs(case, "Mira approved. Monday. Budget was seven.")


@pytest.mark.parametrize("optional_status,quote,expected", [
    ("passed", "Mira approved.", 100), ("not_applicable", "", 100), ("failed", "Monday.", 80),
])
def test_conditional_status_controls_its_component(optional_status: str, quote: str, expected: float) -> None:
    """Normalize applicable conditional claims and omit inapplicable ones.

    Args:
        optional_status: Provider classification for the optional condition.
        quote: Evidence required for present claims.
        expected: Percentage dictated by the requested denominator semantics.
    """
    result = finalize_answer_judgment(AnswerRating(criteria=[decision(0, "passed", "Mira approved."),
        decision(1, optional_status, quote)], unverified_claims=[]), rubric_inputs(1, 1), "response", POLICY)
    assert result.score == expected and result.required_count == 1
    assert result.violated_optional == (optional_status == "failed")


def test_all_optional_successes_cannot_rescue_a_missing_core() -> None:
    """Apply the zero-required-success gate despite correct conditional claims."""
    result = finalize_answer_judgment(AnswerRating(criteria=[decision(0, "failed"),
        decision(1, "passed", "Mira approved.")], unverified_claims=[]), rubric_inputs(1, 1), "", POLICY)
    assert result.score == 0 and result.verdict == "incorrect"


def test_unverified_extras_are_retained_without_a_factual_penalty() -> None:
    """Keep uncertainty distinct from demonstrated contradiction in audit records."""
    result = finalize_answer_judgment(AnswerRating(criteria=[decision(0, "passed", "Mira approved.")],
        unverified_claims=["Budget was seven."]), rubric_inputs(1, 0), "", POLICY)
    assert result.score == 100 and result.unverified_claims == ("Budget was seven.",)


def test_duplicate_error_metadata_does_not_remove_applicable_items() -> None:
    """Count every failed rubric item even when audit metadata groups an assertion."""
    result = finalize_answer_judgment(AnswerRating(criteria=[decision(0, "passed", "Mira approved."),
        decision(1, "failed", "Monday."), decision(2, "failed", "Monday.", 1),
        decision(3, "failed", "Budget was seven.")], unverified_claims=[]), rubric_inputs(1, 3), "", POLICY)
    assert result.violated_optional == 3 and result.score == 80
    assert result.conditional_count == 3 and result.conditional_fraction == 0


@pytest.mark.parametrize("required,passed", [(3, 2), (4, 3), (101, 75)])
def test_ratio_is_not_quantized_before_citation_gate(required: int, passed: int) -> None:
    """Preserve thirds and below-threshold fractions instead of rounding to bands.

    Args:
        required: Number of mandatory criteria.
        passed: Number satisfied by the controlled candidate.
    """
    rating = AnswerRating(criteria=[decision(i, "passed", "Mira approved.") if i < passed else decision(i, "failed")
                                    for i in range(required)], unverified_claims=[])
    result = finalize_answer_judgment(rating, rubric_inputs(required, 0), "", POLICY)
    assert result.score == pytest.approx(100 * passed / required)
    assert (result.score / 100 >= .75) == (passed / required >= .75)


@pytest.mark.parametrize("defect", ["missing", "duplicate", "unknown", "required_na", "invented_quote",
                                      "empty_pass", "empty_violation", "forward_duplicate", "duplicate_required",
                                      "different_claim_duplicate", "invented_unknown", "empty_core"])
def test_invalid_criterion_outputs_fail_closed(defect: str) -> None:
    """Reject structurally plausible outputs that do not match the current request.

    Args:
        defect: Specific identity, applicability, evidence, or deduplication violation.
    """
    inputs = rubric_inputs(1, 2)
    values = [decision(0, "passed", "Mira approved."), decision(1, "failed", "Monday."), decision(2, "not_applicable")]
    unknown: list[str] = []
    if defect == "missing":
        values.pop()
    elif defect == "duplicate":
        values[2] = values[1]
    elif defect == "unknown":
        values[2] = decision(99, "not_applicable")
    elif defect == "required_na":
        values[0] = decision(0, "not_applicable")
    elif defect == "invented_quote":
        values[0] = decision(0, "passed", "The reference says Mira")
    elif defect == "empty_pass":
        values[0] = decision(0, "passed")
    elif defect == "empty_violation":
        values[1] = decision(1, "failed")
    elif defect == "forward_duplicate":
        values[1] = decision(1, "failed", "Monday.", 2)
        values[2] = decision(2, "failed", "Monday.")
    elif defect == "duplicate_required":
        values[0] = decision(0, "failed", "Monday.", 1)
    elif defect == "different_claim_duplicate":
        values[2] = decision(2, "failed", "Budget was seven.", 1)
    elif defect == "invented_unknown":
        unknown = ["Never said this"]
    else:
        inputs = replace(inputs, case=replace(inputs.case, required_rubric_indices=()))
    with pytest.raises(ValueError):
        finalize_answer_judgment(AnswerRating(criteria=values, unverified_claims=unknown), inputs, "", POLICY)


def test_model_cannot_supply_its_own_aggregate_score() -> None:
    """Keep score selection outside model-controlled fields."""
    with pytest.raises(ValidationError):
        AnswerRating.model_validate({"criteria": [decision(0, "failed").model_dump()],
                                     "unverified_claims": [], "score": 1})


@pytest.mark.parametrize("required_passes,statuses,expected", [
    (2, ("passed", "passed"), 100),
    (2, ("passed", "failed"), 90),
    (2, ("failed", "failed"), 80),
    (1, ("passed", "passed"), 60),
    (0, ("passed", "passed"), 0),
    (1, ("not_applicable", "not_applicable"), 50),
    (2, ("passed", "not_applicable"), 100),
    (1, ("failed", "not_applicable"), 40),
])
def test_separately_normalized_components(required_passes: int, statuses: tuple[str, str], expected: float) -> None:
    """Cover the agreed component weighting, applicability, and zero-core rules.

    Args:
        required_passes: Number of successes among two required facts.
        statuses: Conditional decisions, including excluded absent claims.
        expected: Percentage under the deployed 80/20 criterion weights.
    """
    required = [decision(i, "passed", "Mira approved.") if i < required_passes else decision(i, "failed")
                for i in range(2)]
    conditional = [decision(i + 2, status, "" if status == "not_applicable" else "Monday.")
                   for i, status in enumerate(statuses)]
    result = finalize_answer_judgment(AnswerRating(criteria=required + conditional, unverified_claims=[]),
                                      rubric_inputs(2, 2), "", POLICY)
    assert result.score == pytest.approx(expected)
    assert result.required_fraction == required_passes / 2
    assert result.not_applicable_conditional == statuses.count("not_applicable")
    assert result.passed_conditional == statuses.count("passed")
    if all(status == "not_applicable" for status in statuses):
        assert result.conditional_fraction is None


def test_custom_environment_weights_change_answer_score() -> None:
    """Use deployment parsing to change actual arithmetic, without Python defaults."""
    policy = load_answer_scoring_config({"ORANGE_EVAL_REQUIRED_WEIGHT": "0.6",
                                        "ORANGE_EVAL_CONDITIONAL_WEIGHT": "0.4"})
    rating = AnswerRating(criteria=[decision(0, "passed", "Mira approved."), decision(1, "failed"),
                                   decision(2, "passed", "Monday.")], unverified_claims=[])
    result = finalize_answer_judgment(rating, rubric_inputs(2, 1), "", policy)
    assert result.score == pytest.approx(70)


@pytest.mark.parametrize("conditional_count", [1, 10, 100])
def test_conditional_count_does_not_change_group_weight(conditional_count: int) -> None:
    """Keep optional detail volume from outweighing required facts.

    Args:
        conditional_count: Number of satisfied conditions at the same fraction.
    """
    rating = AnswerRating(criteria=[decision(0, "passed", "Mira approved."), decision(1, "failed")] +
        [decision(i + 2, "passed", "Monday.") for i in range(conditional_count)], unverified_claims=[])
    result = finalize_answer_judgment(rating, rubric_inputs(2, conditional_count), "", POLICY)
    assert result.score == pytest.approx(60)
