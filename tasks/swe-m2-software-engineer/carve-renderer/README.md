# Carve renderer from the specification

Author notes. Nothing in this file is shipped to the agent or to either image.

The agent gets the normative specification of Carve, a markup language derived from Djot, and
its documentation site's pages, and writes a renderer that turns Carve into exactly the HTML of
the reference implementation, carve-rs. It never sees carve-rs, any other engine, the executable
spec model or the conformance material. This is idea 10 of the owner's sheet, "spec only, no
binary".

## Development log

### 2026-11-19

- Started from the judge panel's choice for idea 10: Carve (spec markup-carve/carve, MIT) pinned
  at spec tag 0.1.14, graded against carve-rs 0.1.14's release build. The case generator, its
  rewrites and the document generator are in `scripts/`; the rest of the task follows.
