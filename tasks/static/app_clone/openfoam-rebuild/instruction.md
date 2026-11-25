# Reimplement OpenFOAM

## Goal

Build a new implementation of OpenFOAM v2606 from scratch, whose externally observable behaviour
matches the installed OpenFOAM.

## Context

- OpenFOAM v2606 is installed and on `PATH`. You can run its programs as often as you like, but
  not read their files. Its documentation is in `/app/docs` and its example cases in
  `/app/tutorials`.
- There is no network access.
- You have 12 hours. Run `bash /app/timer.sh` to check how much wall-clock time remains.

## Clean-room rules

Learn what OpenFOAM does only from running its programs through their normal interface
(arguments, case files, standard input and output), its documentation and its example cases.

- Do not reproduce OpenFOAM's source code from memory or any other copy.
- Do not decompile, disassemble or trace the installed programs or libraries (`objdump`, `gdb`,
  `strace`, `ltrace`, `perf` and the like). Any tool is fine on programs you build yourself.
- Do not wrap, copy, re-link or call the installed programs or libraries.

## What to deliver

Your source code in `/app/rebuild` and a build script `/app/rebuild/compile.sh`. Run from
`/app/rebuild` on a fresh copy of your source in this environment, without network access and
within two hours, it builds an executable for each OpenFOAM program into `/app/rebuild/bin`,
named like the program. If `compile.sh` does not build them from your source, the work does not
count.

Your programs will run where OpenFOAM is not installed and none of its environment variables are
set, as a user that cannot write to `/app/rebuild`, with `HOME` and `TMPDIR` set to new empty
directories. Everything they need at run time must be in `/app/rebuild`. They should run about
as fast as the installed programs.

Write highly modular code. You choose the languages, structure and names.

Keep `/app/rebuild/PROGRESS.md` up to date: which programs and features work, how you checked
them against the installed OpenFOAM, and what remains.
