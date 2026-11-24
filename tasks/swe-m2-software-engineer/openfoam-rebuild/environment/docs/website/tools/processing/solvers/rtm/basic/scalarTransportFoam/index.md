<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/basic/scalarTransportFoam/ -->

# scalarTransportFoam

## Overview

* Category: [Basic](../index.md)
* transient
* incompressible

## Equations

Evolves a transport equation for the scalar TTT

∂∂t(T)\+∇ ∙ (uT)−∇ ∙ (DT∇T)\=ST \\ddt{T} \+ \\div (\\u T) \- \\div (D\_T \\grad T ) \= S\_{T}∂t∂​(T)\+∇∙(uT)−∇∙(DT​∇T)\=ST​
## Input requirements

Mandatory fields:

* `U`: velocity \[m/s]
* `T`: scalar \[\-]

### Physical models

* Transport `$FOAM_CASE/constant/transportProperties` requirements:

```
// Diffusion coefficient \[m2/s\]
DT              4e-05;

```

### Solution controls

[$FOAM\_CASE/system/fvSchemes](../../../../../../fundamentals/case-structure/fvschemes.md) requirements:

* [time schemes](../../../../numerics/schemes/time.md): `ddt(T)`
* [gradient schemes](../../../../numerics/schemes/gradient.md): `grad(T)`
* [divergence schemes](../../../../numerics/schemes/divergence.md): `div(phi,T)`
* [laplacian schemes](../../../../numerics/schemes/laplacian.md): `laplacian(DT,T)`

[$FOAM\_CASE/system/fvSolution](../../../../../../fundamentals/case-structure/fvsolution.md) requirements:

* [solver entry](../../../../numerics/solvers.md#options) for `T`

## Further information

Source code

* [scalarTransportFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/basic/scalarTransportFoam)

See also

* [icoFoam](../../incompressible/icoFoam.md)
* [pisoFoam](../../incompressible/pisoFoam.md)

Tutorials

* [scalarTransportFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/basic/scalarTransportFoam)
