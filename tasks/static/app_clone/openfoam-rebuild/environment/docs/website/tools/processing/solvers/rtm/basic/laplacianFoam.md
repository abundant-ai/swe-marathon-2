<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/basic/laplacianFoam -->

# laplacianFoam

## Overview

* Category: [Basic](index.md)
* Steady state or transient

## Equations

The solver evolves a scalar, TTT, using the equation:

∂∂t(T)−∇ ∙ (DT∇T)\=ST \\ddt{T} \- \\div (D\_T \\grad T) \= S\_T∂t∂​(T)−∇∙(DT​∇T)\=ST​
## Input requirements

Mandatory fields:

* Transported field: `T`: scalar \[\-]

### Physical models

* Transport `$FOAM_CASE/constant/transportProperties` requirements:

```
// Diffusion coefficient \[m2/s\]
DT              4e-05;

```

### Solution controls

[$FOAM\_CASE/system/fvSchemes](../../../../../fundamentals/case-structure/fvschemes.md) requirements:

* [time schemes](../../../numerics/schemes/time.md): `ddt(T)`
* [gradient schemes](../../../numerics/schemes/gradient.md): `grad(T)`
* [laplacian schemes](../../../numerics/schemes/laplacian.md): `laplacian(DT,T)`

[$FOAM\_CASE/system/fvSolution](../../../../../fundamentals/case-structure/fvsolution.md) requirements:

* [solver entry](../../../numerics/solvers.md#options) for `T`

## Further information

Source code

* [laplacianFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/basic/laplacianFoam)

See also

* [simpleFoam](../incompressible/simpleFoam.md)

Tutorials

* [laplacianFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/basic/laplacianFoam)
