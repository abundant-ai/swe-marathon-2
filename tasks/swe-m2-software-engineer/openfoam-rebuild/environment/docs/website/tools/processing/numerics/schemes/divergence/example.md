<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence/example -->

# Divergence scheme example

* Solver: [scalarTransportFoam](../../../solvers/rtm/basic/scalarTransportFoam/index.md)
* Repository link: [divergenceExample](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/schemes/divergenceExample)

## Introduction

This example case comprises a 2\-D box section, across which a uniform flow
is applied. A passive scalar is introduced across the left boundary, and
transported across the domain. By looking at the profile of the scalar part
way across the section, we can determine the characteristics of our divergence
scheme selection.

## Case set\-up

A frozen flow field is set by the `U` field, and the passive scalar by the
`T` field. The time step is set to 5e\-3s, leading to a maximum Courant
number of 0\.5\. The impact of the choice of numerical scheme is assessed by
varying the `div` scheme entry of the [fvSchemes](../index.md) file:

```
divSchemes
{
    div(phi,T)      Gauss <interpolation scheme>
}

```

### Mesh

A 2\-D square domain with side length 1m is employed, with two mesh variants: 50x50
uniform quad cells and a triangle mesh:

![Case set-up](/img/tools/processing/numerics/schemes/divergence/example/images/example-divergence-schematic.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-mesh.png)
Results are sampled at the location shown by the dashed line.

### Boundary conditions

The velocity is set to a constant value of (1,1,0\) m/s across the domain
with the following boundary conditions:

| Patch | Type | Value |
| --- | --- | --- |
| left | fixedValue | (1,1,0\) |
| right | zeroGradient |  |
| top | zeroGradient |  |
| bottom | fixedValue | (1,1,0\) |
| frontAndBack | empty |  |

The passive scalar is initialised to zero and evolved with the velocity
field by assigning a value of 1 at the `left` boundary:

| Patch | Type | Value |
| --- | --- | --- |
| left | fixedValue | 1 |
| right | zeroGradient |  |
| top | zeroGradient |  |
| bottom | fixedValue | 0 |
| frontAndBack | empty |  |

## Results

The following sequence of images show the steady results for the spatial
distribution of the passive scalar.
First order methods such as [upwind](rtm/upwind/index.md)
show their diffusive characteristic, whereby the sharp profile is heavily
smeared as the flow is not aligned with the mesh:

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-upwind.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-upwind.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-upwind-result.png)
\| \| [upwind](rtm/upwind/index.md) \| \|
The [linear](rtm/linear/index.md) scheme is a second order
method, able to better preserve the step profile, but at the expense of
unboundedness:

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-linear.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-linear.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-linear-result.png)
\| \| [linear](rtm/linear/index.md) \| \|
The remaining methods provide a blend between first order upwind and
second order linear methods:

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-Minmod.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-Minmod.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-Minmod-result.png)
\| \| [Minmod](rtm/Minmod/index.md) \| \|

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-SFCD.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-SFCD.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-SFCD-result.png)
\| \| [SFCD](../../../../../index.md#schemes-divergence-sfcd) \| \|

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-limitedLinear-coeff10.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-limitedLinear-coeff10.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-limitedLinear_10-result.png)
\| \| [limitedLinear 1\.0](rtm/limitedLinear/index.md) \| \|

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-vanLeer.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-vanLeer.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-vanLeer-result.png)
\| \| [vanLeer](rtm/vanLeer/index.md) \| \|

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-MUSCL.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-MUSCL.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-MUSCL-result.png)
\| \| [MUSCL](rtm/MUSCL/index.md) \| \|

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-midPoint.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-midPoint.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-midPoint-result.png)
\| \| [midPoint](rtm/midPoint/index.md) \- equivalent to [linear](rtm/linear/index.md) on isotropic structured meshes \| \|

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-linearUpwind.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-linearUpwind.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-linearUpwind_gradU-result.png)
\| \| [linearUpwind](rtm/linearUpwind/index.md) \| \|

![](/img/tools/processing/numerics/schemes/divergence/example/images/quad/divergence-test-quad-QUICK.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/tri/divergence-test-tri-QUICK.png)![](/img/tools/processing/numerics/schemes/divergence/example/images/graphs/divergence-test-QUICK-result.png)
\| \| [QUICK](rtm/QUICK/index.md) \| \|
