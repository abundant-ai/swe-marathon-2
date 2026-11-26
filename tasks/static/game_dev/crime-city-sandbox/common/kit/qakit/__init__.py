"""QA kit core: run a Godot game headless with the QA telemetry node and record what it does.

The kit prepares a copy of a game project (the telemetry node added first among its
autoloads, one worker thread), imports it, starts game processes with resource limits,
talks to the telemetry node over a signed local link, steps the game tick by tick or
lets it run in real time, and records the frames it reports as a hashed trace.

Modules:
- link: message framing and signing for the telemetry link.
- procs: game processes with limits, captured output and whole-tree kills.
- session: one game process and its telemetry link (lockstep or real time).
- prepare: copy, telemetry insertion, settings and import of a project.
- trace: canonical frames, segments and the SHA-256 chain.
- play: the play file format (a scripted session) and its runner.
- expect: expectations evaluated over a recorded play.
"""
