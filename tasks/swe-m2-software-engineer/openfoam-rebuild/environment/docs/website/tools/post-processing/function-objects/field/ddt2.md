<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/ddt2 -->

# ddt2

## Description

The `ddt2` function object computes the magnitude or magnitude squared of
the Eulerian time derivative of an input volume field for time\-variant
simulations (not appropriate to steady\-state simulations).

The result can be further used for determining e.g. variance or RMS values.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `ddt2` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
ddt21
{
    // Mandatory entries (unmodifiable)
    type            ddt2;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields          (<field1> <field2> ... <fieldN>);

    // Optional entries (unmodifiable)
    mag             false;

    // Optional entries (runtime modifiable)
    result          d@@dt2;

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
| type | Type name: ddt2 | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of the operand fields | wordList | yes | \- |
| mag | Compute 'mag' instead of 'magSqr' | bool | no | false |
| result | Name of results | word | no | magSqr(ddt2(@@)) |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

A list of fields can contain exact names or regular expressions.
The token `\@\@` in the result name is replaced by the name of the source
field. In the special case of a single source field (specified as
a non\-regex), the `\@\@` token checking is suppressed.

The function object will skip over fields that appear to have
already been processed (ie, their names are similar to the output names).

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [ddt2](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/ddt2)

API:

* [Foam::functionObjects::ddt2](https://api.openfoam.com/2606/Foam_functionObjects_ddt2.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
