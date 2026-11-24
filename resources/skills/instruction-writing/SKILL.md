---
name: instruction-writing
description: Write or revise candidate instructions as realistic professional requests with clear requirements, modular code deliverables, and no disclosed grading mechanics.
---

# V2 candidate instructions

Read the current request, the existing instruction, and the
[v2 requirements](../../requirement.md). Preserve accepted changes. Examples
cannot add requirements, and later turns must identify which earlier requirements
remain or are replaced. Multi-turn work is encouraged; a single-turn task must
meet the same difficulty and long-horizon bar.

## Write the user's request

Start task design with `instruction.md`, before designing its environment,
verifier, reward, or oracle. Write as a user asking an engineer, researcher, or
other professional to do useful work. Explain the intent, the objective, and what
the user expects to receive. Include relevant context without inventing a
backstory.

Use descriptive sections suited to the work. Start with the goal and context,
then organize required behavior, interfaces, constraints, and deliverables. Put
inputs, defaults, consequential types, state changes, errors, resource limits,
and absolute output paths beside the requirements they clarify. Leave methods
and implementation choices open unless the request requires them. Surface
ambiguities that would change success instead of inventing a constraint.

The [knowledge-work assistant instruction](../../../tasks/enterprise/knowledge-work-assistant/instruction.md)
is an example of a direct request organized by purpose, inputs, public behavior,
and development records. Its headings, RAG workflow, models, database, CLI, and
paths belong to that task. Choose the structure and requirements the new task
needs.

## Make requirements easy to scan

When an instruction contains many requirements, use focused bullet points and
short **bold labels** so the reader can find each obligation quickly.

- Group related requirements under descriptive headings. Give each bullet one
  action, constraint, or closely related set of conditions.
- Bold a short label or a consequential limit; keep the explanation in ordinary
  text. Avoid bolding whole paragraphs.
- Keep exceptions and dependencies beside the rule they qualify. Use numbered
  lists for ordered procedures and tables for comparable items or parameters.
- Use prose for context and reasoning. Split paragraphs that bury several
  independent obligations instead of making the reader extract a checklist.

Treat useful bold labels and requirement lists as functional formatting during
the Humanizer pass. Preserve them when they improve navigation. Formatting changes
must retain exact names, values, interfaces, and required-versus-optional meaning.

## Describe the deliverable

For tasks that ask the candidate to write code, require highly modular code as
an explicit property of the deliverable. Keep module names, frameworks, and other
implementation choices open. A useful split puts domain rules in focused
functions and parsing, storage, or network effects in adapters that call them.
Module count and file size do not establish modularity.

Use [function contracts](../funtional-programmer/SKILL.md) when writing authoring
code or code examples. Authoring conventions become candidate requirements only
when the instruction explicitly asks for them.

## Keep assessment mechanics private

Never disclose final-evaluation protocols, methods, or procedures in
`instruction.md`. This includes how checks run, private cases, judge settings,
scoring formulas, grading limits, and artifact transfer. Apply the same boundary
to candidate-visible comments, help text, examples, and resource READMEs. Keep
assessment mechanics in author-only documentation and configuration.

State required product behavior directly. The task may ask the candidate to
perform development experiments or keep progress records; those requests are
part of the work. Choose records and paths appropriate to the task without
explaining the final grader. Preserve necessary attribution and let installed
tools be discoverable instead of listing inventories.

## Review the instruction

Apply [Humanizer](../humanizer/SKILL.md), then compare exact names, quantities,
types, formats, and meaning with the request. Check that every requirement is
visible and that examples have not become accidental constraints. Save only the
final prose. Editing an instruction does not itself authorize changing its
verifier or running trials.

For a dense instruction, also scan just its headings and bold labels: can the
reader locate the required behavior, limits, exceptions, and deliverables?
