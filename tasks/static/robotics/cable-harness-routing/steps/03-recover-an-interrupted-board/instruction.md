# Finish a partly installed harness after interruption

The operator may publish a revised recipe while the board is partly assembled.
A movable fixture can block the planned feed, a guide can be opened for
service, or a safe stop can interrupt a move. The revised recipe identifies
which unlatched guides may change. Material already held by a latched clip
must remain attached. Recover from the arm, cable and fixture state reported
after the stop.

Keep the original completion, retention, load and joint limits. Accept revised
observations using the supplied board generation and capture tick. An old
observation cannot authorize motion in a newer generation. When camera and
clip measurements disagree, hold and take any still-available probe or scan
before proceeding. Plan a different feed or regrasp when the changed fixture
makes the original route infeasible. Return a blocked result when the revised
conditions cannot be met without exceeding the limits or opening a clip that
must stay latched.

The controller process can restart after the plant accepted a command and
before the next receipt arrives. The plant persists the last accepted command
ID for the board and deduplicates retries by ID. Write the command and its
generation to durable state before sending it. On restart, reconcile the
pending command with the next plant receipt. A retry of an observation must
return the same pending command and ID until the controller has a receipt
or a newer board generation invalidates the motion. A command from an older
generation must never reissue motion in a newer generation.

Add `--state PATH` to the existing command. When provided, keep the committed
state at that path, including board generation, pending command, receipt and
material assignment for clips already installed. Resume with the same path
after process restart. Keep simulator operations, persistence and recovery
decisions in separate modules.
