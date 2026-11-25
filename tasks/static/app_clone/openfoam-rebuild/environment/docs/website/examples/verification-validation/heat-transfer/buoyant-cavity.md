<!-- https://doc.openfoam.com/2606/examples/verification-validation/heat-transfer/buoyant-cavity -->

# Buoyant cavity

## Overview

* Solver: [buoyantSimpleFoam](../../../tools/processing/solvers/rtm/heat-transfer/buoyantSimpleFoam/index.md)
* Investigation into natural convection in a heat cavity
* Experimental case described by Betts and Bokhari
[6](../../../references.md#betts_experiments_2000)
* [buoyantCavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/buoyantCavity)

The case is described in the following figure

![Case description](../../../assets/images/boundary-conditions-small-9817eeb811aa8dfc0432bb997bc6ddc9.png)

A temperature difference of 19\.6K is maintained between the hot and cold;
the remaining patches are treated as adiabatic.

## Mesh

* 3D structured mesh created using [blockMesh](../../../tools/pre-processing/mesh/generation/blockMesh/index.md)

## Results

Results are presented for a selection of y/H locations

### Velocity distributions

![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/U1-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/U3-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/U4-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/U5-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/U6-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/U7-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/U9-400x400.png)
### Temperature distributions

![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/T1-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/T3-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/T4-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/T5-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/T6-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/T7-400x400.png)![](/img/examples/verification-validation/heat-transfer/buoyant-cavity/T9-400x400.png)
