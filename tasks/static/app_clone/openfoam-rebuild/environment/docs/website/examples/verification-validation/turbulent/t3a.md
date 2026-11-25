<!-- https://doc.openfoam.com/2606/examples/verification-validation/turbulent/t3a -->

# Turbulence transition T3A

## Overview

* Solver: [simpleFoam](../../../tools/processing/solvers/rtm/incompressible/simpleFoam/index.md)
* Incompressible
* Steady
* Turbulence transition modelled using the [kOmegaSST\-LM](../../../tools/processing/models/turbulence/ras/linear-evm/rtm/kOmegaSSTLM/index.md) model
* [T3A](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/T3A)

![Case description](../../../assets/images/boundary-conditions-small-eca9873e16fb47c3b8a9315c99979156.png)

## Mesh

* 2D structured mesh created using [blockMesh](../../../tools/pre-processing/mesh/generation/blockMesh/index.md)

![Mesh](../../../assets/images/mesh-600-4b66641ff8281c825c79b1977e997807.png)

![Close-up around the step](../../../assets/images/mesh-close-up-600-62792faec6edc4fbf84780b30d4701e1.png)

## Boundary conditions

* Ux: 5\.4 m/s
* Isotropic turbulence: 3\.3 %
* Viscosity ratio: 12

Fluid properties

* Kinematic viscosity: 1\.5e\-5 m2/s

## Results

![Turbulence kinetic energy](/img/examples/verification-validation/turbulent/t3a/k-400x400.png)![Wall shear stress](/img/examples/verification-validation/turbulent/t3a/tauw-400x400.png)
