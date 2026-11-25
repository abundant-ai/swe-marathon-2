<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/compressible/rhoPimpleFoam -->

# rhoPimpleFoam

## Overview

* Category: [Compressible](index.md)
* transient
* compressible
* heat transfer
* [Turbulence](../../../models/turbulence.md)
* [Thermophysical](../../../models/thermophysical.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* [transonic option](index.md#common-options-transonic)
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

* [rhoPimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/compressible/rhoPimpleFoam)

See also

* [pimpleFoam](../incompressible/pimpleFoam.md)
* [rhoSimpleFoam](rhoSimpleFoam.md)

Tutorials

* [rhoPimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam)
