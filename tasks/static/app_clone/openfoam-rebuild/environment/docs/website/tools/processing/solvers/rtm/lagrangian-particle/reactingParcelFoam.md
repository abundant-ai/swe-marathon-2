<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/lagrangian-particle/reactingParcelFoam -->

# reactingParcelFoam

## Overview

* Category: [Lagrangian particles](index.md)
* transient
* compressible
* lagrangian particles: reacting
* [Turbulence](../../../models/turbulence.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)
* chemistry
* combustion

## Equations

* [PIMPLE algorithm](../../pressure-velocity/pimple.md)
* [Hydrostatic pressure effects](../../algorithm-p-rgh.md)

## Input requirements

Mandatory fields:

* p: pressure \[pa]
* p\_rgh: pressure \- hydrostatic contribution \[pa]
* U: velocity \[m/s]
* T: temperature \[K]
* specie fields, e.g. N2, O2 depending on choice of thermophysical modelling

### Physical models

* [turbulence](../../../models/turbulence.md):
`constant/turbulenceProperties`
* [heat transfer](../../../models/thermophysical.md#usage):
`constant/thermophysicalModels`
* reacting particles: `constant/reactingCloud1Properties`
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

* [reactingParcelFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/lagrangian/reactingParcelFoam)See also

Tutorials

* [reactingParcelFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam)
