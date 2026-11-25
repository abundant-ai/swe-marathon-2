<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/compressible/rhoCentralFoam -->

# rhoCentralFoam

## Overview

* Category: [Compressible](index.md)
* transient
* compressible \- density based
* heat transfer
* shock capturing
* [Turbulence](../../../models/turbulence.md)
* [Thermophysical](../../../models/thermophysical.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* based on the central\-upwind schemes of Kurganov and Tadmor

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

* [rhoCentralFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/compressible/rhoCentralFoam)

See also

* [rhoPimpleFoam](rhoPimpleFoam.md)

Tutorials

* [rhoCentralFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoCentralFoam)
