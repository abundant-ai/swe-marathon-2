# Qualify and route replacement harness batches

Keep the original routing command and behavior. The cell now receives batches
whose bending stiffness, sliding friction and initial shape vary. The cable
data in the recipe contains length, radius, material marks and admissible
parameter ranges. The previous characterized parameters are available as a
starting point. A scan can hide the portion behind an installed cover, and two
visible segments can lie close together.

Extend the controller to perform bounded probe moves and record the fitting
observations it used. Use the known tool motion, wrench and material-mark
movement to assess whether a planned feed and bend will stay within the
recipe limits. Probe limits and the maximum number of probes are in the recipe.
When more than one shape or parameter fit explains the observations, either
take another allowed measurement or select a move that is safe under all
remaining interpretations. Hold when neither option gives a safe route.

Complete the original seating and retention checks on the replacement cable.
The position of each seated segment must remain valid while later segments are
fed through the gripper. Restore an accessible segment if it slips from an
unlocked guide. Treat a latched clip and its assigned material interval as
constraints on any repair.

Extend each response with a reason code for an unresolved observation or
unsafe route. Record the estimated parameter ranges and the observations used
to narrow them in `/app/harness_router/calibration.json` at the end of a run.
Use the same public command and message framing as before.
