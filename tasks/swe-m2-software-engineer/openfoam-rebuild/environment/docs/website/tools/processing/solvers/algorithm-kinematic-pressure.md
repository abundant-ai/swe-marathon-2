<!-- https://doc.openfoam.com/2606/tools/processing/solvers/algorithm-kinematic-pressure -->

# Kinematic pressure

For constant density problems the system of equations can be simplified.
The [incompressible](rtm/incompressible.md) solvers
transform the pressure from static pressure, psp\_sps​ \[pa] to kinematic
pressure pkp\_kpk​, i.e.

pk\=psρ\[m2/s2] p\_k \= \\frac{p\_s}{\\rho} \\qquad \\mathrm{\[m^2/s^2]}pk​\=ρps​​\[m2/s2]
Note that the kinematic pressure has the name `p` in OpenFOAM solvers, the
same as the name for the static pressure `p`. Accordingly, to interpret the
results from incompressible solvers, the kinematic pressure should be multiplied
by the reference density (constant) value.
