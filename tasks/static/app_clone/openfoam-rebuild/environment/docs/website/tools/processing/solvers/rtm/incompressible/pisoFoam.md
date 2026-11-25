<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/incompressible/pisoFoam -->

# pisoFoam

## Overview

* Category: [Incompressible](index.md)
* transient
* incompressible
* [Turbulence](../../../models/turbulence.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* [PISO algorithm](../../pressure-velocity/piso.md)

## Input requirements

Mandatory fields:

* p: [Kinematic pressure](../../algorithm-kinematic-pressure.md) \[m2/s2]
* U: velocity \[m/s]

### Physical models

* [turbulence](../../../models/turbulence.md):
`constant/turbulenceProperties`
* [finite volume options](../../../numerics/fvoptions.md#usage) :
`constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [pisoFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/incompressible/pisoFoam)

See also

* [simpleFoam](simpleFoam.md)
* [rhoPimpleFoam](../compressible/rhoPimpleFoam.md)

Tutorials

* [pisoFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam)
