<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/combustion/coldEngineFoam -->

# coldEngineFoam

## Overview

* Category: [Combustion](index.md)
* transient
* compressible
* heat transfer
* [Turbulence](../../../models/turbulence.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)
* moving mesh
* time defined in crank\-angle (CA) degrees

## Equations

* [PIMPLE algorithm](../../pressure-velocity/pimple.md)

## Input requirements

Mandatory fields:

* p: pressure \[pa]
* U: velocity \[m/s]
* T: temperature \[K]

### Physical models

* [turbulence](../../../models/turbulence.md):
`constant/turbulenceProperties`
* [heat transfer](../../../models/thermophysical.md#usage):
`constant/thermophysicalModels`
* [finite volume options](../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [coldEngineFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/combustion/coldEngineFoam)

See also

* [engineFoam](engineFoam.md)
* [XiFoam](XiFoam.md)

Tutorials

* [coldEngineFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/coldEngineFoam)
