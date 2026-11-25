<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/incompressible/simpleFoam -->

# simpleFoam

## Overview

* Category: [Incompressible](index.md)
* steady state
* incompressible
* [Turbulence](../../../models/turbulence.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Equations

The solver employs the [SIMPLE](../../pressure-velocity/simple.md)
algorithm to solve the continuity equation:

∇ ∙ u\=0 \\div \\u \= 0∇∙u\=0
and momentum equation:

∇ ∙ (u⊗u)−∇ ∙ R\=−∇p\+Su \\div ( \\u \\otimes \\u ) \- \\div \\vec{R} \= \- \\grad p \+ \\vec{S}\_u∇∙(u⊗u)−∇∙R\=−∇p\+Su​
Where:

u\\uu
: Velocity

ppp
: Kinematic pressure

R\\vec{R}R
: Stress tensor

Su\\vec{S}\_uSu​
: Momentum source

## Input requirements

Mandatory fields:

* p: [Kinematic pressure](../../algorithm-kinematic-pressure.md) \[m2/s2]
* U: velocity \[m/s]

### Physical models

* [turbulence](../../../models/turbulence.md):
`constant/turbulenceProperties`
* [finite volume options](../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

### Solution controls

[$FOAM\_CASE/system/fvSchemes](../../../../../fundamentals/case-structure/fvschemes.md) requirements:

* [time schemes](../../../numerics/schemes/time/rtm/steadyState.md): `steadyState`
* [gradient schemes](../../../numerics/schemes/gradient.md): `grad(U)`, `grad(p)`
* [divergence schemes](../../../numerics/schemes/divergence.md): `div(phi,U)`
* note: [Bounded schemes for steady state](../../../numerics/schemes/divergence.md#special-cases-steady-state)
* [laplacian schemes](../../../numerics/schemes/laplacian.md):
`laplacian(nuEff,U)`, `laplacian((1|A(U)),p)`

[$FOAM\_CASE/system/fvSolution](../../../../../fundamentals/case-structure/fvsolution.md) requirements:

* [solver entries](../../../numerics/solvers.md#options) for `U`, `p`

## Further information

Source code

* [simpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/incompressible/simpleFoam)

See also

* [pimpleFoam](pimpleFoam.md)
* [rhoSimpleFoam](../compressible/rhoSimpleFoam.md)

Tutorials

* [simpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam)
