<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/Q -->

# Q

## Description

The `Q` function object
computes the second invariant of the velocity gradient tensor \[s−2s^{\-2}s−2]:

Q\=12\[(tr(∇u))2−tr(∇u ∙ ∇u)] Q \= \\frac{1}{2}\\left\[\\left(\\mathrm{tr} \\left(\\grad \\u\\right)\\right)^2
 \- \\mathrm{tr} \\left(\\grad \\u \\dprod \\grad \\u\\right)\\right]Q\=21​\[(tr(∇u))2−tr(∇u∙∇u)]
`Q` iso\-surfaces are good indicators of turbulent flow structures.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volVectorField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `Q` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
Q1
{
    // Mandatory entries (unmodifiable)
    type            Q;
    libs            (fieldFunctionObjects);

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
| type | Type name: Q | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func Q

```

## Stored properties

### Fields

The Q field is stored on the mesh database, using the default name

```
Q

```

If the `field` entry is set to a value other than `U`, the default name
becomes

```
Q(<field>)

```

This can be overridden using the `result` entry.

## Sample output

## Further information

Tutorial:

* [pimpleFoam](../../../processing/solvers/rtm/incompressible/pimpleFoam.md) `surfaceMountedCube`
tutorial: [fullCase](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/surfaceMountedCube/fullCase)

Source code:

* [Q](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/Q)

API:

* [Foam::functionObjects::Q](https://api.openfoam.com/2606/Foam_functionObjects_Q.html)

Related:

* [Vorticity](vorticity.md)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+) ]
