<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/heat-transfer/buoyantSimpleFoam/ -->

# buoyantSimpleFoam

## Overview

* Category: [Heat transfer](../index.md)
* steady state
* compressible
* [Turbulence](../../../../models/turbulence.md)
* [Thermophysical](../../../../models/thermophysical.md)
* [fvOptions](../../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* [SIMPLE algorithm](../../../pressure-velocity/simple.md)
* [Hydrostatic pressure effects](../../../algorithm-p-rgh.md)

## Input requirements

Mandatory fields:

* p: pressure \[pa]
* p\_rgh: pressure \- hydrostatic contribution \[pa]
* U: velocity \[m/s]
* T: temperature \[K]

### Physical models

* [turbulence](../../../../models/turbulence.md):
`constant/turbulenceProperties`
* [heat transfer](../../../../models/thermophysical.md#usage):
`constant/thermophysicalModels`
* [finite volume options](../../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../../numerics/schemes.md)
* + [Linear equation solvers](../../../../numerics/solvers.md)
* [controlDict](../../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [buoyantSimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/heatTransfer/buoyantSimpleFoam)

See also

* [simpleFoam](../../incompressible/simpleFoam.md)
* [rhoSimpleFoam](../../compressible/rhoSimpleFoam.md)

Tutorials

* [buoyantSimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam)
