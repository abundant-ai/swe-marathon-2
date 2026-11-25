<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/gradient/example -->

# Gradient scheme example

## Introduction

The test case comprises a 2\-D section comprising extruded triangle cells.
An initial field is assigned the mesh cell centre values such that
the computed gradient should take the value of 1 in each co\-ordinate direction.
By changing the choice of gradient scheme we can observe how each performs.

## Case set\-up

Gradient schemes under test:

* Gauss linear
* Gauss pointLinear
* leastSquares

Interpolation schemes under test:

* Unlimited
* [cellLimited](rtm/cellLimited/index.md)
* [cellMDLimited](rtm/cellMDLimited/index.md)
* [faceLimited](rtm/faceLimited/index.md)
* [faceMDLimited](rtm/faceMDLimited/index.md)

### Boundary conditions

Only the left and right domain boundaries are set to physical patch types; the
remainder are set to the [empty](../../../boundary-conditions/rtm/constraint/empty/index.md)
constraint to enforce the 2\-D system.

### Mesh

The mesh comprises extruded triangle cells with low non\-orthogonality with
average and maximum values of 7 and 26 deg, respectively.

### Scheme controls

```
grad(Cc)        <scheme>

```

## Results

The following images show the percentage error of the magnitude of the gradient
of the cell centres, defined as:

error\=100∣∇(Cc)∣−20\.520\.5 \\textrm{error} \= 100 \\frac{\\left\|\\grad(C\_c)\\right\| \- 2^{0\.5}}{2^{0\.5}}error\=10020\.5∣∇(Cc​)∣−20\.5​
The range is set to \+/\- 10% for all images.

### Unlimited

![Gauss linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-Gauss-linear.png)![Gauss point linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-Gauss-pointLinear.png)![Least squares](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-leastSquares.png)
### Cell limited

![Gauss linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-cellLimited-Gauss-linear-1.png)![Gauss point linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-cellLimited-Gauss-pointLinear-1.png)![Least squares](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-cellLimited-leastSquares-1.png)
### Face limited

![Gauss linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-faceLimited-Gauss-linear-1.png)![Gauss point linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-faceLimited-Gauss-pointLinear-1.png)![Least squares](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-faceLimited-leastSquares-1.png)
### Multi\-directional cell limited

![Gauss linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-cellMDLimited-Gauss-linear-1.png)![Gauss point linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-cellMDLimited-Gauss-pointLinear-1.png)![Least squares](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-cellMDLimited-leastSquares-1.png)
### Multi\-directional face limited

![Gauss linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-faceMDLimited-Gauss-linear-1.png)![Gauss point linear](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-faceMDLimited-Gauss-pointLinear-1.png)![Least squares](/img/tools/processing/numerics/schemes/gradient/example/gradient-test-faceMDLimited-leastSquares-1.png)
