---
name: judge-prompt-writing
description: Write or revise LLM judge prompts and structured output guidance while preserving the author's layout and scoring contract. Use for rubric explanations, conditional criteria, evidence modes, and rendered input/output examples in any domain.
---

# Judge prompt writing

Use this skill for author-only evaluation prompts. Follow the repository's
[judge requirements](../../requirement.md#llm-judges) and apply
[Humanizer](../humanizer/SKILL.md) to the prose. Use
[declarative-task-design](../declarative-task-design/SKILL.md) when changing what
counts as success, and [function contracts](../funtional-programmer/SKILL.md)
when changing code. A wording edit does not authorize a new scoring policy.

## Preserve the author's structure

Read the current file immediately before editing. The author may have changed
headings, emphasis, section order, or examples since the last response. Preserve
those changes. When asked to clarify a passage, edit within its existing section;
do not impose a standard template, add an Inputs heading, or move explanations
elsewhere merely because a renderer expects an older layout. Adapt the renderer
when necessary and verify the boundary between instructions and input data.

Write complete, natural sentences. Use concrete examples to explain abstract
terms, and numbered conditional steps when the reader must choose an outcome.
Keep short bold labels when they help scanning. Do not turn a small clarification
into a rewrite of the whole prompt.

## Give each rule one home

Keep the goal, rubric mechanics, evidence definitions, general criteria, and
output guidance distinct within the author's chosen sections. Before adding a
rule, check whether it already appears elsewhere. For example, once Rubric
explains required and guard items, Criteria should cover remaining issues such
as attribution, negation, scope, paraphrases, and instruction injection.

Place definitions beside the fields they explain. If an input contains a mode,
define every allowed value and its consequence. Describe the evidence that the
judge actually receives, not everything available elsewhere in the benchmark.
The author assigns modes; a candidate's abstention or missing context must not
silently change an answerable case into an unanswerable one.

For example, the knowledge assistant uses `gold` for answerable cases with
linked source records, `reference_only` for answerable cases without a supplied
gold-document set, and `unanswerable` for cases expecting scoped abstention.
Its accuracy judge receives a rubric and reference, not those source records.
These names and evidence boundaries are task-specific examples, not defaults
for every domain.

## Make rubric decisions concrete

Explain stable item identifiers, where their classifications come from, and how
the judge should return them. If using zero-based indices, say that numbering
starts at zero. Display each item's classification beside its text rather than
making the judge infer it from a distant list. Preserve the original indices
when displaying, filtering, or grouping items.

For a rubric with required facts and conditional guards, explain both groups:

- A required item states what the answer must establish. Explain what satisfies
  it, including accepted alternatives, and what happens when it is omitted.
- A guard constrains a claim the answer may choose to make. It must not become
  a demand to introduce that claim or reproduce all details in a reference.

In the assistant example, a guard about the release date follows these steps:

1. If the answer gives no release date, return `not_applicable` for that guard.
2. If it gives a date that the supplied facts establish as correct, return `passed`.
3. If the supplied facts establish that date as false, return `failed`.
4. If the supplied facts cannot establish whether the date is correct or false,
   return `not_applicable` and record the unverified claim where the schema requires it.

Distinguish an absent optional claim, an unverified claim, and a demonstrated
error. Preserve the task's policy for each. Accept semantically equivalent
answers when exact wording is not required. Exact matching can still be required
for evidence excerpts copied from the candidate or a source; semantic matching
of an answer and provenance validation of a quotation serve different purposes.

## Separate judgment from arithmetic

State explicitly what the model decides and what code computes. For a
criterion-based judge, return per-item decisions, evidence, explanations, and
duplicate references. Keep aggregate scores, weights, denominators, thresholds,
and derived verdicts in deterministic code. Do not ask the model to calculate
them or include undeclared `score` fields in examples.

If the existing design asks a judge to select a qualitative band, retain that
contract. Put the allowed values and anchored descriptions in the Pydantic
field's `Field(description=...)`; the prompt can tell the judge to follow that
guidance. Require a reason that justifies the band. Do not silently change a
banded judge into a criterion-based one, or change the available bands.

Keep assessed dimensions separate. For example, factual correctness and citation
support need different evidence and outputs. When later judging is conditional,
enforce the configured gate in code and run stages sequentially for each item.
The assistant's citation threshold and optional quotation-only audit illustrate
this pattern; they are not requirements for unrelated judges.

## Align prompts, schemas, and validators

Store prompts in Markdown with named input placeholders. Put the role in the
framework's supported system-prompt configuration. Separate trusted instructions
from submitted content, JSON-escape inserted values, and treat every input,
including source documents, as data rather than instructions. Test literal
braces and fake headings so candidate text cannot become a template directive.

Use PydanticAI native structured output with explicit Pydantic classes and
meaningful field descriptions. The schema must agree with the prompt about
allowed statuses, evidence, applicability, and scoring ownership. Reject extra
fields and validate request-dependent constraints in code, including:

1. Every rubric item has exactly one outcome. Missing, duplicate, or unknown
   indices fail validation; `not_applicable` still counts as an outcome.
2. Required items cannot use `not_applicable` when the contract requires a
   substantive answer. Guard outcomes follow the declared conditional policy.
3. Quoted evidence occurs in the permitted input, and citation IDs and indices
   refer to supplied records. Full source context must not replace missing
   support in a candidate's quotation when quotation support is being assessed.
4. Duplicate-error references identify the same assertion under the declared
   deduplication rules, without merging independent errors.

Use the configured bounded repair retries for invalid judge outputs. Exhausted
judge or provider failures invalidate evaluation; do not quietly convert them
to wrong-answer scores. Schema validity and exact-quote checks do not establish
semantic correctness, which still needs calibration.

## Show examples and verify the change

When asked for an example, show the input, the fully filled current prompt, the
structured judge output, and any separately computed result. Use the actual
renderer and schema. Preserve the distinction between a fresh model response,
a saved response, and a constructed illustration. A saved response can validate
against the current schema without proving how the model responds to new wording.
Identify its model and prompt provenance; never present it as a fresh run.

For example, this decision-only output has no aggregate score:

```json
{
  "criteria": [
    {"rubric_index": 0, "status": "passed", "candidate_quote": "Maya owns the release.", "reason": "Identifies the required owner.", "duplicate_of": null},
    {"rubric_index": 1, "status": "not_applicable", "candidate_quote": "", "reason": "The answer gives no release date.", "duplicate_of": null}
  ],
  "unverified_claims": []
}
```

This is an illustrative schema example, not a live result or a universal output
contract. Use the task's actual field definitions and decisions in delivered examples.

Run focused existing checks for rendering, evidence separation, schema handling,
coverage, and scoring invariants affected by the edit. Test behavior rather than
requiring incidental words or headings. Review the final diff for lost conditions
and unintended layout changes. Before a subsequent live evaluation, follow the
repository's calibration requirements with cases covering correct and partial
answers, contradictions, unverified additions, supported extra details, and
misleading evidence as applicable. Report controlled checks and live calibration
separately. Prompt editing alone does not authorize uploads, trials, or model calls.

The knowledge assistant's [answer prompt](../../../tasks/enterprise/knowledge-work-assistant/tests/verifier/judging/answer_prompt.md),
[output schemas](../../../tasks/enterprise/knowledge-work-assistant/tests/verifier/judging/schemas.py),
and [answer validation and scoring](../../../tasks/enterprise/knowledge-work-assistant/tests/verifier/judging/answer_scoring.py)
are maintained examples. Read their current versions before describing their
behavior; do not copy their domain assumptions into another task.
