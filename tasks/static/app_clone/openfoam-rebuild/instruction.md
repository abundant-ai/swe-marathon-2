# Reimplement OpenFOAM

## Goal

Build a new implementation of OpenFOAM v2606 from scratch, whose externally observable behaviour
matches the installed OpenFOAM.

## Context

- OpenFOAM v2606 is installed in `/opt/openfoam` and on `PATH`. You can run its programs as
  often as you like, but not read the programs or their libraries. Its run-time data
  (`/opt/openfoam/etc`) and scripts (`/opt/openfoam/bin`) are readable. Its documentation is in
  `/app/docs` and its example cases in `/app/tutorials`.
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
directories. Everything they need at run time must be in `/app/rebuild`.

Write highly modular code. You choose the languages, structure and names.

## How it is graded

Your programs are run on recorded runs of the installed programs, each in a copy of the case
folder it ran in. A run is compared with its record in several checks: exit code, standard
output, standard error, each file written, and that no other file was written, changed or
removed. The reward is the share of checks passed.

- Dates, host names, process ids, run times, memory use, the paths of the case, home and
  installation, and the C++ function names and source lines in error messages are ignored.
  Where OpenFOAM prints a path inside its installation, such as
  `/opt/openfoam/etc/controlDict`, print the same path inside `/app/rebuild` (any folder
  above `etc/`).
- Text must match exactly. Integers must be equal. Other numbers may differ by one unit in the
  last printed digit (in exponent form at most one unit in the sixth significant digit, since
  `1e+06` stands for `1.00000e+06`), numbers in binary files by a relative 1e-12, and numbers
  that vary between identical runs of OpenFOAM by more. Dictionary entries may come in any
  order.
- A run may take 30 times as long as the installed program took, and at least 10 seconds.
  Longer runs fail all their checks.

Keep `/app/rebuild/PROGRESS.md` up to date: which programs and features work, how you checked
them against the installed OpenFOAM, and what remains. It is a working note and is not graded.
