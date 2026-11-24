<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/subtract -->

# subtract

## Description

The `subtract` function object
subtracts a given list of (at least one or more)
fields from a field and produces a new field, where the fields possess the
same sizes and dimensions:

```
fieldResult = field1 - field2 - ... - fieldN

```

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field(s)` | `$FOAM_CASE/<time>/<inpField>s` |
| output file | \- | \- |
| output field | `{vol,surface}<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `add` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
subtract1
{
    // Mandatory entries (unmodifiable)
    type            subtract;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entry (runtime modifiable)
    fields          (<field1> <field2> ... <fieldN>);

    // Optional (inherited) entries
    result          <fieldResult>;
    region          region0;
    subRegion       region0;
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

The minimal set of entries comprise:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: subtract | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Names of the operand fields | wordList | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldsExpression](fieldsExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "subtract(<field1>, <field2>, ..., <fieldN>)"

```

## Stored properties

### Fields

The `subtract` function object is stored on the mesh database,
using the default name:

```
subtract(<field1>,<field2>,...,<fieldN>)

```

This can be overridden by using the `result` entry.

## Further information

Tutorial:

* [bubbleColumn](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/twoPhaseEulerFoam/laminar/bubbleColumn)
* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [subtract](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/subtract)

API:

* [Foam::functionObjects::subtract](https://api.openfoam.com/2606/Foam_functionObjects_subtract.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
