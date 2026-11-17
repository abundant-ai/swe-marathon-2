# Instruction-writing comparisons

The [Orange instruction](../../../../tasks/swe-m2-ai-engineer/knowledge-work-assistant/steps/01-build-rag/instruction.md)
is the genuine user-written voice reference. The pairs below are constructed
examples in that style. They are not presented as quotations from a human author
or as records of an actual model's output. Their filenames, commands, and
hypothetical grading details are invented for teaching.

Each pair starts with the same underlying public assignment. The rewrite makes
that assignment easier to follow and removes evaluator-facing commentary. It
does not add requirements to repair vague prose. The review notes and evidence
maps are for task authors; do not copy them into candidate instructions.

These examples illustrate writing choices. They are not complete proposals for
the repository's multi-day workload requirement.

## Example 1: an application with persistent state

### Poor draft: abstract wording and exposed grading mechanics

```markdown
# Comprehensive record lifecycle solution

Your mission is to deliver an exceptionally robust and seamless record lifecycle
capability that operationalizes archival fidelity across ingestion modalities.
This isn't just about storing data; it is about ensuring trust at every layer.

The intended use is a local archive for company records. Please ensure the
implementation is in /app, is highly modular, and exposes an executable recordbook
entry point that supports recordbook import --file RECORDS.json [--replace] as
well as recordbook list. In terms of input-contract alignment, RECORDS.json is a
valid JSON array whose records have unique string id values and string title and
content values, with all fields being required. Only these three fields occur.

Stateful continuity must be demonstrated using /app/state across process
invocations. Additive ingestion shall provide existing-identity preservation,
which means ignoring incoming records whose IDs already exist, including keeping
the stored title and content unchanged, while admitting unseen IDs. Replacement
must materialize exactly the supplied records, replacing existing values and
eliminating absent identities. Listing must emit a JSON array to stdout, preserving
the original field values and sorting records by id in ascending order. Listing
an archive before any import must produce an empty JSON array.

The hidden harness will exercise both import modes, restart processes, and inspect
persisted records. It will copy /app into a fresh verifier container. Structure
your solution to maximize credit on these grading dimensions and avoid triggering
the evaluator's persistence penalties. Save development inputs and results under
/app/dev and maintain a PROGRESS.md file there. This is the foundation of success.
```

The reader has to translate phrases such as "existing-identity preservation" into
ordinary behavior. The grader paragraph changes the apparent objective from
building an archive to satisfying tests. The storage requirements are useful;
they should remain public even after the grader paragraph is removed.

### Clear rewrite: the same assignment as a professional request

```markdown
# Local record archive

## Goal

Build a local archive in /app for company records. We need to add new records
without changing those already stored, and occasionally replace the archive
with a complete updated collection. Keep the implementation highly modular.

## Commands and input

Provide an executable /app/recordbook with these commands:

recordbook import --file RECORDS.json [--replace]
recordbook list

RECORDS.json contains a valid JSON array. Each record has exactly three required
string fields: id, title, and content. IDs are unique within each input file.

## Import behavior

Store the archive under /app/state so later CLI processes can read it.

Without --replace, add records with new IDs and ignore records whose IDs are
already stored. Keep the stored title and content unchanged for those IDs.

With --replace, make the archive match the supplied file. Replace the values
for existing IDs and remove records absent from the file.

## Listing and development records

recordbook list writes the stored records as one JSON array to stdout, sorted
by id in ascending order. Preserve the original field values. Before the first
import, listing returns an empty array.

Save your development inputs and results under /app/dev, and maintain a
PROGRESS.md file in that directory.
```

### Author review: what survived and how it can be observed

| Public requirement retained | Observable evidence |
| --- | --- |
| Application location, executable, commands, and input schema | The declared executable accepts the two commands and valid three-field input records. |
| Persistent state under /app/state | A later CLI process lists the records imported by an earlier process. |
| Additive import preserves existing records | Import an existing ID with changed text and a new ID; the old text remains and the new record appears. |
| Replacement matches the supplied collection | Import a replacement collection; listed values and IDs match it, including removals. |
| Listing preserves fields and orders records | Compare the listed array with the stored records and their ascending IDs. An untouched archive lists an empty array. |
| Modular implementation and development records | Inspect responsibility boundaries in the delivered code and the requested development files. |

