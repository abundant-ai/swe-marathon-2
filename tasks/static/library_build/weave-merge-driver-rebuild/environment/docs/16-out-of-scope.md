# 16. What the replacement need not do

A replacement must do everything chapters 1 to 15 state, and may leave out the following.

- **[OUT-1] Other file types.** Only `PATH`s ending in `.py`, `.ts`, `.go`, `.json` and `.toml` are
  sent ([CLI-8]). Where a rule names other extensions or languages, only its effect on these five
  matters.
- **[OUT-2] Other calls.** A call without `-o OUT`, without `-l` (annotated markers), or with a
  marker width other than 7; the long
  spellings `--output`, `--marker-length` and `--path`; and the flags `--audit`, `-h`/`--help` and
  `-V`/`--version`. The positional reading of [CLI-5] is still required.
- **[OUT-3] The `weave-set` attribute** (which weave reads with
  `git check-attr -z weave-set -- PATH`). A replacement behaves as when no file declares it: no
  order-sensitive collection is united by declaration, and [GATE-IOTA] is never waived.
- **[OUT-4] Environment variables.** A replacement behaves as when no `WEAVE_` variable is set; in
  particular the duplicate-name limit of [ENT-8] stays 10.
- **[OUT-5] Side files and messages.** Audit and findings documents, the lifetime statistics file,
  merge-event lines, warnings, and every other line written to standard error ([CLI-5]).
- **[OUT-6] A missing `git`.** weave's in-process replacement for `git merge-file`, used only when
  git cannot be run.
- **[OUT-7] The other programs.** The `weave` command (`weave explain`, `weave check` and the rest)
  and every program other than `weave-driver`; of the commands the hint of [BOX-7] names, only its
  text is required.
- **[OUT-8] Large inputs.** Every input the driver receives is at most 100,000 bytes; nothing is
  required for a larger one.
