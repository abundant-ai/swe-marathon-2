<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/time/example -->

# Time scheme example

* Solver: [scalarTransportFoam](../../../solvers/rtm/basic/scalarTransportFoam/index.md)
* TODO: Repository link: TBA

## Introduction

The test case comprises a 2\-D box section, across which a uniform flow
is applied. A passive scalar is introduced in a circular region at the start
time, and transported across the domain. By looking at the profile of the
scalar across the section, we can determine the characteristics of our
time scheme selection.

## Case set\-up

The impact of the choice of time scheme is assessed by
varying the `ddt` scheme entry of the [fvSchemes](../../../../../fundamentals/case-structure/fvschemes/index.md) file:

```
ddtSchemes
{
    ddt(phi)        <time scheme>
}

```

### Boundary conditions

Velocity boundary conditions

| Patch | Type | Value |
| --- | --- | --- |
| left | fixedValue | (1,1,0\) |
| right | zeroGradient |  |
| top | zeroGradient |  |
| bottom | fixedValue | (1,1,0\) |
| frontAndBack | empty |  |

Scalar boundary conditions

| Patch | Type | Value |
| --- | --- | --- |
| left | fixedValue | 0 |
| right | zeroGradient |  |
| top | zeroGradient |  |
| bottom | fixedValue | 0 |
| frontAndBack | empty |  |

![Initial field](data:image/png;base64,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)

### Mesh

![Case set-up](../../../../../assets/images/divergence-test-mesh-c733948f4e377db647dbe27fce355120.png)

## Results

### Euler results

![Time 1](/img/tools/processing/numerics/schemes/time/example/images/time-test-euler-002.png)![Time 2](/img/tools/processing/numerics/schemes/time/example/images/time-test-euler-007.png)![Time 3](/img/tools/processing/numerics/schemes/time/example/images/time-test-euler-012.png)
### backward results

![Time 1](/img/tools/processing/numerics/schemes/time/example/images/time-test-backward-002.png)![Time 2](/img/tools/processing/numerics/schemes/time/example/images/time-test-backward-007.png)![Time 3](/img/tools/processing/numerics/schemes/time/example/images/time-test-backward-012.png)
### Crank\-Nicolson results

![Time 1](/img/tools/processing/numerics/schemes/time/example/images/time-test-crank-nicolson-002.png)![Time 2](/img/tools/processing/numerics/schemes/time/example/images/time-test-crank-nicolson-007.png)![Time 3](/img/tools/processing/numerics/schemes/time/example/images/time-test-crank-nicolson-012.png)
