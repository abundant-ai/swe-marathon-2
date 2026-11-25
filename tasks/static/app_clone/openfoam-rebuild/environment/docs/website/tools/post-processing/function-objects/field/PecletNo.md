<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/PecletNo -->

# PecletNo

## Description

The `PecletNo` function object
computes the Peclet number as a `surfaceScalarField.`

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `surfaceScalarField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `surfaceScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `PecletNo` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
PecletNo1
{
    // Mandatory entries (unmodifiable)
    type            PecletNo;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    rho             rho;

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
| type | Type name: PecletNo | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| rho | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func PecletNo

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [PecletNo](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/PecletNo)

API:

* [Foam::functionObjects::PecletNo](https://api.openfoam.com/2606/Foam_functionObjects_PecletNo.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
