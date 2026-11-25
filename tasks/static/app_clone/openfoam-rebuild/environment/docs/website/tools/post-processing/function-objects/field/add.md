<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/add -->

# add

## Description

The `add` function object sums a given list of (at least two or more) fields
and outputs the result into a new field, where the fields possess the same
sizes and dimensions:

```
fieldResult = field1 + field2 + ... + fieldN

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
add1
{
    // Mandatory entries    (unmodifiable)
    type            add;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entries    (runtime modifiable)
    fields          (<field1> <field2> ... <fieldN>);

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
| type | Type name: add | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of the operand fields | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldsExpression](fieldsExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "add(<field1>, <field2>, ..., <fieldN>)"

```

## Stored properties

### Fields

The `add` function object result field is stored on the mesh database,
using the default name:

```
add(<field1>,<field2>,...,<fieldN>)

```

This can be overridden by using the `result` entry.

## Further information

Tutorial:

* [bubbleColumn](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/twoPhaseEulerFoam/laminar/bubbleColumn)
* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* API:
* [Foam::functionObjects::add](https://api.openfoam.com/2606/Foam_functionObjects_add.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
