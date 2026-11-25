<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/Lambda2 -->

# Lambda2

## Description

The `Lambda2` function object computes the second largest eigenvalue of
the sum of the square of the symmetrical and anti\-symmetrical parts of
the velocity gradient tensor.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volVectorField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `Lambda2` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
Lambda21
{
    // Mandatory entries (unmodifiable)
    type            Lambda2;
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
| type | Type name: Lambda2 | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func Lambda2

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [Lambda2](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/Lambda2)

API:

* [Foam::functionObjects::Lambda2](https://api.openfoam.com/2606/Foam_functionObjects_Lambda2.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
