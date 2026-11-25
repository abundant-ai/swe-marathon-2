<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/multiphase/interFoam -->

# interFoam

## Overview

* Category: [Multiphase](index.md)
* transient
* incompressible
* multiphase: 2 immiscible phases
* isothermal
* [Turbulence](../../../models/turbulence.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* [PIMPLE algorithm](../../pressure-velocity/pimple.md)
* [Hydrostatic pressure effects](../../algorithm-p-rgh.md)

## Input requirements

Mandatory fields:

* p: pressure \[pa]
* p\_rgh: pressure \- hydrostatic contribution \[pa]
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

* [interFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/multiphase/interFoam)

See also

Tutorials

* [interFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam)
