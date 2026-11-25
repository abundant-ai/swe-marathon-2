<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/heat-transfer/chtMultiRegionFoam -->

# chtMultiRegionFoam

## Overview

* Category: [Heat transfer](index.md)
* transient
* multiple compressible fluid and solid regions
* [Turbulence](../../../models/turbulence.md)
* [Thermophysical](../../../models/thermophysical.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

* [PIMPLE algorithm](../../pressure-velocity/pimple.md)
* [Hydrostatic pressure effects](../../algorithm-p-rgh.md)

## Input requirements

Mandatory fields:

Fluid fields

* p: pressure \[pa]
* p\_rgh: pressure \- hydrostatic contribution \[pa]
* U: velocity \[m/s]
* T: temperature \[K]

Solid Fields

* T: temperature \[K]

### Physical models

* [turbulence](../../../models/turbulence.md): `constant/turbulenceProperties`
* [heat transfer](../../../models/thermophysical.md#usage): `constant/thermophysicalModels`
* [finite volume options](../../../numerics/fvoptions.md#usage) : `constant/fvOptions` (optional)

### Solution controls

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

## Further information

Source code

* [chtMultiRegionFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/heatTransfer/chtMultiRegionFoam)

See also

* [laplacianFoam](../basic/laplacianFoam.md)
* [buoyantPimpleFoam](buoyantPimpleFoam.md)

Tutorials

* [chtMultiRegionFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionFoam)
