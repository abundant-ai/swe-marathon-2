<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/combustion/XiFoam -->

# XiFoam

## Overview

* Category: [Combustion](index.md)
* transient
* compressible
* [Turbulence](../../../models/turbulence.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)
* heat transfer
* chemistry
* combustion
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
* chemistry: `constant/chemistryProperties`
* combustion: `constant/combustionProperties`
* [finite volume options](../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [XiFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/combustion/XiFoam)

See also

* [engineFoam](engineFoam.md)

Tutorials

* [XiFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/XiFoam)
