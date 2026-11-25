<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/incompressible/icoFoam -->

# icoFoam

## Overview

* Category: [Incompressible](index.md)
* transient
* incompressible

## Equations

The solver uses the [PISO](../../pressure-velocity/piso.md) algorithm to solve the continuity
equation:

∇ ∙ u\=0 \\div \\u \= 0∇∙u\=0
and momentum equation:

∂∂t(u)\+∇ ∙ (u⊗u)−∇ ∙ (ν∇u)\=−∇p \\ddt{\\u}
 \+ \\div ( \\u \\otimes \\u )
 \- \\div ( \\nu \\grad \\u )
 \=
 \- \\grad p∂t∂​(u)\+∇∙(u⊗u)−∇∙(ν∇u)\=−∇p
Where:

u\\uu
: Velocity

ppp
: Kinematic pressure

## Input requirements

Mandatory fields:

* p: [Kinematic pressure](../../algorithm-kinematic-pressure.md) \[m2/s2]
* U: velocity \[m/s]

### Physical models

* None

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [icoFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/incompressible/icoFoam)

See also

* [pimpleFoam](pimpleFoam.md)

Tutorials

* [icoFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/icoFoam)
