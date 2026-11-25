<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/incompressible/boundaryFoam -->

# boundaryFoam

## Overview

* Category: [Incompressible](index.md)
* steady state
* incompressible
* [turbulence](../../../models/turbulence.md)
* evolves the flow system to reach a target average velocity
* useful to set velocity and turbulence inflow conditions based on a fully
developed flow profile

## Equations

The velocity is modelled according to the equation

∇ ∙ Rdev\=∇p\+SU \\div \\tensor{R}\_{dev} \= \\grad p \+ S\_U∇∙Rdev​\=∇p\+SU​
where the velocity and pressure gradient are corrected to achieve the target
velocity u‾\\overline{\\u}u. After solving the above equation, the velocity
is corrected from the current volume\-averaged velocity, i.e.

un\+1\=un\+(u‾−u‾n) \\u^{n\+1} \= \\u^n \+ \\left( \\overline{\\u} \- \\overline{\\u}^n \\right)un\+1\=un\+(u−un)
and the pressure gradient from:

(∇p)n\+1\=(∇p)n\+1A(u‾−u‾n)‾ \\left(\\grad p\\right)^{n\+1} \= \\left(\\grad p\\right)^{n} \+ \\overline{\\frac{1}{\\mat{A}}\\left( \\overline{\\u} \- \\overline{\\u}^n \\right)}(∇p)n\+1\=(∇p)n\+A1​(u−un)​
where the averages are calculated as volume averages.

## Input requirements

Mandatory fields:

* p: [Kinematic pressure](../../algorithm-kinematic-pressure.md) \[m2/s2]
* U: velocity \[m/s]

### Physical models

* [turbulence](../../../models/turbulence.md):
`constant/turbulenceProperties`
* [finite volume options](../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [boundaryFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/incompressible/boundaryFoam)

See also

* [simpleFoam](simpleFoam.md)

Tutorials

* [boundaryFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/boundaryFoam)