The rewrite retains the location, schema, modes, persistence, output behavior,
modularity, and development artifacts. It removes the fictional private harness,
transfer procedure, and credit language. The evidence map is author guidance;
the candidate already has the behavior it needs to implement.

## Example 2: a decision brief grounded in supplied records

### Poor draft: evaluation language obscures the decision

```markdown
# Holistic release readiness synthesis

You are tasked with conducting a comprehensive and nuanced release-readiness
analysis that synthesizes multifaceted stakeholder perspectives into an
impactful, actionable artifact. The goal is not simply summarization, but a
rigorous demonstration of analytical excellence.

Use only /data/release/release-plan.md, /data/release/issues.csv, and
/data/release/decision-notes.md. The plan defines launch-blocking conditions;
the CSV has issue_id, status, owner, and summary fields; the notes record release
decisions. Treat the CSV as current issue status and the notes as decision
history. Disagreement between them must be surfaced, not silently reconciled.

The final artifact must be /app/release-brief.md and contain Decision, Blockers,
and Unknowns sections. Select ship or hold by applying the plan's launch-blocking
conditions. If missing or conflicting information prevents establishing that
those conditions are satisfied, select hold and identify the unresolved question.
If the CSV has no owner for a blocker, report unassigned instead of inventing
one. Every factual claim needs a source filename and issue ID or section heading.
For each blocker include the issue ID, owner, and recommended next action.

The private judge gives credit for groundedness, comprehensive blocker coverage,
and decision consistency. It compares your recommendation with a reference brief
and downweights unsupported claims. Optimize your narrative against that rubric;
include enough citations to pass the evidence checks. Deliver a polished,
professional document that leaves no stone unturned.
```

The opening hides the practical question: can the release ship? The final
paragraph exposes a fictional assessment process and encourages writing for the
judge. Removing it must not remove source requirements, blocker coverage, or the
rule for handling uncertainty.

### Clear rewrite: a decision the user can act on

```markdown
# Release readiness brief

## Goal

Write /app/release-brief.md to help the release lead decide whether to ship.
Recommend ship or hold, explain the blockers, and identify what still needs an
answer before the decision can be settled.

## Records to use

Use only these files:

- /data/release/release-plan.md defines the launch-blocking conditions.
- /data/release/issues.csv lists issue_id, status, owner, and summary.
- /data/release/decision-notes.md records release decisions.

Use the CSV for current issue status and the notes for decision history. If they
disagree, describe the disagreement instead of choosing one account silently.

## Brief

Use three sections: Decision, Blockers, and Unknowns.

In Decision, apply the launch-blocking conditions in the plan and recommend ship
or hold. If missing or conflicting information prevents you from establishing
that those conditions are satisfied, recommend hold and name the question that
needs to be resolved.

In Blockers, list every issue that blocks release under the plan, with its issue
ID, owner, and your recommended next action. Use unassigned when the CSV has no
owner. Make clear which next actions are your recommendations.

In Unknowns, list the missing or conflicting information that affects the decision.
Support every factual claim with a source filename and an issue ID or section
heading so the release lead can find the underlying record.
```

### Author review: useful judgment without a disclosed rubric

| Public requirement retained | Observable evidence |
| --- | --- |
| One brief at the required path with the three named sections | Inspect the delivered file and its section structure. |
| Only the three supplied sources | Trace factual statements and citations to those files. |
| A decision based on the plan | Compare the recommendation and its explanation with the plan's conditions and supplied issue status. |
| Hold when relevant uncertainty prevents a supported ship decision | Use a case with conflicting or missing evidence and inspect the stated decision and unresolved question. |
| Complete blocker coverage with IDs, owners, and actions | Match the blocker list to the source records; check missing owners remain unassigned and proposed actions are identified as recommendations. |
| Traceable factual claims | Follow each filename and issue ID or heading and assess whether the cited passage supports the claim. |

The public decision rule remains explicit. The final grader's prompt, reference
brief, scoring, and weights remain private. Source faithfulness and the reasoning
behind a recommendation need substantive review; the presence of a citation or
a heading alone does not establish quality.

## What to carry into another task

Start with the user and the work they need done. Keep exact interfaces and
observable requirements wherever they matter. Put related conditions together,
and name uncertainty when the source leaves a decision open. Remove the voice
of an evaluator without making the requested outcome less precise.

When a real draft lacks a public requirement, report the gap to its author.
These examples have invented, fully supplied contracts for demonstration; they
do not authorize adding equally specific details to an unrelated assignment.
