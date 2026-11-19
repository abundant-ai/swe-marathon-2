# BasedPL interpreter rebuild

Author notes. Nothing in this file is shipped to the agent or to either image.

The agent gets an execute-only copy of `bpl`, the interpreter of the BasedPL array language
(github.com/AnswerDotAI/basedpl, Apache-2.0, first published 2026-09-16, pinned at tag v0.1.95,
commit `af3609a`), and its documentation, and writes an interpreter that prints the same output.
Unlike a MirrorCode task it gets no example runs and no expected outputs: it finds out what the
interpreter does by running it.

## Development log

### 2026-11-19

- Started from the judge panel's choice for idea 9 ("no examples"): BasedPL, pinned at v0.1.95.
  The hardening patch, the pinned `Cargo.lock` and the local build script are in place; the
  rest of the task follows.
