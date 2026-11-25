<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/zeroGradient -->

# zeroGradient

## Description

The `zeroGradient` function object creates a volume field with zero\-gradient
boundary conditions from another volume field.

The result can be used, for example, to post\-process near\-wall field values.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `zeroGradient` function object by using `functions`
sub\-dictionary in `system/controlDict` file:

```
zeroGradient1
{
    // Mandatory entries (unmodifiable)
    type            zeroGradient;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields          (<field1> ... <fieldN>); \\(U "(T|k|epsilon|omega)");

    // Optional entries (runtime modifiable)
    result          @@<name>;

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
| type | Type name: zeroGradient | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Name of the operand fields | wordList | yes | \- |
| result | Name of the output field | word | no | zeroGradient(@@) |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

A list of fields can contain exact names or regular expressions.
The token '@@' in the result name is replaced by the name of the source
field. In the special case of a single source field (specified as
a non\-regex), the '@@' token checking is suppressed.

The function object will skip over fields that would not benefit e.g.
`processor`, `empty`, `zeroGradient`, `symmetry` patches.
This check should also prevent processing fields multiple times.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [zeroGradient](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/zeroGradient)

API:

* [Foam::functionObjects::zeroGradient](https://api.openfoam.com/2606/Foam_functionObjects_zeroGradient.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
