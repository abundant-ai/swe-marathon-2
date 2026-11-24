# Writing test cases for OpenFOAM v2606

Goal: small OpenFOAM case folders that make real OpenFOAM exercise behaviour the official
tutorials never reach. Each program run in a case later becomes a test: we record what real
OpenFOAM writes, prints and returns, and a reimplementation must reproduce it.

## Environment
- Docker image `ofrebuild:harvest` (OpenFOAM v2606, user `dev`, tutorials in `$FOAM_TUTORIALS`,
  every OpenFOAM program on PATH, `-help`, `-help-full` and `-list…` options work).
- Try a case:  `docker run --rm -v <case dir>:/c:ro ofrebuild:harvest bash -c 'cp -r /c /tmp/x && cd /tmp/x && ./Allrun'`
  Inspect with `docker run --rm -it ...` as needed. Use `--rm` always. Don't build images.

## A case is a folder `scripts/generate/cases/<group>/<name>/` with
- a complete OpenFOAM case (system/, constant/, 0/ or 0.orig/ …) and any input files it needs
  (e.g. a small hand-written .msh or .stl), and
- `Allrun` (bash, executable): plain commands in order, each OpenFOAM program called by name.
  First line after the shebang: `# from: <tutorial it is based on, or "scratch">; exercises: <feature(s)>`.
  For expected failures (error cases) write `prog args || true` so Allrun still exits 0.

## Rules
- Base cases on a tutorial where possible: copy, shrink the mesh, change the one thing you target.
- Small and fast: every program run under ~5 s, whole Allrun under ~30 s. Coarse meshes, short
  endTime / few iterations.
- Deterministic: run Allrun twice in fresh copies; results (excluding log.* files) must be identical
  (`diff -r`).
- Must really exercise the target: no `FOAM FATAL` unless the case is an error case, and the
  feature must appear in the run (the type is selected, the program prints its work).
- Out of scope, skip: anything compiled at run time (`coded…`, `#codeStream`, `dynamicCode`),
  network, tools not in the image. Don't use git. Only write inside your own group folder.
- No READMEs or notes files; the Allrun header line is the only description.

## Report back (short)
Cases written (name → feature), features you skipped and why, anything surprising.
