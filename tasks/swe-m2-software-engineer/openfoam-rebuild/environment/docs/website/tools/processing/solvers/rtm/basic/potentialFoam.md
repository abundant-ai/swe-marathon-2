<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/basic/potentialFoam -->

# potentialFoam

Solves for the velocity potential to provide velocity and incompressible flux
fields, typically used to initialise viscous calculations.

## Overview

* Category: [Basic](index.md)
* steady state
* incompressible

## Equations

Solves for the velocity potential, Φ\\PhiΦ, using the equation

∇2Φ\=∇ ∙ ϕ \\laplacian \\Phi \= \\div \\phi∇2Φ\=∇∙ϕ
where the volumetric flux, ϕ\\phiϕ is given by dotting the interpolated
velocity with the face area vectors:

ϕ\=uf ∙ Sf \\phi \= \\u\_f \\dprod \\vec{S}\_fϕ\=uf​∙Sf​
Finally the cell centre velocity is derived by reconstructing the volumetric
flux.

## Input requirements

Mandatory fields:

* `p`: kinematic pressure \[m2/s2] or `Phi`: velocity potential \[m2/s]
* `U`: velocity \[m/s]

### Physical models

* None

### Solution controls

[$FOAM\_CASE/system/fvSchemes](../../../../../fundamentals/case-structure/fvschemes.md) requirements:

* [gradient schemes](../../../numerics/schemes/gradient.md): `grad(Phi)`
* [laplacian schemes](../../../numerics/schemes/laplacian.md): `laplacian(1,Phi)`

[$FOAM\_CASE/system/fvSolution](../../../../../fundamentals/case-structure/fvsolution.md) requirements:

* [solver entry](../../../numerics/solvers.md#options) for `Phi`

### Command line options

* `-pName <name>`: name of the pressure field
* `-initialiseUBCs`: initialise the velocity boundary conditions prior to
computing the volumetric flux
* `-writePhi`: write the velocity potential field
* `-writep`: write the Euler pressure field

## Further information

Source code

* [potentialFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/basic/potentialFoam)

See also

* [simpleFoam](../incompressible/simpleFoam.md)

Tutorials

* [potentialFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/basic/potentialFoam)
