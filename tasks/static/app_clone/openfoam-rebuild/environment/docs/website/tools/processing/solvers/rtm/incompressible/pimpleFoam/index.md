<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/incompressible/pimpleFoam/ -->

# pimpleFoam

## Overview

* Category: [Incompressible](../index.md)
* transient
* incompressible
* [Turbulence](../../../../models/turbulence.md)
* [fvOptions](../../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* [PIMPLE algorithm](../../../pressure-velocity/pimple.md)

## Input requirements

Mandatory fields:

* p: [Kinematic pressure](../../../algorithm-kinematic-pressure.md) \[m2/s2]
* U: velocity \[m/s]

### Physical models

* [turbulence](../../../../models/turbulence.md):
`constant/turbulenceProperties`
* [finite volume options](../../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../../numerics/schemes.md)
* [Linear equation solvers](../../../../numerics/solvers.md)
* [controlDict](../../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [pimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/incompressible/pimpleFoam)

See also

* [simpleFoam](../simpleFoam.md)
* [rhoPimpleFoam](../../compressible/rhoPimpleFoam.md)

Tutorials

* [pimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam)
