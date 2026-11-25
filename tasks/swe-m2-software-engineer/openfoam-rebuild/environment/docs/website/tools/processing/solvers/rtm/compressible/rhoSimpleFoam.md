<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/compressible/rhoSimpleFoam -->

# rhoSimpleFoam

## Overview

* Category: [Compressible](index.md)
* steady state
* [Turbulence](../../../models/turbulence.md)
* [Thermophysical](../../../models/thermophysical.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* [transonic option](index.md#common-options-transonic)
* \[SIMPLE]([https://doc.openfoam.com/2606/\#pv\-simple](../../../../../index.md#pv-simple)"]

## Input requirements

Mandatory fields:

* p: pressure \[pa]
* U: velocity \[m/s]
* T: temperature \[K]

### Physical models

* [turbulence](../../../models/turbulence.md):
`constant/turbulenceProperties`
* [heat transfer](../../../../../index.md#models-thermophysical:):
`constant/thermophysicalModels`
* [finite volume options](../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Steady state schemes](../../../numerics/schemes/divergence.md#special-cases-steady-state)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [rhoSimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/compressible/rhoSimpleFoam)

See also

* [simpleFoam](../incompressible/simpleFoam.md)
* [rhoPimpleFoam](rhoPimpleFoam.md)

Tutorials

* [rhoSimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam)
