<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/mag -->

# mag

## Description

The `mag` function object computes the magnitude of an input field.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `{vol,surface}ScalarField` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `mag` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
mag1
{
    // Mandatory entries (unmodifiable)
    type            mag;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entries (runtime modifiable)
    field           <inpField>;

    // Optional (inherited) entries
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
| type | Type name: mag | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "mag(<field>)"

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [mag](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/mag)

API:

* [Foam::functionObjects::mag](https://api.openfoam.com/2606/Foam_functionObjects_mag.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
