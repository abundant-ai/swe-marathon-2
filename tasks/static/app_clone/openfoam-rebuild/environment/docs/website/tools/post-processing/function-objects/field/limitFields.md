<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/limitFields -->

# limitFields

## Description

The `limitFields` function object
limits input fields to user\-specified min and max bounds.

For non\-scalar types of input fields, the user limit is used to create a
scaling factor using the field magnitudes.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `limitFields` function object by using `functions` sub\-dictionary
in `system/controlDict` file:

```
limitFields1
{
    // Mandatory entries (unmodifiable)
    type            limitFields;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields          (U);
    limit           max;
    max             100;

    // Optional (inherited) entries
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
| type | Type name: limitFields | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | List of fields to process | wordList | yes | \- |
| limit | Bound to limit \- see below | word | yes | \- |
| min | Min limit value | scalar | conditional | \- |
| max | Max limit value | scalar | conditional | \- |

Options for the `limit` entry:

* `min` : Specify a minimum value
* `max` : Specify a maximum value
* `both` : Specify a minimum value and a maximum value

The inherited entries are elaborated in:

* [functionObject](../index.md)

Example by using the `postProcess` utility:

```
postProcess -func limitFields

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [limitFields](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/limitFields)

API:

* [Foam::functionObjects::limitFields](https://api.openfoam.com/2606/Foam_functionObjects_limitFields.html)

**History:** Introduced in version [v1912](https://www.openfoam.com/news/main-news/openfoam-v1912)
