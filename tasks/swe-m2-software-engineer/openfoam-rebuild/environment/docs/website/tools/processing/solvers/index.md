<!-- https://doc.openfoam.com/2606/tools/processing/solvers/ -->

# Solver Applications

## Flow

* [Basic](rtm/basic/index.md)
* [Incompressible](rtm/incompressible/index.md)
* [Compressible](rtm/compressible/index.md)
* [Heat transfer](rtm/heat-transfer/index.md)
* [Multiphase](rtm/multiphase/index.md)
* [Lagrangian particles](rtm/lagrangian-particle/index.md)
* [Discrete methods](rtm/discrete-methods.md)
* [Combustion](rtm/combustion/index.md)
* [Direct Numerical Simulation (DNS)](rtm/dns.md)

## Other

* [Electromagnetics](rtm/electro-magnetics.md)
* [Financial](rtm/financial.md)
* [Stress analysis](rtm/stress-analysis.md)

## Common variable transformations

Many OpenFOAM solver applications employ common variable transformations,
including:

* [kinematic pressure](algorithm-kinematic-pressure.md) for
incompressible solvers
* [hydrostatic pressure](algorithm-p-rgh.md) effects

## Pressure\-velocity coupling

* Introduction: [Pressure\-velocity algorithms](pressure-velocity/index.md)
* Steady state: [SIMPLE](pressure-velocity/simple.md)
* Transient: [PISO](pressure-velocity/piso.md)
* Transient: [PIMPLE](pressure-velocity/pimple.md)

## Capability matrix

noteThe solver capability matrix is not yet included in this site. See the [production docs](index.md) for the full table.
