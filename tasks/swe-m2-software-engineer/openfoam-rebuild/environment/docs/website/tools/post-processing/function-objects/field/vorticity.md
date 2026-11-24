<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/vorticity -->

# vorticity

## Description

The `vorticity` function object
computes the vorticity, the curl of the velocity.

Ω\=∇×u \\vec \\Omega \= \\nabla \\times \\uΩ\=∇×u
where:

Ω\\vec \\OmegaΩ
: Vorticity vector \[1/s]

u\\uu
: Velocity \[m/s]

## Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volVectorField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volVectorField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `vorticity` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
vorticity1
{
    // Mandatory entries (unmodifiable)
    type        vorticity;
    libs        (fieldFunctionObjects);

    // Optional (inherited) entries
    field           <inpField>;
    result          <fieldResult>;
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: vorticity | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func vorticity

```

## Sample output

## Further information

Tutorial:

* [pimpleFoam](../../../processing/solvers/rtm/incompressible/pimpleFoam.md) `surfaceMountedCube` tutorial:
[fullCase](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/surfaceMountedCube/fullCase)

Source code:

* [vorticity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/vorticity)

API:

* [Foam::functionObjects::vorticity](https://api.openfoam.com/2606/Foam_functionObjects_vorticity.html)

Related:

* [Q criterion](Q.md)

**History:** Introduced in version [v1812](https://www.openfoam.com/news/main-news/openfoam-v1812) ]
