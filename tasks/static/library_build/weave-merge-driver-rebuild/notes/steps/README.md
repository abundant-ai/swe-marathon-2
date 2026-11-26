# Draft step instructions for the candidate chains (proposals)

These are drafts in the requester's voice for the two chains in `../STEPS.md`. They are not
implemented steps: the repository allows only implemented steps in `task.toml`, and the panel
decided to build the single step (the task root's `instruction.md`) first. If spike days 4-5 adopt
a chain, each draft moves to `steps/<name>/instruction.md` and the root files become step 2's.

| File | Chain | Step |
| --- | --- | --- |
| `c-01-rebuild-driver.md` | C | 1: rebuild 0.5.4 |
| `c-02-follow-releases.md` | C | 2: follow 0.6.0-0.7.1 |
| `b-01-rebuild-driver.md` | B | 1: rebuild 0.6.2 |
| `b-02-follow-release.md` | B | 2: follow 0.7.0-0.7.1 |

Rules every draft keeps (from the 2026-11-20 multi-turn decision and the 2026-11-26 brief): each
step restates every requirement in force, because a step may start a fresh session; step 1 says
new releases will come, never how many or when; no comparison, grading, budget or session
vocabulary; each requirement is stated by what depends on it; each step ends with a cut-over line.
Version numbers, paths and crate lists are placeholders until the spike pins them.
