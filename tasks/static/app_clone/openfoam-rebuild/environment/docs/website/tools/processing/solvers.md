<!-- https://doc.openfoam.com/2606/tools/processing/solvers -->

# Solver Applications

## Flow

* [Basic](solvers/rtm/basic/index.md)
* [Incompressible](solvers/rtm/incompressible/index.md)
* [Compressible](solvers/rtm/compressible/index.md)
* [Heat transfer](solvers/rtm/heat-transfer/index.md)
* [Multiphase](solvers/rtm/multiphase/index.md)
* [Lagrangian particles](solvers/rtm/lagrangian-particle/index.md)
* [Discrete methods](solvers/rtm/discrete-methods.md)
* [Combustion](solvers/rtm/combustion/index.md)
* [Direct Numerical Simulation (DNS)](solvers/rtm/dns.md)

## Other

* [Electromagnetics](solvers/rtm/electro-magnetics.md)
* [Financial](solvers/rtm/financial.md)
* [Stress analysis](solvers/rtm/stress-analysis.md)

## Common variable transformations

Many OpenFOAM solver applications employ common variable transformations,
including:

* [kinematic pressure](solvers/algorithm-kinematic-pressure.md) for
incompressible solvers
* [hydrostatic pressure](solvers/algorithm-p-rgh.md) effects

## Pressure\-velocity coupling

* Introduction: [Pressure\-velocity algorithms](solvers/pressure-velocity/index.md)
* Steady state: [SIMPLE](solvers/pressure-velocity/simple.md)
* Transient: [PISO](solvers/pressure-velocity/piso.md)
* Transient: [PIMPLE](solvers/pressure-velocity/pimple.md)

## Capability matrix

noteThe solver capability matrix is not yet included in this site. See the [production docs](solvers/index.md) for the full table.
