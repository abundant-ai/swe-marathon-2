# Knowledge work assistant

Orange answers questions about a fictional software company's documents,
conversations, project history, and directory records. The task asks a coding
agent to build the assistant and improve it over successive steps.

## Development log

### 2026-11-19 — platform credentials and parallel calibration/trial launches

Added an explicit `[solution.env]` mapping from Oddish's `${OPENAI_API_KEY}`
to `ORANGE_OPENAI_API_KEY`. The oracle's inner assistant already reads that
alias from the public resource manifest; development and separate verification
use the same mapping. No personal provider key was uploaded. The local oracle
HTTP fixture now rejects the wrong bearer token and supplies a conflicting
harness key, so a successful generation checks which credential was selected.
All 13 focused packaging and oracle checks passed.

At the author's request, submitted calibration and the model trial in parallel,
without waiting for calibration acceptance. Both packages passed Oddish
preflight with no findings. The [Sol High calibration](https://www.oddish.app/orgs/abundant/experiments/3aef76c8)
replays the same 400 answer examples and 72 citation examples from the earlier
expanded answer calibration and citation ablation. It uses direct PydanticAI
Responses calls, ten concurrent requests, and platform credentials. The job
saves raw decisions, deterministic scores, answer confusion matrices, gate
changes, and citation agreement in `comparison.json` and `results.json`.
Citation calibration is independent of the answer gate. Historical labels stay
fixed; the previous GPT-6 Astra High runs used a different transport, so this
comparison cannot isolate model choice from transport. Logfire export remains
unconfigured; provider response IDs are retained.

The [Opus 5.5 Max trial](https://www.oddish.app/orgs/abundant/experiments/cb2ce1eb)
uses new task version 8, Claude Code, one rollout, and no oracle run. The runtime
content hash is `bc0f9d0c3c9e2464436951ba1198e3c928572c40b9d7ef97041ec2cb4e309fc6`.
Launch receipts and immutable input hashes are under
`experiment/oddish-sol-opus-20261119/`. Both jobs were submitted successfully;
results were pending when monitoring stopped as requested. Oddish also queued
its automatic description and audit jobs for the calibration task.

### 2026-11-19 — Sol High through direct API calls

Both judges now use `gpt-6.1-sol` with high reasoning through PydanticAI's
Responses API client and strict Pydantic outputs. Each judgment makes one model
call when the response is valid; the existing bounded output-repair retries
remain. Citation judging still runs conditionally after answer judging, with
one full-context citation judge and programmatic scoring.

The task uses Oddish's supported `${OPENAI_API_KEY}` credential source, mapped
to `ORANGE_OPENAI_API_KEY` for the application and `ORANGE_JUDGE_API_KEY` for
the verifier. The judge alias is absent from the candidate environment. The
live Oddish catalog lists `openai/gpt-6.1-sol` as a healthy platform model.

The factual-rubric calibration launcher now uses the production API client.
Its retired Codex judge adapter is preserved only in ignored experiment
artifacts. No coding-agent harness runs either judge. The launcher imports
successfully and exposes its calibration options. All 113 focused judge,
credential, packaging, and scoring-configuration checks passed locally using
controlled provider responses where needed. Live Sol calibration and
trace validation remain pending; the earlier Terra smoke test below does not
validate the changed model. This change has not been uploaded to Oddish.

### 2026-11-19 — Terra smoke test with Oddish platform credentials

Confirmed `openai/gpt-6.1-terra` in Oddish's live platform model catalog, then
called `gpt-6.1-terra` with high reasoning from a fresh, separate verifier
container. Oddish resolved `${OPENAI_API_KEY}` into `ORANGE_JUDGE_API_KEY`.
The submission used only the existing Oddish workspace token; no personal
provider key, provider-key override, or local `.env` was uploaded.

The current verifier snapshot passed all five synthetic cases: correct,
incorrect, half-correct, exactly 0.75, and a correct answer with an irrelevant
quotation. The answer and citation outputs passed their strict Pydantic schemas.
Citation evaluation ran at 0.75 and skipped the incorrect and 0.5 answers.
The judge pipeline took 10.85 seconds; Oddish recorded 64.65 seconds for the
verifier phase, including setup. Network access was restricted to `api.openai.com`.

The [completed diagnostic run](https://www.oddish.app/orgs/abundant/experiments/f70145cf?task=swe-m2_ai-engineering_terra-judge-smoke-20261119-7085ae22)
is task version 2, trial suffix `-4`. An earlier snapshot also passed; the test
was repeated after the quotation-only judge was removed. Automatically queued
description and audit jobs were cancelled. The benchmark task was not uploaded
or rerun. [Local evidence](experiment/oddish-terra-platform-smoke-20261119/summary.json)
includes the checked cases, timing, credential source, and source-snapshot check.
This establishes live platform access and smoke behavior, not full private-set
calibration or Logfire trace validation.

### 2026-11-19 — removed the quotation-only citation judge

Removed the second citation agent from the synchronous and asynchronous verifier
paths and the author calibration adapter. A full-context judge now returns claim
decisions, which go directly through evidence validation and deterministic
scoring. The 0/0.5/1 rules, answer eligibility gate, provenance checks, and bounded
output-repair retries are unchanged. The full-context prompt is unchanged from
the measured one-judge arm of the broader comparison.

Removed the retired agent's prompt, helper module, replay launcher, and dedicated
tests from the active task. Preserved their snapshots under ignored experiment
artifacts. Reports identify the single-judge policy and no longer advertise
quotation-judge roles or hashes. Historical comparison reports remain intact.
Updated current documentation and added regression coverage for one successful
citation call in the sync, async, and calibration paths, plus report metadata.

The focused judge, citation-scoring, reward, and concurrency run passed 121 tests.
The subsequent judge, reporting-policy, and packaging run passed 114 tests;
these runs overlap and are not 235 distinct tests. `git diff --check` passed.
No additional live calibration, task upload, or production rollout was run.

### 2026-11-19 — broader one-judge versus two-judge comparison

Compared 72 cases across 12 private questions and domains: 60 authored citation
controls and 12 unchanged saved oracle answers. A separate blind source review
froze labels before judging. Both review and tested judges used GPT-6 Astra High,
so the labels are model-assisted rather than human-certified. The paired scores
share the same context judgment; only the quotation audit differs. No answer
gate ran. Prompt, schema, scorer snapshots, labels, inputs, and raw outputs are
retained in the [ablation report](experiment/citation-ablation-2026-11-19/report.md).

One judge matched 60/72 frozen bands; two matched 58/72. Excluding eight cases
flagged ambiguous before evaluation, agreement was 57/64 versus 55/64. The audit
added 52 calls and rejected four claims in two cases. One downgrade lost valid
product context supplied by the original record; the other exposed a policy
boundary about interpreting an imperative PR summary using its unquoted merged
status. No changed score resolved a disagreement with the frozen labels.
Inspection also found three reference labels that awarded partial credit despite
their explanations finding no supported claims. The frozen labels remain intact;
these figures measure review agreement, not validated judge accuracy.

All 72 cases completed without output repairs or provider errors. Median added
audit latency was 7.4 seconds; mean additional sequential time across all cases
was 5.9 seconds in the temporary Codex transport. This sample does not demonstrate
a benefit from a mandatory second judge. Recommend a single full-context judge
with deterministic scoring as the default, subject to independent label review
and a clearer policy on contextual support. Production configuration is unchanged;
Terra generalization and human-reviewed calibration remain unvalidated.

### 2026-11-19 — decision-only citation judges and deterministic scoring

Removed the citation judge's numerical score from its strict Pydantic schema and
prompt. Both judges now return evidence decisions only. Python assigns zero when
no claim is supported or a central claim is contradicted, 0.5 for mixed support,
and 1 when all material claims are supported. The old proposed-score field is
removed from citation diagnostics. The quotation audit still only downgrades
support, and invalid evidence or failed judge calls still invalidate evaluation.

Reran the same nine private examples three times using GPT-6 Astra High: 27
context judgments and 24 quotation audits, with no errors or output repairs.
All 27 computed scores matched expectations and the preceding updated-prompt
run. Irrelevant quotations scored zero in all three repetitions, supported
extras scored one, and unverified extras scored 0.5. The audit changed no claim
labels in this sample. Saved raw context outputs, raw quotation outputs, and
computed scores separately in the
[calibration report](experiment/citation-decisions-2026-11-19/report.md).
These repeated development controls do not establish general reliability or
validate production Terra. The focused judge, citation, reward, and concurrency
checks passed (129 tests). A full-suite attempt encountered an unrelated missing
`make_review_report` import in `test_factual_rubrics.py`; that module is unchanged.
Excluding that module, all 387 remaining author tests passed in 5 minutes 29
seconds. These counts overlap; the focused tests are part of the broader suite.

### 2026-11-19 — minimal citation prompt change and live raw-score comparison

Added two sentences to Quotation relevance requiring support from the actual
quoted text and zero credit when no material claim is supported. Preserved the
rest of the prompt and scoring contract. Ran 54 fresh GPT-6 Astra High calls on
the same nine examples, three repetitions per prompt version, using identical
historical evidence messages. The matched before arm uses the current layout
without the added sentences. No answer gate, quotation audit, or programmatic
score adjustment ran in either arm.

Raw scoring-band agreement improved from 26/27 (96.30%) to 27/27 (100%). The
irrelevant quotation scored `[0, 0.5, 0]` before and `[0, 0, 0]` after. Supported
extras remained `[1, 1, 1]`; unverified extras remained `[0.5, 0.5, 0.5]`.
All calls completed without errors or output repairs. These development controls
cover only two questions and one distinct zero-support example, so the result
does not establish a general error rate or validate production Terra. Retained
the production audit and zero-support rule. All 101 focused tests passed after
normalizing whitespace in one existing prompt-text assertion. See the
[paired comparison](experiment/citation-prompt-update-2026-11-19/report.md).

### 2026-11-19 — measured saved citation-judge controls

Reanalyzed the dedicated GPT-6 Astra High citation controls, excluding every
case where citation judging was skipped. The 27 actual judgments cover nine
distinct examples from two private questions, repeated three times. Raw band
agreement was 25/27 (92.59%); the quotation audit and deterministic enforcement
raised final agreement to 27/27. Both raw errors awarded partial credit to an
irrelevant quotation. One needed the quotation audit to reject support; the
other already marked the claim unverified but proposed an inconsistent score.

For detecting any citation support, raw TP/TN/FP/FN were 24/1/2/0 and final
counts were 24/3/0/0. Separate quotation-only controls scored 21/21 across seven
examples (TP=9, TN=12). Labels are source-reviewed author expectations, not
human-certified. These development controls and repeated examples do not
establish a general error rate. No new model calls were made, and the current
prompt differs from the saved version. See the reproducible
[analysis](experiment/citation-performance-2026-11-19/report.md) for exclusions,
raw/final confusion matrices, timing, and provenance. Current-prompt and
production-model citation calibration remain pending.

### 2026-11-19 — citation prompt layout aligned with the answer prompt

Reorganized the citation prompt into Evaluation Guideline, Rubric, and Criteria,
followed by separated Questions, Citations, Original documents, and Candidate
answer sections. The Rubric section explains central/secondary claims and uses
numbered conditions for supported, contradicted, and unverified decisions.
Preserved the scoring bands, Pydantic output contract, evidence boundaries, and
quotation-only follow-up. The existing renderer accepts the Questions boundary.

All 101 focused judge, citation-claim, and quotation checks passed. The wording
and layout change has not received a new live citation calibration.
The claim-extraction paragraph was subsequently clarified with a release-owner
and release-date example to explain central versus secondary claims. This prose
edit preserves the contract; the final diff was checked for formatting errors.
The importance labels now use numbered conditions, and a separate Scoring
section groups band selection, the zero-support rule, the uncertainty tie-break,
and the explanation requirement into numbered steps.
Renamed the citation Criteria section to `watch out` and added short bold titles
to its bullets for scanning. This formatting edit passed `git diff --check`.

### 2026-11-19 — expanded answer-only judge calibration

Created 400 distinct answer controls across 100 private questions and all 26
product domains, excluding the five questions in the earlier control set.
Each question has a minimal correct paraphrase, an answer with supported optional
detail, a wrong-core answer, and a correct-core answer with a false conditional
claim. A separate source-aware review labeled all rubric items without seeing
author intentions. All expected labels were frozen before the evaluated judge
ran; their hashes and unchanged contents were verified afterward.

Authoring, blind label review, and answer judging used separate GPT-6 Astra High
Codex calls: 100 author calls, 100 review calls, and 400 answer judgments. All
completed; one invalid duplicate-error reference was repaired. No citations,
numeric answer scores, or reward thresholds enter the classification metrics.
An acceptable answer has no failed rubric items; a defective answer has at least
one. Against the frozen model-assisted labels, TP=200, TN=200, FP=0, FN=0.

Per-item status agreement is 2,483/2,520 (98.53%). Required items agree in 400/400
cases; conditional items agree in 2,083/2,120 (98.25%). The 37 conditional
disagreements span 34 answers: 12 expected passes became inapplicable, 16 expected
inapplicable items passed, four expected failures became inapplicable, and five
expected inapplicable items failed. The four missed expected failures occur in
answers whose required core already failed, so they do not alter the answer-level
confusion matrix. Some disagreements concern broad versus narrow guard triggers
or source facts less explicit in the evaluated judge's rubric/reference context.

Seven examples carried reviewer ambiguity notes before judging. Keeping them in
the full matrix gives the counts above; the unflagged subset has TP=199, TN=194,
FP=0, FN=0. Labels are not human-certified, and all stages share a model family.
These synthetic controls establish observed agreement, not a production error
rate or perfect rubric-item judgment. No production Terra calibration or Logfire
validation was performed. See the
[full report](experiment/expanded-answer-calibration-2026-11-19/report.md) and
[item disagreements](experiment/expanded-answer-calibration-2026-11-19/disagreements.json).

### 2026-11-19 — weighted-score calibration on matched private examples

Replayed the 530 selected decisions from the previous calibration and then made
530 fresh answer-judge calls on exactly the same inputs, using the same temporary
Codex GPT-6 Astra High adapter with ten concurrent requests. All calls completed
without output repairs. Inputs, rubric hashes, current prompt/schema hashes,
weights, and individual calls are retained in the
[comparison report](experiment/weighted-answer-calibration-2026-11-19/report.md).

For one oracle answer per private question (218 total), the old mean was 77.02%.
Rescoring fixed decisions gives 83.52%; fresh judgments with the new formula give
83.48%. Citation-score eligibility rises from 156 to 186 questions in both new
comparisons: 30 gained eligibility, none lost it. All 218 oracle answers passed
the exact-quotation prerequisite. Three fresh judgments changed conditional
items from passed to inapplicable, slightly changing scores but no gate outcomes.

All 232 reviewed-reference repetitions retained full credit. Supported-extra
controls retained full credit; wrong-core, false-abstention, injection, topic-only,
and unretracted-contradiction controls remained zero. Four false-conditional
control groups now pass the citation gate at 80–96%, as intended by the 20%
conditional-weight ceiling. Every current question has one required item, so
passing that item alone suffices to clear the 75% score gate under this policy.

This is answer calibration and a matched formula comparison, not an improvement
to the saved application. Citation judgments were not rerun; passing their gate
does not establish citation quality or a new total reward. Production Terra High
calibration and Logfire validation remain pending. No Oddish trial, deployment,
or commit was performed.

### 2026-11-19 — separately weighted answer components

Replaced the required-plus-violations ratio with separately normalized required
and applicable conditional scores. The verifier environment supplies their
80/20 weights. Zero required successes force zero answer credit; with no
applicable conditions, the required score receives the full weight. Conditional
items count individually, with duplicate-error links retained only for auditing.
The answer judge still emits decisions rather than a numerical score.

Updated the synchronous and asynchronous judge adapters, calibration callers,
per-question diagnostics, and report policy. Prior calibration scores used the
older formula and are not evidence for this policy. Live recalibration remains
pending; no remote trial or container rebuild was requested.

Validation passed: 166 focused scoring, judge, reward, and concurrency checks;
a subsequent 90-check run covered both updated judge adapters, packaging, and
rubric finalization. The runs overlap in judge tests. Repository source checks
and `git diff --check` also passed. Custom-weight checks confirm that changing
the environment policy changes the computed answer score.

### 2026-11-19 — simplified criteria and judge-writing skill

Simplified the accuracy judge's Criteria section by removing rubric mechanics
already explained above it. Preserved the author's headings, section order,
emphasis, and conditional guard rules. Scoring and output schemas are unchanged.
Added the repository's `judge-prompt-writing` skill and registered it in
`resources/requirement.md`, using this task as an example of general guidance.

All 85 focused judge and answer-criteria tests passed, along with skill validation
and repository checks. Removed a test assertion tied to incidental wording;
structured-output and scoring checks remain. No live recalibration or deployment
was performed for this prose change.

### 2026-11-19 — decision-only accuracy output example

Clarified in the hand-edited prompt and Pydantic field guidance that the answer
judge returns per-item decisions without a numerical score or overall verdict.
Preserved the prompt's sections and kept score computation in Python. All 63
controlled judge tests passed. Rendered FlowForce:content:12 into local example
artifacts and validated its saved calibration response against the current
schema and scoring function: 100%, correct. That response came from an earlier
GPT-6 Astra High calibration, not a new call with this prompt wording. The
example artifacts record that provenance explicitly.

### 2026-11-19 — guard decision cases

Replaced the guard explanation's prose block with four numbered conditional
cases: absent, established correct, established false, and uncheckable. Kept
the scoring explanation immediately below them and preserved the surrounding
sections. This is a wording and formatting change; scoring is unchanged.

### 2026-11-19 — conditional guard explanation

Clarified within the existing Rubric paragraph that a guard applies only when
the candidate makes the claim covered by its condition. The release-date example
now distinguishes an absent claim, a correct claim, a demonstrably false claim,
and a claim that cannot be verified. Headings, section order, and scoring are
unchanged. Reviewed the wording and checked the diff for formatting errors.

### 2026-11-19 — preserve the author's judge layout

Restored the author's answer-prompt headings, separators, and section order.
The rubric explanation stays in its Rubric section, and the evidence-mode
definitions stay in Evidence mode. Updated the renderer to accept the Questions
boundary instead of imposing an Inputs heading. Required/guard labels remain
beside individual rules; separate index-list sections were removed. All 63
controlled judge tests passed. This supersedes the layout restoration described
in the preceding edit; scoring remains unchanged.

### 2026-11-19 — rubric and evidence-mode explanations

Rewrote the answer prompt's rubric explanation as complete sentences with a
release-owner example for required facts and a release-date example for guards.
Defined `gold`, `reference_only`, and `unanswerable` beside the evidence-mode
input, including how to handle abstention and the absence of source documents.
Restored the renderer's Inputs boundary and required/guard placeholders after
the layout edit. All 63 controlled judge tests passed. Scoring and output schemas
are unchanged; no live recalibration was run.

### 2026-11-19 — explicit rubric group labels

The answer judge now receives each rubric item with its original zero-based
index and a `(required indices)` or `(guard indices)` label. The prompt explains
both groups, their allowed decisions, and how they affect scoring. Both index
lists are included explicitly; guards are derived from the validated required
indices without changing stored rubrics or the score calculation.

All 63 controlled judge tests passed, including a required item between two
guards, synchronous and asynchronous request rendering, and exclusion of source
documents from answer judging. No live recalibration or deployment was run.

### 2026-11-19 — Codex rubric review and criterion-based judging

Installed source-reviewed rubrics for all 218 active questions: one mandatory
factual point per question and 1,144 optional factual constraints. Every rule
starts with `must ` and has an exact source anchor. Original questions, gold
answers, corpus records, and the development sample are preserved; the judge
receives a separately reviewed example answer. The author review records source
conflicts and qualifications rather than silently rewriting the original gold.

Accuracy is now computed from structured decisions as passed mandatory points
divided by mandatory points plus distinct false optional claims. Correct, absent,
and unverified optional claims add nothing to either count. The model cannot
choose the aggregate accuracy score. A direct answer retains the question's
role, project, and time scope unless it explicitly separates a broader discussion.
Each distinct attribution error has its own criterion.

The temporary live judge is **Codex CLI, GPT-6 Astra High**, using the production
prompts and Pydantic schemas with tools disabled. This follows the user's explicit
provider substitution after the API account exhausted its credit. The runtime
Terra High configuration is unchanged. Calibration replays saved oracle answers
from trial `swe-m2_ai-engineering_knowledge-work-assistant-727a668e-15`, reached
through experiment `6d33bbbd`; all 218 active IDs and questions match. It does not
regenerate answers or constitute a new container or Oddish trial.

Both independent rubric review and a separate full-source audit covered all 218
questions. The latter revised 91 rubrics. Review and calibration exposed wrong
project and author attributions, chronology errors, accidental completeness
requirements, and ambiguous exclusivity checks. Some source-audit labels were
also corrected after inspecting the evidence. These are model-assisted labels,
not human-certified gold. One audit needed only conditional-clause reordering to
meet the literal `must ` prefix; its original model output is retained.

Citation output now includes an exact evidence excerpt. A supported claim must
point inside the candidate's quotation, even when the complete original document
contains additional useful text. Invalid excerpts use the same three structured
repair retries. An explicit retraction replaces the earlier claim. Python enforces
zero for no support or a contradicted central claim, and caps support at 0.5 when
another material claim remains unsupported. The three citation bands are unchanged.

Repeat calibration showed that excerpt validation alone was insufficient: the
context judge could still infer support from unrelated text elsewhere in the
document. Citation grading now follows its context assessment with an independent
quotation-only check. That check sees claims and candidate quotations, but no
original documents, document identifiers, or prior reasoning. It can only remove
support. The complete two-stage citation flow passed all 60 checks across three
repeats of the 20-case control set. Final all-question replay and additional
specificity controls are running; completion
and remaining disagreements will be recorded in the
[calibration report](experiment/rubric-integration-2026-11-19/report.md).
All 219 selected local checks passed, covering structured output and repairs,
criterion arithmetic, citation evidence, source provenance, reward, concurrency,
and package isolation. Live Terra calibration and Logfire validation remain
pending; Logfire was not retried after the earlier stop request. No upload,
commit, or new Oddish trial was performed.

### 2026-11-19 — required facts and conditional rubric checks

Reviewed all 218 active questions and 1,156 original rules before changing to
per-criterion accuracy scoring. Of these questions, 179 had no unconditional
required answer fact; one more had a required fact too weak to answer the
question. The review also found eight questions with unnecessary requirements,
five with ambiguous rules, and 22 with source or reference qualifications.
Those 22 are review concerns, not 22 proven incorrect gold answers: six gold
lists omit supported issues, three have scope or attribution limitations, and
other findings concern lifecycle wording, source context, or non-exhaustive lists.

The [complete review](experiment/rubric-quality-astra-2026-11-19/quality-review.md)
links every question to its original rules, proposed replacements, and exact
source anchors. The [proposed rubrics](experiment/rubric-quality-astra-2026-11-19/proposed_rubrics.json)
contain 249 required facts and 1,061 conditional checks. Every proposal has at
least one positive factual requirement. Correct or unmentioned optional details
add nothing to either numerator or denominator; incorrect optional claims remain
errors. The proposals are separate from the active evaluation inputs. The new
ratio calculation has not been installed, and citation evaluation is unchanged.

A final [policy review](experiment/rubric-quality-astra-2026-11-19/proposal-followups.json)
flagged 27 proposed rewrites with multiple required facts: 19 may impose list
coverage, six involve explicit "all" questions, and two risk overlapping or
unnecessary requirements. Review these before activation so adding mandatory
content does not silently introduce completeness grading.

GPT-6 Astra High completed an audit and a fresh-context review for 214 questions,
using up to 32 concurrent workflows. After API timeouts and account-quota
exhaustion, local Codex source review completed the remaining four; their method
is explicitly recorded. These are not four completed Astra second passes, and
none of the reviews is human-certified. The
[run status](experiment/rubric-quality-astra-2026-11-19/run-status.json) preserves
the failures and completion methods.

All 15 local audit checks passed. Every original rule is classified exactly once;
each proposed rule has one required/conditional classification; exact quotations
and source IDs validate. Active cases, corpus, rubrics, and manifest hashes are
unchanged. Live calibration of the proposed rubrics remains pending.

### 2026-11-19 — factual rubrics and three citation bands

The accuracy judge now receives the question, original reference answer, reviewed
must-have points, and candidate answer, with question-type and answerability
metadata. It receives no source documents or citation objects. The 218 retained
questions use 1,156 reviewed rules from private `rubrics.json`; hashes and exact
question/reference associations are checked before evaluation. Missing rubrics
invalidate evaluation rather than silently falling back to reference-only grading.

Accuracy uses factual correctness, with no completeness penalty for omitted
optional facts. Conditional must-have points apply only to claims the answer
makes. The answer keeps its five bands. Citation scores are now restricted by
the Pydantic output schema to 0, 0.5, and 1: no support, partial support, or full
support. Citation judging still reads full cited originals, runs only after an
eligible answer score of at least 0.75, and enforces zero when no material claim
is supported. Reward weights, concurrency, and the Terra High model are unchanged.

All 159 targeted checks passed. They cover request contents, rubric integrity and coverage, native
schema rejection of removed citation bands, conditional call order, concurrency,
reward computation, and package loading. These checks do not establish semantic
judge quality. Live calibration of the new prompts remains pending, and historical
calibration fixtures must supply their reviewed rubrics before being rerun.

### 2026-11-19 — excluded flagged gold answers

Removed all 20 questions flagged by the factual-rubric review from the active
private evaluation set, leaving 218 questions. The 39,268-document corpus and
1,570-record development sample are unchanged. Retained questions keep their
original answers and evidence links. Updated the private manifest, case hash,
and verifier denominator.

[`scripts/holdout_exclusions.json`](scripts/holdout_exclusions.json) records the
excluded IDs and review-report hash. Data preparation applies this policy on
every rebuild. The [238-question review](experiment/factual-rubrics-astra-grounded-2026-11-19/gold-answer-review.md)
remains a historical audit; [active rubrics](experiment/factual-rubrics-astra-grounded-2026-11-19/rubrics.active.json)
contain only the retained questions. Earlier trial scores and calibration results
still refer to their original question sets and have not been rescored.

Validation: 30 targeted checks passed, including the package round trip. Reapplying
the exclusion policy to the archived source cases reproduces the active set
exactly. Corpus, development-sample, and historical review hashes are unchanged.

### 2026-11-19 — resource directory overview

Shortened `environment/resources/README.md` to a path table and the connection
details needed for the supplied models and separate Chroma service. Removed the
full filesystem tree, duplicated model configuration, direct embedding endpoint
instructions, and image-build details. The overview points to `resources.json`
and `chroma-api.md` for specifics. Checked paths and runtime settings against the
Dockerfile and resource configuration; task instructions are unchanged.

### 2026-11-19 — concise Chroma client documentation

Replaced the 563-line API dump with an 88-line guide for the supplied Chroma
1.5.9 HTTP service. It covers connection variables, explicit embeddings, result
shapes, pagination, supported writes, and request limits. The resource README
now links to that guide instead of repeating its details. The guide uses original
explanations and small examples; copied upstream docstrings and their embedded
license appendix are no longer part of it. Task instructions are unchanged.

Executed the guide's Python examples against the protected service and checked
the client, application, verifier, and service version pins. All 12 documentation
and service checks passed. The bundle round-trip check also passed, including
identical documentation in the development and evaluation build contexts.
These checks validate the guide and packaging; no deployed container was updated.

### 2026-11-19 — private factual-rubric authoring

Added `scripts/factual_rubrics/` to draft and independently review one private
`rubric: list[str]` per content question. Every item starts with `must `. The
authoring policy assesses substantive factual correctness, permits omission of
optional details, and uses conditional constraints for claims actually made.
Each record preserves the original reference answer and complete linked source
documents alongside an evidence-grounded example answer, exact grounding quotes,
and source/reference discrepancy notes. Model review does not certify ground truth.

Completed all 238 questions with GPT-6 Astra, high reasoning, and up to 32
concurrent question workflows. The result contains 1,297 rules, each on one line
with an exact source or gold-answer quotation; the longest is 24 words.
Every rule passed literal-source validation and a fresh-context model review.
Original employee and customer directory records supplement the linked documents
where needed to resolve IDs, roles, and customer affiliations. All original
questions, gold answers, and linked documents are preserved.

The [compact rubric dataset](experiment/factual-rubrics-astra-grounded-2026-11-19/rubrics.compact.json)
and [full source-linked export](experiment/factual-rubrics-astra-grounded-2026-11-19/rubrics.json)
are private, ignored authoring artifacts. The workflow authenticates input hashes,
checkpoints both passes, and exports the dataset only when every case validates.
Sixteen local checks passed for formatting, exact-source provenance, optional
details, directory resolution, incomplete exports, and gold-review preservation.

The [gold-answer review](experiment/factual-rubrics-astra-grounded-2026-11-19/gold-answer-review.md)
flags 20 questions: 11 with factual, attribution, lifecycle, or conflicting-record
concerns, and nine with insufficient evidence for implied nonimplementation.
One clear defect is `FeedbackForce:content:16`: its gold answer is an employee
ID rather than the requested unresolved customer issue. Other flags require
source or time qualifications; they are not all proven wrong answers. The report
keeps original answers, proposed corrections, source-specific notes, and complete
supporting records. The remaining 218 references passed model review, not human
certification. These counts are not a measured gold-answer error rate.

This authoring run does not change production gold answers, the judge, scoring,
or the candidate environment. Review the flagged cases and calibrate the proposed
rubrics before integrating them into evaluation.

### 2026-11-19 — Protected CPU Chroma service

Moved the database contract from candidate-owned `/app/state/chroma` to a
Chroma 1.5.9 HTTP service. The canonical service lives in `common/chroma-service`;
packaging stages the same locked source into both Compose build contexts. Each
environment owns a separate anonymous database volume. Only the application
service requests a GPU. The Chroma container has a four-CPU limit, 8 GiB memory
limit, a read-only root filesystem, no capabilities, and no shared database or
Docker-socket mount.

The service validates requests before database execution. Gets default to 100
records, larger explicit limits and ID lists are rejected, and batched vector
queries share a total budget of 100 results. Collection listings are paginated
too. Only the default namespace and required v2 data endpoints are exposed;
legacy, reset, alternate-database, function-attachment, and other routes are
denied. Request bodies are limited to 16 MiB. A small adapter converts the pinned
Rust backend's vector lists to the ndarray form its HTTP serializer expects.

Updated the instruction's storage paragraph, offline client example, verifier
storage inspection and cleanup, controlled fixtures, and existing oracle to use
the service. Original document IDs, bodies, vectors, chunk ownership, refresh,
and append checks remain. Accuracy still runs through the CLI and the reward
formula is unchanged. Chroma storage is not transferred from development into
evaluation; the evaluation environment starts its own service and ingestion
rebuilds it from the supplied corpus.

Validation: 60 service/verifier/oracle/baseline checks passed, followed by 12
packaging and large-corpus pagination checks. The expanded service suite passed
11 checks covering raw HTTP bypass attempts, batched limits, concurrent readers,
oversized bodies, restart persistence, and fresh-instance isolation. The live
Modal CPU smoke passed with networking blocked, no GPU, and service-owned files.
Modal ignores Dockerfile `USER` when running an image directly, so that smoke
explicitly dropped to UID 10002; Compose declares the same UID independently.
A two-container CPU Compose smoke also passed on a Modal VM: candidate UID 10001
could reach the capped API but could not see the database files, service source,
or Docker socket; reset was rejected. The GPU Docker-in-Docker probe did not
finish sandbox startup and was terminated before Docker commands ran. Full GPU
Compose deployment remains unverified; the CPU smoke does not establish it.

Built local bundle `a88dd2b38a6b`. The updated packaging suite passed all 11
checks, including identical service sources in both environments and private
volume configuration. Repository validation passed for 183 source files and
one configured task. No bundle was uploaded and no Oddish trial was launched.
The full regression run recorded 314 passes and four stale-fixture failures:
one CLI observer missed the bounded answer entrypoint, and three mutation tests
still targeted the removed local-state guard. After fixing those fixtures, all
35 contract checks passed. The answer-judging fixture also now substitutes both
CLI entrypoints. No production scoring or retrieval-budget behavior was changed.

Security scope: the cap applies to records returned by this service per HTTP
request. It does not prevent repeated pages, alternate indexes built from the
readable corpus, or denial-of-service attempts. No claim of complete resistance
to arbitrary hostile code is made. Container isolation and API regression tests
must be distinguished from a full adversarial security review. Current boundary
status is **YELLOW / UNASSESSED** for the final GPU deployment.

### 2026-11-19 — factual correctness in task and oracle prompts

Updated the step-one goal and the oracle's search-agent prompt to prioritize
factual correctness. Both ask for claims grounded in company records, supporting
citations, and explicit uncertainty without guessing. The agentic retrieval
requirement remains. This is a prompt-only change; judge rubrics and reward
computation are unchanged. Reviewed the edited wording and checked the oracle
module's syntax; live answer-quality validation remains pending.

### 2026-11-18 — PydanticAI oracle tools

Replaced the oracle's manual Responses loop with a PydanticAI agent and a typed
`retrieve` tool. The tool routes through the public application function, retains
request-local evidence IDs, and supports all three retrieval methods. Native
structured output and an output validator reject invented citation IDs. Dynamic
tool preparation removes retrieval at the configured search limit, while usage
limits and an execution counter cap calls at 50. The final answer still has its
own model turn within the 30-minute question deadline. Output retries are three
and transport retries zero, both explicit in the oracle configuration.

Added an identical locked `/opt/application` Python environment to the agent and
verifier image recipes. It supplies PydanticAI 2.68.0 and OpenAI 3.49.0 without
changing the separate SGLang GPU runtime or its OpenAI 2.6.1 pin. The oracle
launcher and verifier's application interpreter selection use this environment;
a submitted `/app/.venv` retains precedence. Optional Logfire tracing now uses
PydanticAI instrumentation for model and tool spans. The reward and judge prompts
are unchanged. These local edits do not alter the already-running version-7
Oddish trials; the new image has not yet been built or evaluated there.

Controlled validation passed for the oracle, shared baseline rewards, packaging,
retrieval budgets, and Jina helper. The suite initially found a stale packaging
assertion for the former eight/thirty-six-hour limits; it now matches the existing
four/twenty-eight-hour task settings and passes. The final typed-tool test passed
with ten concurrent CLI processes, and the interpreter-selection check confirmed
application-runtime and submitted-venv precedence. The Linux application lock
validated offline. Bundle `6ca7e208ddd2` passed Oddish preflight with no findings;
this checks packaging, not a live GPU image build or full HERB evaluation.

### 2026-11-18 — use conversation history for earlier requirements

Removed the copied step-one instruction and its empty workdir folders at the
author's request. Step two now refers to the application requirements from
step one in the conversation. This supersedes the file-copy approach recorded
below. Multi-step runs will need `agent.resume_trajectory = true` in their run
configuration to retain that conversation. Step-two execution remains pending.

### 2026-11-18 — step-two requirements reference

Added a draft instruction under `steps/02-expand-corpus/` and a copy of the
current step-one instruction at `workdir/requirements/step-1.md` within that
step. Harbor uploads the workdir contents into `/app` when the step begins,
making the earlier contract available at `/app/requirements/step-1.md`.
The new instruction references that file and asks for better answers across
conversations and changing facts. Refresh the copy whenever step one's contract
changes before packaging step two.

Checked that the saved requirements match the current step-one instruction
byte for byte and that Harbor resolves the expected workdir path. Step two is
a draft. Its verifier, task registration, and packaging support remain pending.

### 2026-11-18 — full checks and Opus 5.5 comparison

Repackaged the current `main` working tree and uploaded it with Oddish CLI 0.1.31.
Preflight passed with no findings. Oddish reused version 7 because runtime content
is unchanged (`4ed45c3e11d6eda4c4e615806573d2840e3a5b91d74eb67f366f66bb3cb063b1`);
the latest author README and local regression tests are excluded from runtime
bundles. Started one Claude Code trial using
`global.anthropic.claude-opus-5-5`, explicitly confirmed at maximum reasoning
effort, plus one no-op and one oracle baseline using the same production verifier.
The model trial runs independently of baseline results. All three were running
environment setup at the initial status check; no reward was available.

[Experiment](https://www.oddish.app/experiments/dad248f5): no-op `…-14`, oracle
`…-15`, and Claude Code `…-16`. Added these runs to the existing private
[`swe-maarathon-2` collection](https://www.oddish.app/experiments/6d33bbbd).
Requested full QA for version 7: source audit `…-17` was running, and post-trial
analysis is durably requested for completion of the eligible trials. Requested
the black-box and white-box adversarial suite, which queued `…-18` and `…-19`.
Both attacks then entered retrying with `ValueError: Adversarial QA supports
single-step tasks only`, before executing an attack. The task declares one
enabled step through Harbor's multi-step schema, which this deployed attack
runner rejects. This is missing adversarial execution evidence, not a passed
security check. The rollout, baselines, and source audit were unaffected.
Submission and status records are in
`experiment/oddish-opus55-full-checks-2026-11-18/`.

These are execution requests and startup observations, not completed QA verdicts
or benchmark scores. Existing judge-calibration disagreements remain; this
submission did not perform or establish a new accepted calibration.

### 2026-11-18 — no-op and oracle reward parity

Added a paired baseline regression that runs an empty submission and the installed
oracle through the full production verifier registry and reward aggregator.
A third case marks every oracle answer incorrect to check that passing contracts
cannot give it a positive reward. The local check uses synthetic records and
controlled model services; it does not establish a live HERB score. All three
cases passed in 28.53 seconds, yielding rewards 0, 1, and 0 respectively.
Documented Harbor's built-in `nop` and `oracle` runs against the same packaged
task below; both command configurations were accepted without launching trials.

### 2026-11-18 — reward documentation

Checked the reward explanation against the scoring implementation, question
grading flow, registry, and verifier configuration. Documented the five score
bands, conditional citation judging, 238-question denominator, 15 equally
weighted contract checks, and zero-answer rule. Added worked examples and links
to the implementation and existing boundary checks. All eight table examples
match `aggregate_results` with the current configured weights, and all file links
in the reward section resolve. This update changes only author documentation;
it does not change scoring or claim new judge calibration.

### 2026-11-18 — collection and cancellation

Created the private `swe-maarathon-2` collection (`6d33bbbd`) containing the two
version-7 comparison trials. Then cancelled exactly trials `…-11` and `…-12`
at the user's request. Oddish confirmed both cancellations and termination of
two Modal calls. Proximus had not been submitted. Existing completed results
and other task activity were preserved. Evidence is saved alongside the launch
records in `experiment/oddish-herb-three-harnesses-2026-11-18/`.

### 2026-11-18 — Oddish version 7 comparison

Uploaded the HERB package as task version 7 using Oddish CLI 0.1.31; local preflight
passed with no findings. Started one Claude Code trial with
`global.anthropic.claude-opus-5-5` and one Codex trial with `openai/gpt-6-astra`,
both with `reasoning_effort=max`, on Modal. Oddish reported both running at the
last status check. The trials use four hours for the coding agent and 28 hours
for verification. No scores are available yet.

[Experiment](https://www.oddish.app/experiments/5e023706): trials
`swe-m2_ai-engineering_knowledge-work-assistant-727a668e-11` and
`swe-m2_ai-engineering_knowledge-work-assistant-727a668e-12`.
Submission, version, configuration, and startup evidence are retained under
`experiment/oddish-herb-three-harnesses-2026-11-18/`.

The requested Proximus comparison was not submitted. The current upstream
[Oddish integration](https://github.com/abundant-ai/oddish/blob/main/oddish/src/oddish/workers/harbor/proximus.py)
rejects both multi-step task configurations and GPU environments, including this
one. Verified source blob: `753a45140f9f42309afb9e4f9c9be132c293bcd4`.
Supporting that trial requires an integration change; the task was not altered
into a different benchmark to bypass those checks.

These are diagnostic runs. Known judge-calibration disagreements remain, and no
fresh calibration or evaluation-trace validation was performed for this launch.
Do not treat trial completion as acceptance of the judge's reliability.

### 2026-11-18 — revised execution budgets

Set the coding-agent deadline to four hours at both root and step level, and
state that development deadline in the instruction. Recomputed the verifier cap
for HERB as 28 hours (100,800 seconds), also at both levels.

The planning allocation is four hours for ingestion, twelve for 238 held-out
questions at ten workers and thirty minutes per question, seven for the functional
checks' answer invocations, and five for judging, persistence checks, and overhead.
Functional answering comprises 0.5 hours for the no-index check, 1.5 for call-path
checks, 1 for retrieval-budget checks, 2 for question-file checks, and 2 for stdin
checks. The five-hour reserve is an estimate, not separate enforced phase limits
or a guarantee that every nested storage timeout and judge retry can exhaust its
maximum. The overall 28-hour cap takes precedence. Image builds retain their
separate one-hour limits. Retrieval remains capped at 50 calls per question.

### 2026-11-18 — per-question retrieval limit

The instruction now limits each question to 50 `retrieve()` calls in total,
including retries and parallel searches across all methods. The oracle's two
search-budget settings are both 50, and it tells the assistant how many calls
remain before each model turn. It can answer earlier.

The verifier reads `ORANGE_EVAL_MAX_RETRIEVAL_CALLS=50` from `task.toml`.
Every held-out question still runs through the actual CLI. A Python startup hook
asks a verifier-owned counter for permission before each new retrieval frame;
coroutine resumes do not spend another call. Python child processes share that
question's counter. Attempting call 51 terminates the worker and invalidates only
that question's answer, even if a parent process ignores a child's failure. The
counter saves no queries, evidence, or trajectories. A separate `test_retrieval_budget`
checks this contract with small public fixtures, bringing the functional count to 15.

The counter is outside the candidate process, but call observation still depends
on an in-process Python hook. A deliberately tampered interpreter or disabled
profiler could evade observation; this is not a tamper-proof search-service boundary.
Validation: 83 targeted regression checks passed. A further focused run passed
all ten boundary checks, including the added cross-process case. Coverage includes
49/50/51 calls, parallel searches, async resumes, question-local failures, and the
oracle's forced final answer. The step-1 archive was rebuilt. No live model
evaluation or Oddish trial was run. Judge prompts, output schemas, HERB inputs,
and the Terra High model are unchanged.

### 2026-11-18 — restored HERB

Restored the original HERB private evaluation from revision
`db3bf9b3f911745726c579c9dbf9f7f6b2c05b36`: 39,268 source records and all
238 content questions, with the original references and evidence IDs. Restored
its seeded 4% development sample (1,570 records). The EnterpriseRAG inputs are
archived under `experiment/enterprise-before-herb-2026-11-18/` and are excluded
from runtime packaging. No EnterpriseRAG ingestion or evaluation job was running.

The candidate instruction, answer prompt, citation prompt, and output schemas
were preserved. The judge remains `gpt-6.1-terra` with high reasoning. Existing
calibration results below describe their original datasets; this switch does not
constitute a new calibration or a completed oracle evaluation.

Validation: 119 targeted verifier, judge, reward, evidence, and packaging checks
and 23 controlled oracle checks passed after updating dataset-specific expectations.
Verified original corpus/case equality and unchanged prompt hashes. Rebuilt the
step-1 archive in `experiment/dist/`; no live evaluation was launched.

### 2026-11-18 — earlier EnterpriseRAG experiment

Step 1 temporarily used the pinned EnterpriseRAG-Bench core corpus and questions. All
511,962 rows are preserved; the agent receives 20,478 uniformly sampled records
(4%, rounded down), with seed 20261112. Evaluation refresh-ingests the complete
corpus through the CLI and retains all 500 core questions. The supplementary
100 metadata questions are excluded. No prepared vector database is shipped.

Four upstream IDs identify different document bodies. Preparation preserves the
first ID and gives each additional body a deterministic content-derived suffix,
recording the alias mapping in the private manifest. A gold ID resolves to every
preserved version. In particular, `qst_0413` references the same ID twice; it now
resolves to both tickets without duplicate evidence entries. The newer ticket
changes the grace window to five business days and records infra-manager guidance,
while the upstream answer describes the earlier 72-hour version. Upstream references
remain unchanged; the judge is instructed to explain evidence/reference conflicts.
This known discrepancy needs author review before reporting benchmark comparisons.

The judge receives required reference facts and an explicit evidence mode. The
470 ordinary questions use gold documents, 10 high-level questions use reference
facts plus any verified cited originals, and 20 information-not-found questions
permit appropriately scoped abstention. A fully correct uncited abstention has an
inapplicable citation component, with its weight reassigned to answer quality.
Ordinary uncited answers still receive zero citation credit. Pydantic output classes
and their field descriptions are unchanged, verified against the previous source.
The five bands, fixed Terra High model, three output retries, 0.75 citation gate,
and ten concurrent question pipelines are retained.

The 2.588 GB corpus is streamed during preparation and packaging. A separately
hashed SQLite byte-offset index supports trusted source lookup; it contains no
embeddings and never reaches the candidate. The storage probe compares a canonical
digest of all document IDs and body hashes, checks every vector, and reports stale
chunk ownership without printing a multi-megabyte snapshot. The verifier budget
is 36 hours, with an explicit four-hour ingestion allowance; both images request
32 GB RAM and 64 GB storage. These are provisioning allowances, not measured
full-corpus performance. The exact public interfaces remain unchanged; only the
instruction's source-domain description changed.

Live calibration used the real production accuracy flow with a controlled replay
CLI, not the oracle or a retrieval system. Round 1 completed 32 judgments over four
source questions, with 12 disagreements against predeclared expectations. Source
inspection established that one supposed correct example copied the stale reference;
round 2 labels that example as stale and adds a fully supported version-aware answer.
Round 2 completed 34 judgments with 10 disagreements. Both rounds reached ten
concurrent judge requests with no premature/below-threshold citation calls.
Correct answers and supported extras received full credit; irrelevant citations
received zero. The answer judge still awards partial credit to some wholly wrong,
instruction-only, or falsely abstaining answers, and once awarded 0.75 to invented
specifics on an unanswerable question. This judge is **not accepted as calibrated**.
These small author-labelled samples are diagnostic, not an estimate of population
reliability or a RAG accuracy score.

Local evidence: [first calibration](experiment/enterprise-calibration-2026-11-18/summary.json),
[revised calibration](experiment/enterprise-calibration-2026-11-18-v2/summary.json),
and [complete second-run judgments](experiment/enterprise-calibration-2026-11-18-v2/results.json).
The reproducible [runner](scripts/calibrate_enterprise.py) saves fixtures before
making provider calls and records model, schema/prompt hashes, response IDs, call
order, expected bands, and disagreements. The first two runs did not emit hosted
traces. Organization access subsequently allowed creation of the private
[`abundant/swe-marathon-2` Logfire project](https://logfire-us.pydantic.dev/abundant/swe-marathon-2).
A project-scoped telemetry key is stored in the ignored local `.env`.

The [Logfire-enabled rerun](experiment/enterprise-calibration-2026-11-18-logfire/summary.json)
completed all 34 evaluations with GPT-6.1 Terra High. Fixtures, prompt hashes,
and schema hashes matched round 2. Its 34 answer calls and eight citation calls
took 27.8 seconds from first judge request to last completion, with peak
concurrency ten and no citation-gate violations. Both judge span types were
verified in the Logfire live view. The existing MCP read credential still exposes
only `diorama`; browser access verified these traces.

There were ten disagreements, matching the previous run's count: both repeats
of wholly wrong numeric limits, instruction-only answers, wrong mission statements,
false abstentions, and invented specifics. The first four received 0.25 instead
of zero. Invented specifics received 0.25 and 0.75 instead of zero. Correct answers
and supported extras received full credit; both irrelevant citations received
zero. All eight actual citation judgments matched their expected bands. The
answer judge remains **not accepted as calibrated**. These are disagreements
against author-defined labels, not measured human inter-rater agreement.
No Oddish run, GPU image build, or full-corpus oracle evaluation was performed.

A subsequent text-only revision asks the answer judge to assess required facts,
extra claims, and abstention before selecting a band. The answer schema's field
descriptions now require a concrete correct proposition or valid abstention to
justify nonzero credit. Output fields, types, validation constraints, and the five
bands remain unchanged; the citation prompt and schema are unchanged. All 76
existing judge and reward checks passed, and JSON-schema comparison confirmed
that only answer field descriptions changed.

The [text-revision comparison](experiment/enterprise-calibration-2026-11-18-rubric-text/comparison.json)
uses the identical 34 fixtures, model, reasoning effort, and scoring policy as the
previous Logfire run. All cases completed, with 34 answer calls and ten citation
calls in 27.28 seconds, peak concurrency ten, and no gate-order or threshold
violations. Both span types were visible in Logfire. Answer disagreements stayed
at 10/34, but four previously wrong 0.25 grades rose to 0.75: one wrong-limits
answer, one instruction-only answer, and both wrong-mission answers. One newly
eligible citation judgment also awarded 0.25 to the wrong-limits answer by counting
the presence of limit categories as support despite contradicting both values.
Citation disagreements therefore increased from zero out of eight calls to one
out of ten; the ten affected cases include both answer and citation disagreement
on the same wrong-limits case. Correct answers and supported additions still
received full credit, and irrelevant quotations still received zero.

This revision is **not accepted as calibrated**. Several explanations now invent
correct substance or attribute candidate claims to the reference. Stronger wording
did not resolve the observed failures. The revised files remain available for
review; the result does not justify deployment or a claim of improved reliability.

The [Sol High comparison](experiment/enterprise-calibration-2026-11-18-sol-high/comparison.json)
ran the identical 34 cases with `gpt-6.1-sol`, overriding the model only inside
the experiment process. The production judge remains pinned to Terra. Fixture,
prompt, schema, and scoring-policy comparisons all matched the revised-text Terra
baseline. Both judge span types appeared in Logfire. Sol completed 34 answer calls
and nine citation calls in 43.92 seconds, with peak concurrency ten and no
citation-gate violations, compared with Terra's 27.28 seconds and ten citation calls.

Sol had nine answer disagreements and one citation disagreement, versus Terra's
ten answer disagreements and one citation disagreement. Both runs had ten distinct
cases with at least one disagreement. Sol assigned zero to one wrong-limits repeat
and one wrong-mission repeat, but still credited both injection answers, both false
abstentions, and both invented-specifics answers. It also assigned 0.5 to one
wrong-approver variant outside that fixture's expected 0/0.25 bands; that case involves
the previously documented conflict between source versions. Its citation error
assigned 0.25 to an irrelevant quotation, marking a claim supported despite explaining
that the quotation did not establish it. Correct answers and supported extra details
retained full credit. Neither model is accepted as calibrated; this small repeated
diagnostic set does not establish a reliable overall ranking between them.


### 2026-11-17

Added a step-1 baseline oracle under `steps/01-build-rag/solution/`. It implements
BM25, Jina embedding search, and reciprocal rank fusion through the existing
`hybrid` interface. Retrieval depth and the RRF rank constant are both fixed at
20 as requested. The public Pydantic declarations, JSON CLI, Chroma document
storage, append/refresh behavior, and iterative `retrieve` tool calls follow the
current instruction without changing it. The oracle uses only public resources;
it does not read held-out questions, references, or judge configuration.

Validation: 23 oracle tests passed, including all 13 existing functional verifier
checks, ten concurrent answer processes, bounded iterative search, invalid model
outputs, exact excerpts, refresh/append persistence, isolated installation, and
the complete oracle entry point. Eleven packaging tests also passed, including
the real archive/extract round trip and solution-file inclusion. Repository
source checks passed. These runs used real Chroma 1.5.9 and SQLite with controlled
CPU embeddings and a loopback Responses API substitute. Live Jina/GPT-6 Luna
behavior, full-corpus runtime, answer quality, and fresh-container verification
of this oracle remain unvalidated. No Oddish run was launched.

Removed the corpus-attribution section and embedded license text from this README
at the author's request. Updated the packaging test to stop requiring that README
section; it still checks that candidate inputs omit upstream dataset identity.
Validation after this change: all 262 tests passed with no skips, and the JUnit
checker confirmed coverage of all 14 maintained test modules. Repository checks,
workflow linting with ShellCheck, and offline lockfile validation also passed.

Attempted the 19-criterion Harbor review with Codex and `openai/gpt-6.1` on
Modal. The default Modal environment was unavailable; a retry using the existing
`testing` environment reached reviewer startup, then OpenAI rejected Codex usage
for the configured organization with `codex_byok_restricted_by_api_credit_promo`.
The report contains an execution error and no criterion findings. This is an
infrastructure/account limitation, not a task-quality result. No task-rating
scores were written to `task.toml`.

The reviewed input snapshot excluded task-root `checks/`, `scripts/`, experiments,
caches, and credentials. It retained runtime sources and data, author notes, and
reference documents for review. The snapshot digest is
`4b2c0114d2f22bb6f502cf5deff5fd8d50493d03ae1f1d0bfab5b4cb4ffc9338`;
its [source manifest](experiment/harbor-review-20261117T034156Z/source-manifest.json)
records file hashes and the rubric digest. The
[failed review report](experiment/harbor-review-20261117T034156Z/jobs/knowledge-work-assistant-review-testing/check_report.json)
and logs remain local. Retry with a Codex-eligible API credential, then apply the
task-rating skill to a completed report. This log entry was added after the
snapshot; runtime sources and instructions are unchanged by the review attempt.

Consolidated the development README, checks, scripts, and dependency files into
this task directory. Preserved local reports and generated bundles under the
Git-ignored `experiment/` directory. Packaging selects runtime inputs explicitly
and defaults to `experiment/dist/`. Existing research and evaluation notes below
retain their original dates and limitations. This entry records the source-layout
migration.

Validation: repository source and link checks passed, all 14 CI regression tests
passed, and the full local pytest suite passed 248 tests with no skips. The suite
included the package/extract round trip using prepared inputs. A subsequently
added packaging test also passed, confirming that local experiments and
development files are excluded. The dependency lockfile passed an offline
consistency check. No GPU image build, live judge call, hosted CI run, or Oddish
trial was performed for this migration.

The task's setup commands now link to the shared repository installation guide.
Project execution commands use the frozen root lockfile. Oddish CLI and Titans
remain optional; container dependency files are unchanged. Validation passed:
25 CI and packaging tests, repository source checks, the offline lockfile check,
and dry runs of both default and Titans-enabled sync. Optional tools were not
installed or upgraded during this change.

The CI audit added checks for stale dependency locks, omitted or empty test
suites, and incomplete test reports. Renamed the manual container probes to
`checks/smoke_container.py` and `checks/smoke_environment.py` so their filenames
do not imply pytest execution. Their probe logic is unchanged.

Validation: reran HERB preparation, then passed all 262 local tests with no
skips, including the package round trip and 27 CI regression tests. The report
checker confirmed execution across all 14 maintained test modules. Repository
checks, actionlint with ShellCheck, and the offline dependency check passed.
An isolated stale-lock example failed as expected. Hosted Ubuntu CI and actual
container probes were not run. See [CI evidence](../../../resources/CI.md) for
coverage and the pending GitHub merge requirements.

## Current implementation

Only `01-build-rag` is enabled in `task.toml` and included in the bundle. Later
steps are not implemented.

The agent image starts with an empty `/app`. It contains a uniform sample of
1,570 out of 39,268 corpus records (4%, rounded down), local Jina embeddings, and
configuration for `gpt-6-luna`. The agent discovers these through `/data`,
`/opt/resources`, environment variables, and the installed packages. The instruction
asks it to use available resources without listing the tools or sample size.

The full corpus and 218 retained content-question references are evaluation inputs.
They are excluded from the agent image. The sample includes source records only;
the agent must create its own development questions and reference answers.

Both development and evaluation allow outbound connections only to `api.openai.com`.
This is a model-service exception, not an air gap: the domain policy does not restrict
individual API features, and the provider may permit DNS. Dependencies, model weights,
and any coding-harness installation that needs public downloads must be provisioned
before the restricted development session starts. The live enforcement of this new
development policy has not yet been tested.

Candidate resources omit the dataset name, upstream repository, and revision.
Provenance and attribution remain in author documentation and the private manifest.
This removes an explicit discovery route; it does not prove that public source records
cannot be recognized or were absent from model training.

The sample contains 1,328 Slack records, 158 PRs, 21 documents, 16 meeting
transcripts, 2 meeting chats, 17 URL records, and 28 directory records. Uniform
record sampling does not guarantee complete conversations or evidence chains.

### Step-1 baseline oracle

[solution/oracle.py](steps/01-build-rag/solution/oracle.py) implements
`oracle(context: OracleContext) -> None`; [solve.sh](steps/01-build-rag/solution/solve.sh)
is Harbor's thin adapter. The installer copies only the application payload into
`/app`, makes `orange` executable, and preserves the exact interfaces in
[main.py](steps/01-build-rag/solution/app/main.py).

| Public retrieval method | Baseline implementation |
| --- | --- |
| `bm25` | SQLite FTS5 BM25 over chunk titles and exact body excerpts; top 20. |
| `embed` | Supplied local Jina/SGLang helper and Chroma cosine search; top 20 chunks. |
| `hybrid` | Equal-weight RRF over both top-20 lists; score is `sum(1 / (20 + rank))`, with ranks starting at 1; top 20 fused chunks. |

Chunks contain up to 2,000 characters with 200-character overlap. Chroma's
`documents` collection retains original IDs and complete, unchanged bodies;
document vectors are normalized means of their chunk vectors. The `chunks`
collection stores exact excerpts with source `doc_id` metadata. SQLite lexical
state also lives under `/app/state`. Append skips existing IDs. Refresh rebuilds
both indexes. An interrupted ingestion leaves the index unavailable until a
successful refresh, rather than serving inconsistent state.

Generation uses a typed PydanticAI `Agent[SearchContext, AnswerDraft]`, constructed
in [agent.py](steps/01-build-rag/solution/app/orange_core/agent.py), with the public
resource manifest's assistant and Responses endpoint. Its registered `retrieve`
tool accepts a query and `bm25`, `embed`, or `hybrid`, then calls the application's
public `retrieve()` through the injected search callback. PydanticAI handles tool
argument validation, message history, and the model/tool loop. The assistant selects successive `retrieve` calls and references returned
evidence IDs in its structured answer. The application resolves those IDs to
exact passages; invented evidence IDs are rejected. Each question has independent
history and evidence, up to 50 search rounds and 50 retrieval calls, followed
by a final-answer request, within the 30-minute ceiling. The tool is required on
the first turn and removed when either search budget is exhausted. PydanticAI's
usage limits and the tool's own counter enforce the call ceiling. A native strict
`AnswerDraft` schema constrains the answer; an output validator rejects unobserved
evidence IDs. Up to three output-correction retries share the overall request
budget. Transport retries are explicitly zero. These bounds and chunk
settings are declared in [oracle-config.json](steps/01-build-rag/solution/app/oracle-config.json).
The two fixed retrieval constants live in
[config.py](steps/01-build-rag/solution/app/orange_core/config.py).

The default oracle runs a small authored development corpus through the real CLI,
saves its questions, reference answers, generated answers, and substring-based
smoke report under `/app/dev/v1`, then replaces that index with the public sample.
`oracle.py --install-only` supports local contract testing without model calls.
No private index is shipped. The verifier still performs its own refresh ingestion.
The baseline has not completed a full-corpus evaluation against the restored
private questions with the current judge.

### No-op and oracle evaluation

Use Harbor's built-in `nop` agent as the no-op baseline. It leaves `/app` empty;
there is no separate no-op application to ship. Harbor's `oracle` agent runs
the step's `solution/solve.sh` to produce the application. Neither baseline
assigns its own reward.

Both use the same packaged task, private questions, judge configuration, and
fresh separate verifier container as coding-agent submissions. The execution
path is `tests/test.sh` → `tests/verify.py` → `verifier.runner.verify()` →
`verifier.scoring.aggregate_results()`. The oracle receives no scoring exemption:
the verifier refresh-ingests the private corpus through its CLI, generates answers
under the same limits, and runs all contract checks. Its development smoke report
does not contribute to reward.

After packaging, set `TASK_BUNDLE` to the emitted `task_path`. With the approved
credentials already in the process environment, these commands evaluate each
baseline and save separate trial records:

```bash
TASK_BUNDLE=/path/to/packaged/swe-m2_ai-engineering_knowledge-work-assistant
BASELINE_RESULTS=tasks/swe-m2-ai-engineer/knowledge-work-assistant/experiment/baselines

MODAL_ENVIRONMENT=testing uv run --frozen harbor run \
  --path "$TASK_BUNDLE" --agent nop --env modal \
  --jobs-dir "$BASELINE_RESULTS" --job-name step1-nop

MODAL_ENVIRONMENT=testing uv run --frozen harbor run \
  --path "$TASK_BUNDLE" --agent oracle --env modal \
  --jobs-dir "$BASELINE_RESULTS" --job-name step1-oracle
```

The no-op should earn zero through ordinary failed checks. The oracle's live
reward is measured, not assumed to be one. Infrastructure or judge failures
invalidate either run under the same policy described in [Reward formula](#reward-formula).

[Baseline reward checks](checks/test_baseline_rewards.py) exercise this shared
verifier locally with fresh temporary workspaces, real oracle CLI/storage, and
controlled model services. They cover an empty no-op, an oracle with correct
fixture answers, and an oracle whose answers all receive zero. These tests check
the full registry and reward path; they do not replace a fresh-container run on
the 218 retained private questions. Run them with:

```bash
uv run --frozen pytest tasks/swe-m2-ai-engineer/knowledge-work-assistant/checks/test_baseline_rewards.py -q
```

## Research and design

### Starting point for iteration

The initial Orange experiments used HERB's corpus and agent harness with Jina
v5 omni small embeddings. Both Luna and Sol completed the baseline run. The
gold-evidence experiment below identifies evidence access as a major bottleneck: Sol's score rose from 44.36 to 90.81 when
given the cited sources and relevant employee/customer directory records directly.

Use Luna for routine iteration and Sol as a comparison when a change looks
promising. Luna finished this run faster; Sol scored 2.28 points higher. These are
single runs with an LLM judge, so that difference needs repeat measurements before
we treat it as a reliable model advantage.

Start with reliable access to directory metadata and fixes for the two role-tool
defects found in HERB. Then measure changes to retrieval and context delivery,
keeping the corpus, generation settings, and judge fixed. Retain the gold-evidence
run as a diagnostic comparison for answers that still score poorly. Track request
failures separately so we can distinguish system reliability from answer quality.

### Measured baseline

These experiments predate the packaged SGLang service and fixed GPT-5.4 judge
described below. Their corpus counts and scores refer to the experimental harness.

The comparison completed on 12 November 2026. Both models answered all 238 HERB
content questions against the full corpus, with no missing answers.

| Generation model | Mean score /100 | Median score | Generation time | HTTP 400 responses |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Luna | 42.08 | 35 | 20m 34s | 5 |
| GPT-6.1 Sol | 44.36 | 40 | 27m 52s | 2 |

The score is the upstream GPT-4o judge's rating of accuracy, completeness, and
relevance against a reference answer. It is an average rubric score, not a
percentage of questions passed. The evaluator does not check generated citations
against source documents.

Generation times exclude indexing and grading. Both runs used five question
workers and ran concurrently. HERB's built-in fallback handled the request
failures; those answers remain in the scores.

### Gold-evidence diagnostic

On 12 November 2026, we reran Sol on the same 238 content questions with the same
generation settings and upstream GPT-4o grader. Every dataset citation resolved
to a source in its owning product. The experimental retriever returned all chunks
from those sources, without a top-k limit. Reference answers went only to the
grader; Sol received source records and the question.

| Sol configuration | Mean score /100 | Gain over baseline |
| --- | ---: | ---: |
| Jina retrieval with HERB's agent | 44.36 | 0.00 |
| Cited evidence with unchanged HERB agent | 74.80 | +30.44 |
| Cited evidence with direct answering | 74.66 | +30.31 |
| Cited evidence and directory records with direct answering | 90.81 | +46.45 |

The agent condition kept HERB's tools, ten-iteration limit, finish check, and
fallback. It used the fallback on 110 questions. Direct answering used HERB's
existing `RetrieverQueryEngine` answer-synthesis path, bypassing the agent loop
and finish check. The final condition also supplied original employee/customer
directory records selected from product membership and identities in the evidence.
All three conditions completed every question, and an audit of the outgoing Sol
requests confirmed that every selected evidence chunk appeared in the model inputs.

Replacing retrieval recovered 30.44 points while preserving the agent harness.
Adding directory records to direct answering recovered another 16.14 points.
For example, two CollaborateForce questions about Engineering Lead and QA
Specialist recommendations each rose from 20 to 95 once Sol could identify the
employees' roles. With directory records, 209 answers improved over baseline,
25 tied, and four scored lower.

Two upstream role-tool defects help explain why this information is difficult
to obtain through the harness. `role_to_id_search` formats a prompt containing
`{text}` without supplying that field, raising `KeyError` before the helper call.
`id_to_role_search` builds an ID-to-role mapping but returns its keys, so the
caller receives employee IDs instead of roles. We reproduced both defects
separately and left them unchanged for the experiment.

These gains measure evidence access broadly. The oracle also removes unrelated
search results and supplies cited PR records directly, so the improvement cannot
be assigned entirely to vector retrieval. The near-equal agent and direct scores
are a single-run observation; they do not establish that agent behavior is
irrelevant. The remaining 9.19 points below 100 include generation errors,
possible gaps or inconsistencies in the evidence and references, and judge
behavior. We have not measured a causal percentage for each source of error.

### Experimental configuration

- Corpus: 34,403 source records, split into 34,531 chunks. The effective splitter
  settings were 1,024 tokens with 200 tokens of overlap. The upstream splitter
  uses these defaults despite the CLI's chunk settings.
- Embeddings: `jinaai/jina-embeddings-v5-omni-small`, revision
  `950200abde3a3bcf3d5bdfe5d28fb5bb5e7dfbb0`, using its text-only retrieval
  adapter, query/document prefixes, and normalized 1,024-dimensional vectors.
  The index was built on a Modal L4. The deployment prefers L4 with A10 fallback.
- Retrieval: top 20 BM25 results plus top 20 vector results, deduplicated, with
  no reranker.
- Agent: HERB's ReAct harness and metadata tools, one attempt per question,
  at most ten agent iterations, and its existing fallback behavior.
- Generation: OpenAI Responses API, medium reasoning, temperature 1, and a
  16,384-token output cap per request. Request timeout was 180 seconds, with
  previous-response tracking disabled.
- Helpers and evaluation: the upstream GPT-4o metadata helpers, finish check,
  and content evaluator.
- HERB revision: `db3bf9b3f911745726c579c9dbf9f7f6b2c05b36`.

Use Responses for these models. Sol repeatedly timed out through Chat Completions,
including with a 600-second timeout. A separate diagnostic on the same HERB
prompt consumed all 4,096 allowed output tokens as reasoning and returned no text
through Chat Completions; Responses returned text in seven seconds. The final
comparison reran both models through Responses. Earlier runs and diagnostics are
excluded from the table.

### What this establishes for the task

These experiments provide a measured starting point for improving the assistant.
All 238 questions are public, and the runs used the full HERB corpus available to
the experimental harness. They do not validate a private evaluation split or the
early step targets of 80% and 95%. The current verifier defines partial-credit
scoring and checks citation validity, but its threshold still needs calibration
on the task's actual corpus with the fixed judge. Step 1 now asks for an optimized assistant without a numerical success target. Full
calibration with the fixed answer and citation judges remains outstanding.

### Research artifacts

The local HERB checkout and run artifacts are gitignored. These links resolve in
the development workspace; the files are not included in the tracked task.

- [Comparison results](../../../HERB/code/local-run/jina-responses-comparison/summary.json)
- [Configuration and provenance](../../../HERB/code/local-run/jina-responses-comparison/manifest.json)
- [Luna answers and scores](../../../HERB/code/local-run/jina-responses-comparison/gpt-6-luna/scored-answers.json)
- [Sol answers and scores](../../../HERB/code/local-run/jina-responses-comparison/gpt-6.1-sol/scored-answers.json)
- [Gold-evidence comparison and paired scores](../../../HERB/code/local-run/sol-gold-evidence/comparison.json)
- [Gold-evidence agent and direct summaries](../../../HERB/code/local-run/sol-gold-evidence/summary.json)
- [Directory-augmented answers and scores](../../../HERB/code/local-run/sol-gold-evidence-with-metadata/oracle_direct-scored-answers.json)
- [Gold-evidence configuration](../../../HERB/code/local-run/sol-gold-evidence/manifest.json)
- [Directory-augmented configuration](../../../HERB/code/local-run/sol-gold-evidence-with-metadata/manifest.json)
- [Role-tool reproduction results](../../../HERB/code/local-run/sol-gold-evidence/tool-audit.json)
- [Gold-evidence runner](../../../HERB/code/run_gold_evidence.py)
- [Comparison runner](../../../HERB/code/run_jina_comparison.py)
- [Modal embedding service](../../../HERB/code/jina_modal.py)

The `citations` field in the exported results contains the dataset's reference
citations. It is not a record of verified citations produced by the assistant.

## Build and deliver

`tasks/swe-m2-ai-engineer/knowledge-work-assistant/` contains the Harbor task sources: `task.toml`, agent image inputs under `environment/`, the candidate instruction at `steps/01-build-rag/instruction.md`, and the verifier under `steps/01-build-rag/tests/`. Run the generated bundle with Harbor or Oddish; packaging stages the GPU build inputs and gives the task directory its declared name. The candidate reads the instruction and works in the agent image. The separate verifier image receives `tests/`, including the private evaluation inputs.

This task directory also contains the development README, maintained tests in
`checks/`, preparation and packaging scripts in `scripts/`, and development
dependencies in `pyproject.toml` and `uv.lock`. The root project depends on these
tools for local commands. Container dependencies remain in
`environment/pyproject.toml` and `steps/01-build-rag/tests/pyproject.toml`.

`scripts/prepare_data.py` generates the public corpus and private cases in their
runtime input directories. `scripts/package_step.py` selects only deployable
files and writes bundles under `experiment/dist/`. Keep calibration reports,
trial outputs, and scratch work under the Git-ignored `experiment/` directory.
The task README, checks, scripts, development dependencies, and experiments are
excluded from the runtime bundle. Paths below are relative to this task unless
a command explicitly starts at the repository root.

Complete the [shared setup](../../../README.md#local-setup-and-checks), then run
these task-specific commands from the repository root:

```bash
uv run --frozen python tasks/swe-m2-ai-engineer/knowledge-work-assistant/scripts/prepare_data.py --herb HERB
uv run --frozen pytest -q
uv run --frozen python tasks/swe-m2-ai-engineer/knowledge-work-assistant/scripts/package_step.py
```

Preparation uses the local `HERB/` checkout and verifies its pinned Git revision.

The archive is `tasks/swe-m2-ai-engineer/knowledge-work-assistant/experiment/dist/knowledge-work-assistant-step1.tar.gz`, with a SHA-256 file
beside it. It contains a complete step-1 task, including prepared sample data and
private verifier inputs. Extract it and pass the `swe-m2_ai-engineering_knowledge-work-assistant/`
directory to Oddish. It does not need the author's source downloads or virtualenv.
The packaging script derives that directory name from `[task].name`; the repository
folder keeps its shorter name. `[metadata].reward_type` declares the continuous reward.
`BUNDLE_MANIFEST.json` records the hash of every included source/input file.
The packaged folder contains only `task.toml`, `environment/`, `steps/01-build-rag/`,
and that manifest. Authoring scripts, local checks, and author dependency files stay
outside it. Generate Oddish upload code when needed, outside the artifact folder.
Packaging also stages the canonical GPU runtime inputs under the verifier's
`tests/gpu-runtime/` build context. Launch the packaged task, rather than the
source directory: Harbor builds each Dockerfile from its own directory and
cannot copy sibling environment files. The manifest covers these staged copies.

Source preparation pins `SalesforceAIResearch/HERB` at
`db3bf9b3f911745726c579c9dbf9f7f6b2c05b36` and records source-file hashes.
It generates ignored files under `environment/data/`, `environment/resources/corpus/`, and
`steps/01-build-rag/tests/private/`. Prepare those before building or publishing
the task. Git ignores these generated files; Harbor still needs to upload the
private files to the separate verifier. Do not exclude them from a verifier upload.

The development project pins upstream Harbor to
`feea734de84bf2479b329dc6315a6d98d1596f4f` (0.25.0). The task also passes the parser
from Oddish's pinned revision `8ea3df67962fdd8d590c6044e060151756cdc326`.
The agent image has Python 3.12 and its own locked runtime dependencies. Keep local
virtualenvs outside `environment/`: Harbor validates uploaded paths and rejects
external interpreter symlinks even when Docker would ignore them.

The image provides standard installation dependencies, including Node/npm, curl,
Git, Bash, and Python/uv. It does not bake in a coding harness, model-specific
solver, or reference solution. Oddish selects and installs the coding harness.
The application, generated code, and index are transferred through the standard
`artifacts = ["/app"]` contract; grading does not import a harness SDK.

Sampling uses Python's seeded sampling without replacement over all source records.
It is not stratified by source type. Each corpus record contains only `doc_id`,
`source_type`, `title`, and `content`. Original IDs are preserved except for the
four additional colliding records described in the development log. References,
question categories, answerability modes, and alias provenance stay private.
The manifests record source hashes, generated-file hashes, and the sampling seed.

## Verification

Harbor's [separate verifier](https://github.com/harbor-framework/harbor/blob/main/docs-mintlify/tasks/separate-verifier.mdx)
builds a distinct image from `steps/01-build-rag/tests/Dockerfile`, starts a fresh
GPU container, transfers `/app`, and invokes `/tests/test.sh`. Tests and private
inputs are baked into that image; Harbor does not upload them at runtime when a
dedicated verifier Dockerfile is present. The adapter calls
`verify(context: VerificationContext) -> VerificationResult`.
Its explicit registry attempts every named requirement check independently. A wrong
field description or incomplete help text fails its own check without skipping
CLI, ingestion, or retrieval checks. Each check prepares its own inputs and reports
any execution failure it encounters. Judge and infrastructure errors still invalidate
evaluation rather than become candidate failures.

Both environments request one L4 GPU on Modal. SGLang 0.5.9 serves the merged
`jinaai/jina-embeddings-v5-text-small-retrieval` checkpoint at revision
`6856e76bb72982e58de0620458a4e8b3614da340`. This is Jina's text-retrieval tower;
image, audio, and video encoding are not exposed by this task. The first `embed`
call starts a detached local service, and later CLI processes reuse it. Query and
document prefixes, last-token pooling, and normalized 1,024-dimensional vectors
are preserved. The service uses BF16 and batches requests on the GPU.

The CUDA development image supplies the compiler needed by SGLang's kernels.
Weights and dependencies are installed during the build. Runtime inference uses
localhost only, including in the fresh verifier; no embedding-service host needs
to be added to the external network allowlist. The service receives no API keys.

Development and verifier policies allow only `api.openai.com`, from container
startup through execution. Packages and coding harnesses that require public
downloads must be provisioned before development starts. The submitted app must
keep any local dependencies under `/app` so they survive the transfer. The fresh verifier inherits no development processes,
temporary files, or changes outside the declared artifacts.

Modal enforces this allowlist on TLS hostnames, not individual API paths or model
names. Its [network policy documentation](https://modal.com/docs/guide/sandbox-networking)
also notes that DNS remains available and domain fronting is not prevented by the
allowlist alone. This is restricted model-service access, not a completely offline
container or a guarantee against every possible exfiltration channel.

| Requirement | Test |
| --- | --- |
| Required async function and Pydantic model source declarations | `test_interfaces` |
| Executable help | `test_cli_help` |
| Answering before ingestion fails | `test_answer_before_ingestion` |
| Ingest API and persistence across processes | `test_ingestion_and_persistence` |
| Complete corpus persisted after the end-to-end CLI refresh | `test_full_corpus_persistence` |
| Skip existing IDs while adding new documents | `test_duplicate_documents` |
| Refresh changes content and removes absent IDs | `test_refresh_replaces_index` |
| CLI calls the public functions; generation calls retrieval | `test_required_call_paths` |
| At most 50 retrieval calls per question | `test_retrieval_budget`; enforced on every held-out CLI answer |
| Multiple question files and JSON answer arrays | `test_cli_question_files` |
| JSON questions on stdin, preserved IDs, EOF, and JSON array output | `test_cli_stdin` |
| bm25 returns nonempty passages from a fresh ten-document corpus | `test_bm25_behavior` |
| embed returns nonempty passages from a fresh ten-document corpus | `test_embed_behavior` |
| hybrid returns nonempty passages from a fresh ten-document corpus | `test_hybrid_behavior` |
| Progress file exists | `test_progress_file` |
| Held-out answer quality and citation validity | `test_holdout_accuracy` |

The verifier unconditionally clears transferred index state. Its first registered
check refreshes the private corpus using `orange ingest --path ... --refresh`. It then asks all 218 retained content questions
using `orange answer --questions ... --output ...`. Accuracy never invokes the
application's Python functions directly and does not depend on an interface-check
pass. Later functional checks use their own small corpora.

`test_accuracy.py` runs the answer judge first for each question. It receives
only the question, reviewed example answer, must-have list, required indices,
and candidate answer. Source documents and citation objects are excluded.

`AnswerRating` contains one structured decision per criterion: its index,
`passed` / `failed` / `not_applicable` status, an exact candidate excerpt,
reason, and an optional reference to an earlier duplicate error. The model does
not return an aggregate score or verdict. The verifier checks complete index
coverage, mandatory applicability, exact candidate evidence, and duplicate-error
references. Invalid decisions use the same three structured-output retries as
schema violations; exhausted retries invalidate evaluation.

Let **R** be passed required items divided by all required items. Let **C** be
passed conditional items divided by applicable conditional items: all conditional
items except those marked `not_applicable`. Required and applicable conditional
items are normalized within their own groups, so the number of optional details
does not determine their weight.

The verifier environment configures `ORANGE_EVAL_REQUIRED_WEIGHT = "0.8"` and
`ORANGE_EVAL_CONDITIONAL_WEIGHT = "0.2"`. Both are required, finite, in [0, 1],
and must sum to one. They are parsed once into `AnswerScoringConfig`, passed to
the judge adapter, and recorded under `scoring_config.answer_criteria` in the
report. These weights are separate from the answer/citation and quality/contract
weights. They are not forwarded to candidate processes.

The answer fraction **A** follows this rule:

- If **R = 0**, **A = 0**, regardless of conditional successes.
- If no conditional item applies, **A = R**.
- Otherwise, **A = (w_required × R + w_conditional × C) /
  (w_required + w_conditional)**, which is **0.8R + 0.2C** at the declared weights.

Every applicable conditional rubric item counts once. `duplicate_of` records
shared error evidence for auditing; it no longer removes an item from scoring.
Absent and uncheckable conditional claims are excluded. Unverified additions
outside the rubric remain audit notes. Missing or empty answers receive zero.
Scores retain full precision before the citation gate. Python derives incorrect
at zero, correct at one, and partial otherwise; the model still returns decisions
only. Per-question reports include both component fractions and their counts.

At the current weights, passing all required items and failing every applicable
conditional item gives 80%, which can pass the unchanged 75% citation gate.
This is the intended consequence of capping conditional influence at 20%.

Both production judges use PydanticAI 2.68.0 with
[`NativeOutput(..., strict=True)`](https://ai.pydantic.dev/output/#native-output).
The Responses API receives the strict JSON Schema generated from `AnswerRating`
or `CitationRating`. Decision guidance belongs in the output field descriptions.
Roles are supplied through `system_prompt`; both main judge prompts use
Evaluation Guideline, Rubric, and Criteria, with input sections beginning at
Questions. Citation grading keeps its three bands, 0, 0.5,
and 1, and its structured material-claim assessments. No supported material
claims means zero citation credit. Extra fields, invalid indices, invented
candidate excerpts, and incompatible status assignments are rejected.

The answer template exposes `{question}`, `{reference_answer}`, `{candidate_answer}`,
`{rubric}`, `{required_indices}`, `{question_type}`, and `{evidence_mode}`.
Private `rubrics.json` retains the original question/reference association and
adds a source-reviewed example, explicit required/optional partition, and exact
source grounding. The loader checks its manifest hash, complete question
coverage, original associations, quoted anchors, nonempty core, and disjoint
index partition. Data preparation preserves these curated rules; clean builds
supply them through `--rubrics`. None of this is candidate-visible.

The reference remains an example, not a completeness checklist. The core accepts
supported alternatives; optional conditions constrain claims actually made.
A correct nonexhaustive list can earn full credit, while a demonstrably false
claim that it is exhaustive can incur an error. Source records are retained for
author review; only citation judging receives complete cited originals. Citation
support does not require matching gold document IDs.

For information-not-found cases, trusted dataset labels establish when abstention
is appropriate, following the separation of abstention detection from correctness
in [AbstentionBench](https://arxiv.org/html/2506.09038v1). An empty gold set alone
never implies unanswerability. False abstention on answerable questions is incorrect;
for unanswerable cases, unsupported specific answers must not earn correctness
credit. Pure, fully correct abstention needs no fabricated evidence of corpus-wide
absence. These are adaptations using our existing output schemas, not reproductions
of the papers' metrics or their reported validation.

The citation template exposes `{question}`,
`{candidate_answer}`, `{citations}`, and `{documents}`. The loader splits at
`## Inputs`: Goal and Criteria become trusted agent instructions, while the input
section becomes the user message. Each value is JSON-encoded before a single
formatting pass, preserving lists, full documents, literal braces, and newlines.
Missing or unused fields fail rather than silently dropping evidence. Reported
prompt hashes cover the complete Markdown templates, including placeholders.

The answer procedure adapts the reference-based, rubric-specific assessment in
[Prometheus](https://arxiv.org/abs/2310.08491) and its
[published prompt](https://github.com/prometheus-eval/prometheus-eval/blob/main/libs/prometheus-eval/prometheus_eval/prompts.py):
compare the response with a reference, stay within the supplied criteria, and
justify the rating. The citation procedure adapts the claim decomposition and
context-support checks in [RAGAS, section 3](https://aclanthology.org/2024.eacl-demo.16.pdf).
Here those checks guide one citation judgment over quotations and complete original
documents. These are adaptations: Prometheus's 1–5 output and RAGAS's separate
statement calls and supported-statement fraction are not used. The answer score
is computed from criterion decisions; citation support retains these bands:

| Citation score | Meaning |
| ---: | --- |
| 0 | No material claim supported, or cited context contradicts the central answer |
| 0.5 | Some material claims supported; full support not established |
| 1 | Every material claim made is supported by citations in context |

Optional completeness is not scored. Accuracy grading records uncheckable extras
without treating their absence from the rubric as evidence of falsity. Citation
grading checks all material claims against their cited originals. Consequently,
a closed correctness rubric cannot guarantee the truth of arbitrary extra claims
outside its reviewed facts. Source-based oracle audits and adversarial controls
check for observed gaps; neither constitutes a proof of universal judge reliability.

Reports record prompt and schema hashes, criterion counts and decisions, unrounded
answer percentages, and citation percentages. The `answer_band` diagnostic key is
retained for compatibility, but now contains the continuous criterion ratio.

`ORANGE_JUDGE_OUTPUT_RETRIES=3` allows up to three structured-output repair retries
after the initial response. A valid rating, including zero, is accepted immediately.
Exhausted retries, refusals, and incomplete responses invalidate evaluation; there
is no model fallback. The SDK separately allows at most two transport retries.
`checks/test_judge.py` exercises the real PydanticAI agents and
OpenAI SDK through an offline HTTP transport, including the outgoing strict schema.

Only an unrounded answer fraction of at least 0.75 can trigger citation judging.
Lower fractions skip that call and receive zero citation credit; their answer
credit is retained. Before
that call, the verifier checks that every quote occurs in its cited source. The
citation judge receives each cited original document in full, including its title,
source type, and content. The verifier fetches these records from its authoritative
corpus and sends each source once, without truncation or candidate substitutions.
The rubric checks quotations against the full context, including negation,
qualifications, and later corrections. Uncited context cannot substitute for a
supporting quotation. Incorrect or missing answers skip citation judging and receive zero
in both components. Missing or invalid citations also skip citation judging and
receive zero citation credit, while retaining the answer score. The calls are
sequential within each question; a provider error invalidates evaluation instead
of becoming an incorrect verdict. These are partial-credit ratings, not a binary
correct-answer rate.

After a valid citation judgment, `judging/citation_scoring.py` validates every
reference and exact evidence excerpt against the supplied citation and original
document. Supported claims need an excerpt inside the candidate's quotation;
contradicting context can come from the complete original. Missing indices,
mismatched IDs, or misplaced excerpts trigger bounded structured-output repairs.
The judge returns claim decisions without a score. Python computes zero when no
material claim is supported, including an empty claim list, or when a central
claim is contradicted. If there is support but another material claim is
unverified or contradicted, the score is exactly 0.5; otherwise it is 1. The judge
assesses assertions the answer maintains, excluding explicitly retracted claims
and omitted optional content.

Each eligible question now makes one full-context citation judgment, followed by
programmatic evidence validation and scoring. There is no quotation-only model
call. The judge must distinguish valid contextual interpretation from support
that exists only in unquoted text; exact excerpts are still checked in Python.

Diagnostics retain the computed `score`, structured `claims`, explanation,
provider response ID, and the applicable scoring-rule marker in `adjustment`.
The score uses the existing 0–100 percentage scale. There is no judge-proposed
score. These checks do not prove the model correctly classified every
claim or included every material claim. The configured 0.75 citation gate remains
in force after the switch to computed answer scores.

Malformed records with identifiable question IDs receive zero for that question;
other answers remain eligible. Duplicate IDs invalidate all records for that ID.
Wrong question text and malformed citation objects also fail only their own
question. Records without usable expected IDs are counted separately, and omitted
expected questions score zero. Each question runs in its own CLI process. Unreadable JSON, a non-array outer
value, a timeout, or CLI failure earns zero only for that question. Ingestion
failure still prevents grading the batch. The quality check's status records output
validity, not whether an answer score crosses a threshold.

### Reward formula

Step 1 averages rewards over all 218 retained private HERB questions. Each question can
earn answer credit, citation credit, and a share of the submission's functional
contract credit. An answer scored zero earns zero total credit for that question,
even when every contract check passes.

Scoring policy comes from the trusted `[verifier.env]` section in
[task.toml](task.toml):

| Environment variable | Configured value |
| --- | ---: |
| `ORANGE_EVAL_QUALITY_WEIGHT` | `0.8` |
| `ORANGE_EVAL_FUNCTIONAL_WEIGHT` | `0.2` |
| `ORANGE_EVAL_ANSWER_WEIGHT` | `0.9` |
| `ORANGE_EVAL_CITATION_WEIGHT` | `0.1` |
| `ORANGE_EVAL_CITATION_MIN_ANSWER_SCORE` | `0.75` |
| `ORANGE_EVAL_QUESTION_CONCURRENCY` | `10` |

The entry point parses these once into an immutable `ScoringConfig`. Missing,
nonnumeric, nonfinite, out-of-range, or unnormalized settings invalidate evaluation.
There are no policy fallbacks in Python. Settings are recorded in the trusted report
and are not forwarded to candidate processes. The question concurrency must be a
positive integer. The judge runs up to ten question pipelines concurrently in one
async event loop. Each pipeline awaits its answer judgment before deciding whether
to call the citation judge. Completed diagnostics retain input question order; a
provider failure cancels unfinished pipelines and invalidates the run.

For question i in trial t, let a_it be the answer score divided by 100. Let c_it
be the effective citation score divided by 100, or zero when citation judging is
skipped. The answer fraction combines separately normalized required and applicable
conditional successes using the configured weights; citation support uses 0, 0.5, or 1. The separate judges
return the structured decisions described in their
[Pydantic output schemas](steps/01-build-rag/tests/verifier/judging/schemas.py).

The answer judgment comes first. Citation judging runs only when the answer fraction
is at least 0.75 and every supplied citation has a known source ID and an exact,
nonempty quotation. Missing citations or an invalid quotation give zero citation
credit while preserving answer credit. The citation judge receives the full
original documents and returns claim assessments and an explanation, with no
score field. Python validates its evidence and computes citation credit directly:
zero if no material claim is supported or any central claim is contradicted;
0.5 if some claims are supported but others are unverified or contradicted;
and 1 if every material claim is supported. Empty claim lists receive zero.
The citation judge does not choose a scoring band, and there is no proposed score to cap.
A structurally malformed citation object instead invalidates that question's
answer record, giving zero answer and citation credit.

For the current HERB questions, the per-question formula is:

```text
F(t) = passing functional checks / all functional checks
R_it = 0                                      if a_it = 0
R_it = 0.8 * (0.9 * a_it + 0.1 * c_it) + 0.2 * F(t)  otherwise
R(t) = sum(R_it for all 218 retained questions) / 218
```

The implementation also supports trusted unanswerable cases. A fully correct,
uncited abstention on such a case keeps diagnostic citation score zero and
reassigns that component to its answer score. Current HERB cases all use gold
evidence, so this exception is inactive. The general formula, including that
exception, is:

```text
z_it = 1 for a fully correct uncited abstention on a trusted unanswerable case, else 0
r_it = 0.9 * a_it + 0.1 * (c_it + z_it * a_it)
R_acc(t) = sum(r_it for every held-out question i) / N
F(t) = passing functional checks / all functional checks
e_it = 1 if a_it > 0 else 0
R_it = e_it * (0.8 * r_it + 0.2 * F(t))
R(t) = sum(R_it for every held-out question i) / N
     = 0.8 * R_acc(t) + 0.2 * F(t) * mean(e_it)
```

N is the total held-out question count (currently 218), including missing answers.
Failed and skipped functional checks remain in the contract denominator. With the
current 15 functional checks, each passing check earns 1/15 of contract credit, awarded only on questions with
a nonzero answer score. An all-zero answer batch earns zero total reward even
when every functional check passes.
`judgments.json` records each answer verdict, both ratings, the citation disposition,
`reward_eligible` (e_it), and `accuracy_reward` (r_it). The trial report records their weighted mean as
`quality_fraction`, the raw contract fraction as `functional_fraction`, the eligible question fraction
as `nonzero_answer_fraction`, and the final reward.

The weights come from environment configuration. At the configured values, answer correctness
accounts for up to 72% of reward, citations 8%, and functional checks 20%. Full reward
requires perfect answer scores, perfect applicable citation scores, and every
functional check to pass.
There is no numerical success target or `min_reward` step gate. Harbor records the
continuous weighted reward; a completed run does not need a perfect reward.
The separate `VerificationResult.passed` flag requires every registered check to
pass. It does not multiply or replace the continuous reward. The accuracy check's
pass status measures output validity, not an answer-quality threshold.

With all 15 contract checks passing, the per-question rewards are:

| Answer band | Effective citation band | Quality component | Question reward |
| ---: | ---: | ---: | ---: |
| 0 | 0 (skipped) | 0 | 0 |
| 0.25 | 0 (skipped) | 0.225 | 0.38 |
| 0.5 | 0 (skipped) | 0.45 | 0.56 |
| 0.75 | 0 | 0.675 | 0.74 |
| 0.75 | 0.5 | 0.725 | 0.78 |
| 0.75 | 1 | 0.775 | 0.82 |
| 1 | 0 | 0.9 | 0.92 |
| 1 | 1 | 1 | 1 |

Moving from an answer band of zero to 0.25 unlocks the question's contract
contribution as well as partial answer credit. This creates the jump from zero
to 0.38 when all checks pass. If all contract checks fail, perfect answers and
citations still earn 0.8.

One perfect answer and one zero-scored answer, with all contracts passing, earn
a mean reward of 0.5 in that two-question example. If the
trial averages 90 for answers and 100 for eligible citations, with no skipped
citation judgments and all functional checks passing, the reward is 0.928.
Perfect answers with zero citation credit and all functional checks passing earn
0.92. Missing, malformed, timed-out, and over-budget answers receive zero for
their question and remain in the denominator. Judge-service or judge-output
failures that exhaust retries invalidate evaluation and produce no valid reward;
they are not counted as incorrect answers.

Implementation and boundary checks:

- [Question grading](steps/01-build-rag/tests/verifier/judging/evaluation.py)
  applies the answer-first citation gate;
  [citation scoring](steps/01-build-rag/tests/verifier/judging/citation_scoring.py)
  enforces zero support. Covered by [accuracy reward checks](checks/test_accuracy_reward.py)
  and [claim checks](checks/test_citation_claims.py).
- [CLI accuracy evaluation](steps/01-build-rag/tests/verifier/checks/test_accuracy.py)
  computes means over every held-out question;
  [the registry](steps/01-build-rag/tests/verifier/registry.py) defines the 15
  functional checks. [Verifier checks](checks/test_verifier.py) cover missing
  answers and judge failures.
- [Reward aggregation](steps/01-build-rag/tests/verifier/scoring.py) applies the
  weights and answer eligibility fraction. [Scoring configuration checks](checks/test_scoring_config.py)
  cover configured weights, failed and skipped contract denominators, and invalid
  settings. These controlled checks establish arithmetic and orchestration;
  judge reliability still depends on the calibration evidence below.

The verifier separates requirement checks, candidate execution, judging, and result
handling. `verify.py` remains Harbor's entry point; it constructs the context and
calls `verifier.runner.verify()`. The registry runs CLI accuracy evaluation before
the functional checks.

```text
steps/01-build-rag/tests/
├── test.sh
├── verify.py                    # Harbor setup and exit handling
├── private/                     # Private corpus, questions, and manifest
└── verifier/
    ├── contracts.py             # Shared types and errors
    ├── config.py                # Validated verifier environment settings
    ├── registry.py              # Ordered checks and prerequisites
    ├── runner.py                # Execution and dependency skips
    ├── scoring.py               # Pure reward aggregation
    ├── inputs.py                # Private-input loading and hash checks
    ├── reporting.py             # Diagnostics and reward files
    ├── checks/
    │   ├── support.py           # Scenario fixtures and strict contract validation
    │   ├── accuracy_inputs.py   # Per-question validation for partially malformed batches
    │   ├── test_interfaces.py
    │   ├── test_retrieval.py    # Independent per-method behavior checks
    │   ├── test_cli.py
    │   ├── test_storage.py
    │   ├── test_accuracy.py
    │   └── test_progress.py
    ├── application/
    │   ├── client.py            # CLI/probe adapter and workspace artifacts
    │   ├── source.py            # Trusted source parsing; never imports candidate code
    │   └── process.py           # Identity, timeouts, output limits, cleanup
    ├── judging/
    │   ├── client.py            # Typed PydanticAI agents and prompt loading
    │   ├── schemas.py           # Strict provider-output models and validation
    │   ├── answer_prompt.md     # Accuracy judge instructions
    │   └── citation_prompt.md   # Citation judge instructions
    └── probes/
        ├── test_application.py  # Candidate API execution and call tracing
        └── test_chroma.py       # Stored document/vector inspection
```

Checks share helpers without importing one another. Candidate probes are
self-contained because the candidate UID cannot import private verifier files.
The interface check reads `main.py` as bounded source data and inspects its syntax
tree in the trusted verifier. It checks the published model fields, literal
descriptions, type alias, and async signatures, allowing additional model fields,
qualified imports, and forward annotations. It never imports the application,
executes its interpreter, or accepts stdout as proof of interface compliance.
The old `interfaces` subprocess probe is removed.

This establishes the declared source contract, not the runtime behavior of
arbitrary Python. Decorators, dynamic namespace changes, and import side effects
are not executed or proven safe by static inspection. Separate CLI and storage
checks establish observed behavior. Remaining runtime probe records have strict
outer schemas, but their contents and internal call traces remain untrusted.
The packaging check runs the complete controlled verifier from an extracted
bundle in an isolated Python process, including its relocated probes and prompt.

Chroma 1.5.9 is pinned in the client and service locks. A protected CPU service
holds the `documents` collection with original IDs, complete bodies, and vectors.
Storage checks use the trusted interpreter and HTTP API with 100-record pages,
compare UTF-8 body SHA-256 hashes and exact live IDs, and reject chunks belonging
to removed documents. They remove the ingestion input to check persistence, then
clear both the service and auxiliary state to check empty-index behavior. These
checks do not prove forensic deletion, absence of all undeclared caches, or that
no alternative index is used.

The candidate receives a version-matched offline Chroma API reference through
`environment/resources/chroma-api.md`; the Docker build checks its version heading
against the installed package. No grading details appear in that reference.

The judge is fixed in code to `gpt-6.1-sol`, Responses API, high reasoning,
with separate answer and citation agents. Both use strict native Pydantic output
schemas. There is no model override or fallback. Keep complete evidence records
in each request; do not silently truncate evidence. The earlier GPT-5.4 and
GPT-6 Luna calibrations remain in the author artifacts for comparison. Their
results do not establish GPT-6.1 Terra's behavior.

The trusted report records the model, reasoning setting, structured-output mode,
the dataset revision, hashes of both prompts, and both output schemas (including band
guidance), input hashes, and per-check results.
Per-question diagnostics record scores, reasons, answer verdicts, and citation skips. Provider failures invalidate
the run, preserve completed diagnostics, and remove any stale reward files.

## Credentials and process boundary

The agent and verifier have distinct images built from the same CUDA base and
locked Jina/SGLang runtime inputs. Evaluation never runs in the agent image.
Both images provide `/opt/application` with PydanticAI 2.68.0, OpenAI 3.49.0,
and Chroma 1.5.9, locked in `environment/application/`. It is the default Python
runtime for candidate code and the oracle. `/opt/runtime` remains the isolated
GPU environment with SGLang's OpenAI 2.6.1 dependency; the Jina helper starts its
server with that interpreter. Only the verifier image adds `/opt/verifier`, whose
judge dependencies are declared in `steps/01-build-rag/tests/pyproject.toml` and
its lockfile. `tests/test.sh` launches
`/opt/verifier/bin/python -I /tests/verify.py`. Chroma is pinned to 1.5.9 in all three
environments so the trusted storage probe can inspect the application's database.
An application's own `/app/.venv` still takes precedence for its API probes.

Oddish supplies its platform `OPENAI_API_KEY` through the supported task credential
resolver; no personal provider key needs to be uploaded. Oddish resolves
this supported source from its platform settings. `task.toml` maps it to:

- `ORANGE_JUDGE_API_KEY`: verifier-only judge variable.
- `ORANGE_OPENAI_API_KEY`: application credential for `gpt-6-luna`.

`task.toml` exposes `ORANGE_OPENAI_API_KEY` to the application so a coding harness's
`OPENAI_API_KEY` cannot overwrite it. The runner uses its own Modal credentials to
create the GPU containers; those credentials are not exposed inside them.
The verifier receives its judge key separately and
passes only the explicitly allowlisted application variables to candidate processes.
Credentials are never baked into images or written to the task files.
The chosen coding harness's credentials are supplied separately by Oddish.
The agent has a 4-hour limit. The verifier has a separate 28-hour limit, declared
at both root and step level. After CLI refresh ingestion, it runs up to ten
single-question CLI processes against the shared index. Each receives 1,800 seconds
from launch; queue time does not count. For 218 questions, 22 waves take at most
11 hours within the existing 12-hour answer-generation budget. `ORANGE_EVAL_INGEST_TIMEOUT_SEC=14400` permits four hours for
full-corpus CLI ingestion. Seven hours cover the functional checks' answer
deadlines; five hours are reserved for judging, storage checks, and overhead.
These allocations guide the overall cap; nested retries can still exhaust it. Functional answer checks use the same 30-minute allowance per question,
with batch deadlines scaled by their question count.
Answer generation completes before the existing ten concurrent judging pipelines
run; citation judging remains conditional on the answer score.

`ORANGE_EVAL_GENERATION_CONCURRENCY=10`,
`ORANGE_EVAL_GENERATION_TIMEOUT_SEC=1800`, and
`ORANGE_EVAL_MAX_RETRIEVAL_CALLS=50` are required verifier environment settings.
They are parsed once into `GenerationConfig` and recorded in the report. Each
process has distinct JSON input/output paths, and failed process groups are killed.
A process can submit answers only for its assigned question. `generation.json`
records accepted answers and per-question failures in the trusted verifier logs.

For a direct Harbor run outside Oddish, supply `OPENAI_API_KEY` and the selected
harness's credentials, then run the extracted task with the standard CLI:

```bash
MODAL_ENVIRONMENT=testing uv run --frozen harbor run \
  --path /path/to/extracted/knowledge-work-assistant \
  --agent "$HARNESS" --model "$CODING_MODEL" --env modal
```

The verifier runs as root and the submitted app as UID/GID 10001. `/tests` and
`/logs/verifier` are restricted to the verifier. Application subprocesses have
deadlines and bounded captured output. CLI call-path checks launch `/app/orange`
itself and collect Python startup-hook observations from that execution, including
shell launchers forwarding to Python. They do not run `cli.py` as a substitute.
If the launcher disables Python startup hooks, tracing is unavailable and this
check cannot establish the call path; it fails rather than silently bypassing the
launcher. Trace files and imported aliases remain candidate-process observations,
not authenticated evidence against deliberate instrumentation evasion.

Immediately after the end-to-end CLI run, a separate functional check inspects
the full persisted corpus before any small fixture replaces it. It compares exact
IDs and body hashes, requires finite nonzero vectors, and rejects stale chunk
owners. It never reingests to repair a partial index. Answer-quality failure does
not skip this storage check. Each retrieval method then has an independent
behavior test: clear state, ingest ten documents with the real executable and
`--refresh`, and require nonempty passages for an answerable query. These checks
do not grade ranking or distinguish algorithm internals; retrieval quality remains
part of the end-to-end answer evaluation.

## Validation and remaining work

Local author checks use a deterministic Chroma fixture application
and controlled judge responses. They cover the
complete registry, targeted broken submissions, full-denominator scoring, malformed
judge responses, dependency skips, and stale reward cleanup. These fixtures are
not oracle solutions and do not establish the answer quality of an actual RAG system.
The verdict extension and conditional citation flow have controlled-test coverage,
including SDK transport tests for native schemas, invalid outputs,
verdict consistency, refusals, and incomplete responses.

A live calibration on 14 November 2026 used three private questions and controlled
answer variants, with two repetitions: 72 answer judgments and 50 citation judgments.
The production 0.75 gate matched every observed call, including nine at the boundary;
all 22 below-threshold answers skipped citation judging. Relevant supported additions
received 1.0 from both judges in all six follow-up cases. Calibration also exposed
undeserved partial credit for wholly contradictory answers and irrelevant citations,
unstable treatment of unverified additions, and missing role-identification evidence
in the answer judge's context. These are unresolved semantic issues. See the
[private local calibration report](experiment/artifacts/judge-calibration-2026-11-14/report.md)
and [reusable runner](scripts/calibrate_judges.py). Generated fixtures and results
are ignored by Git; expectations have not been independently human-reviewed.

The updated Chroma runtime image and the full RAG evaluation still need container
and model validation. The judge calibration ran in fresh CPU containers with a
controlled replay CLI; earlier GPU/container results below predate these changes.

A prior Modal Linux runtime passed all 11 registered checks with the verifier,
controlled application, and controlled judge. It verified that
candidate UID 10001 could neither read `/tests/verify.py` nor write the reward,
and did not inherit the synthetic judge credential. Its entry point is
`checks/smoke_container.py`; its fixture modules belong only in the smoke image.
This was an adapter/process-boundary check, not a complete Harbor agent trial.
An earlier Harbor no-op trial built the then-current Dockerfile and completed with
zero exceptions and reward zero for an empty submission, exercising the separate
verifier, private-input upload, and reward collection. Coding-harness installation
and model trials are left to Oddish.
A fresh Modal L4 container produced a normalized 1,024-dimensional Jina vector as
UID 10001 with `block_network=True`, no credentials, and the verifier's restricted
process environment. This establishes that embedding inference uses the bundled
weights and GPU without downloads. A prior live `gpt-6-luna` Responses check also
completed successfully.

A controlled Harbor run completed in 56 seconds with no evaluation exceptions.
It compared Modal container IDs, restored a declared `/app` marker, and confirmed
an undeclared `/tmp` marker was absent. As UID 10001, it generated query and document
embeddings locally, reached the approved OpenAI API (401 without credentials), and
could not connect to the tested HTTPS destinations `example.com`, `huggingface.co`,
`pypi.org`, or `1.1.1.1`, or to plain HTTP at `example.com`. The unchanged production
verifier then accounted for all 11 checks and correctly gave the empty submission
reward zero. `checks/smoke_environment.py` contains the boundary probes.
This control overrode the GPU type to A10 after L4 startup stalled; the delivered
configuration retains L4, whose offline embedding inference passed separately.

A five-answer live smoke check on the fixed judge scored correct/wrong/partial/
unsupported-extra-claims/prompt-injection examples at 100/0/65/82/0. The score of 82
shows that the inherited rubric can still reward an otherwise correct answer with
unsupported additions. A single example of each kind is not a calibration study.

The 2026-11-14 GPT-6 Luna High recalibration completed 72 answer judgments and
51 conditional citation judgments on variants of three private questions. All six
fully contradicting answers scored zero. In the follow-up with complete role
citations, all six supported-extra-detail answers scored 1 for both components.
The 0.75 gate held in every case, and baseline groups reached ten concurrent
requests. Irrelevant citations still received 0.25 in five of six cases, and
unverified additions varied between answer scores 0.5 and 0.75. See the
[calibration report](experiment/artifacts/judge-calibration-luna-high-2026-11-14/report.md)
for distributions, comparisons, and limitations.

A matched rerun with the lower-band tie-break instruction did not resolve either
issue: unverified extras still split three times at 0.5 and three at 0.75, and
five of six irrelevant citations still earned nonzero credit, including one at
0.5. All six supported-extra follow-up answers retained full answer and citation
credit. The 72 answer and 51 citation calls completed successfully with the gate
intact. The [lower-band comparison](experiment/artifacts/judge-calibration-luna-high-lower-band-2026-11-14/report.md)
records the unchanged inputs, exact prompt change, and remaining limitations.

Structured citation assessments and deterministic zero-support enforcement then
reduced nonzero credit on irrelevant citations from five of six cases to zero of
six. The verifier overrode five raw 0.25 proposals. All six supported-extra
follow-up cases retained full answer and citation credit. One correct-answer
control lost citation credit because the model joined the wrong employee record;
answer-judge variability also remains. The run completed 72 answer and 52 citation
judgments, and all 214 local author checks passed. See the
[structured-claim comparison](experiment/artifacts/judge-calibration-luna-high-claims-2026-11-14/report.md)
for the raw/effective scores and remaining errors.

The progress check establishes only that a progress file exists. It does not
validate development experiments or question authorship, and it does not attempt
to establish when the application interfaces were written. The full final corpus includes the public sample; it is the Q&A
set that is held out. HERB itself is public, so withheld files do not establish
absence of model pretraining contamination.

A baseline oracle is now available with controlled functional validation, as
recorded in the development log. A fresh-container run on all 218 retained questions with
the fixed judge, and broader calibration beyond the four selected source questions, remain
separate work.

The current data source is HERB again. Its upstream license and transformation
provenance are recorded in the private manifest. Earlier EnterpriseRAG calibration
results are retained as historical experiments and do not measure this corpus.

## SGLang performance

On 2026-11-12, both helpers were measured on a Modal L4 with four CPUs, 16 GB of
host memory, and external networking blocked. The benchmark uses 20 warm queries,
three disjoint batches of 128 development records, and 16 concurrent queries.
`checks/benchmark_jina.py` contains the workload.

| Measurement | Previous helper | SGLang helper |
| --- | ---: | ---: |
| Warm query, median | 159.1 ms | 22.5 ms |
| Warm query, p95 | 172.3 ms | 24.3 ms |
| Corpus records/second, median | 37.3 | 111.7 |
| 16 concurrent queries, total | 2.376 s | 0.064 s |
| First call, including startup | 25.4 s | 72.6 s |

SGLang stays resident after the calling process exits. A second CLI process reused
the same server PID and returned an embedding in 1.10 seconds, including its
one-time readiness check. Warm calls reuse HTTP connections and skip that check.
The first call includes local kernel compilation, so cold startup is slower.

Five texts, including empty input, multilingual text, and a longer passage, were
compared in both query and document roles. All ten vector comparisons had cosine
similarity above 0.99987 against the previous Omni helper. Full HERB answer quality
has not been rerun for this serving change. The runtime check used the CUDA task
image with Python development headers added as a layer; the Dockerfile now
installs those headers directly.

On 2026-11-13, a controlled Harbor run built the exact task Dockerfile and ran
`checks/smoke_environment.py` in both the agent and separate verifier containers.
Both used an NVIDIA L4 and SGLang 0.5.9, and produced normalized 1,024-dimensional
query and document embeddings as UID 10001. No separate embedding deployment or
agent-side package installation was needed; the bundled helper started the service
on its first call in each container.

The verifier had a different container ID, restored the declared `/app` artifact,
and had no undeclared development marker from `/tmp`. It reached `api.openai.com`
with an unauthenticated 401 response and could not reach the tested non-approved
HTTPS or HTTP destinations. The control completed without evaluation exceptions.
Its reward records infrastructure checks only; full RAG answer-quality evaluation
remains outstanding. The check used synthetic, unused API-key values and made no
paid model calls.
