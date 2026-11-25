# Route a flexible wiring harness through an assembly board

Build a controller that routes a cable through the clips on a jig and leaves the
keyed connector seated. We use the same workcell for several board layouts. The
controller must use the board recipe and live measurements to route each cable.

The simulator supplies one articulated arm with a wrist force/torque sensor, a
gripper with pinch and slide modes, a fixed start anchor, and an instrumented
assembly board. In pinch mode the gripper holds one material point. In slide
mode the cable can move through the gripper. The released length and wrist load
depend on how the cable is already routed. The board provides clip switch
readings and a connector interlock. The clips and inlet shapes constrain the
cable mechanically.

## Route recipe and measurements

The JSON recipe gives the board frame in the robot base frame, fixture poses and
geometry, ordered guide and clip entries, and cable length, marked arc lengths,
radius, rest curvature and characterized bending stiffness. A route entry names
the fixture, its allowed entry side and the interval of material arc length
that belongs there. The connector recipe gives its keyed pose and approach
axis. The workcell documentation supplies calibrated camera and tool frames,
allowable motion, tick units and the input and command schemas. Distances are
in metres, angles in radians, forces in newtons and moments in newton-metres.

Each decision receives the latest joint feedback, wrist wrench, clip switches,
gripper state and connector interlock. The depth stream reports visible cable
points and the material marks it can read. A missing mark leaves its material
position unknown. The gripper can acquire a visible segment, change mode,
move or hold. The fixture receives no direct commands to set a clip or connector
state.

## Controller behavior

Plan a route that respects fixture entry directions and material intervals.
Keep the measured cable bend radius and loads inside the recipe limits, and
avoid contact with the board and fixtures outside the permitted tool and cable
contact regions. Use force and geometry feedback to stop a move that would
exceed a limit. Respect the stated joint, tool speed and execution limits.

Finish only after the required clips hold the intended cable segments in order
and the connector interlock confirms seating. The route must stay seated
during the recipe's retention check. Return a blocked result and hold safely
when the required route cannot be completed within the recipe limits. Preserve
any already seated segments while stopping.

## Deliverables

Put a modular Python application in `/app/harness_router/`. Run it as
`python3 -m harness_router run --recipe RECIPE.json` from `/app`. The process
reads one JSON observation per line from stdin and emits one JSON response
per line to stdout. Each response includes the observation ID, command ID,
action, and operation status. The simulator applies only permitted commands and
returns the next observation and a receipt. Keep geometry and planning code
separate from command serialization and simulator I/O.
