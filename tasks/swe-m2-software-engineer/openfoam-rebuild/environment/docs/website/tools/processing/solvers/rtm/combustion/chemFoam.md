<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/combustion/chemFoam -->

# chemFoam

## Overview

* Category: [Combustion](index.md)
* transient
* heat transfer
* chemistry
* combustion

## Equations

## Input requirements

Mandatory fields:

* specie fields, e.g. N2, O2 depending on choice of thermophysical modelling

### Physical models

* [heat transfer](../../../models/thermophysical.md#usage):
`constant/thermophysicalModels`
* chemistry: `constant/chemistryProperties`
* combustion: `constant/combustionProperties`

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [chemFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/combustion/chemFoam)

See also

* [reactingFoam](reactingFoam.md)

Tutorials

* [chemFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/chemFoam)
