---
name: instruction-writing
description: Write or revise step instruction.md files in this repository with natural prose and precise, candidate-visible requirements.
---

# Writing step instructions

Read the current instruction and the user's latest changes. Preserve requirements
that still apply, and do not restore details the user deliberately removed.
Use `/Users/eric/.codex/instruction.md` and its required Humanizer skill.

Write as if explaining the work to a capable colleague. Lead with what they need
to build or change. Put inputs, available resources, and interface details near
the actions they support. Use concrete verbs and connected paragraphs. Use lists
or code blocks when they make parallel requirements or exact formats easier to read.

State defaults and exceptions where they affect behavior. Distinguish required
methods from choices the candidate can make. Include acceptance criteria and
limits that affect success, without prescribing unrequested implementation details.
Flag unresolved requirements instead of filling them in with plausible numbers.

## Keep final evaluation out of candidate-facing material

Never explain final evaluation in `instruction.md` or anywhere the candidate can
read in its environment. This includes resource READMEs, starter files, comments,
help text, and example outputs. Keep grader procedures, held-out case details,
judge configuration, scoring formulas, reward rules, timeouts, output caps, fresh
verifier containers, and artifact-transfer mechanics in author-only documentation
and verifier configuration.

State the work, desired outcome, public interfaces, and deliverables directly.
An accuracy goal can be a task requirement; explaining how the final grader computes
it belongs to the author. A request to generate development questions or report
the candidate's own experiments is part of the work and can remain. Preserve
required data attribution without describing final evaluation.

For Orange, ask for an assistant that reaches the requested accuracy and saves its
development work under `/app/dev`. Do not append a paragraph beginning "Final
evaluation..." or move that explanation into `/opt/resources/README.md`.

For example, Orange's `generate` returns a typed answer object, and the CLI
serializes it. An instruction should make that boundary clear. Its corpus size,
model choices, and accuracy threshold belong to that task; do not copy them into
another task as defaults.

Review the draft with Humanizer in file mode. Keep the final file free of drafting
commentary. Check names, types, quantities, formats, and semantics against the
request after editing the prose. Editing an instruction alone does not authorize
building its runtime or verifier.
