<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/surfaceInterpolate -->

# surfaceInterpolate

## Description

The `surfaceInterpolate` function object
linearly interpolates volume fields to generate surface fields.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `surface<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `surfaceInterpolate` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
surfaceInterpolate1
{
    // Mandatory entries (unmodifiable)
    type            surfaceInterpolate;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields      ((<inpField1> <outField1>) ... (<inpFieldN> <outFieldN>));

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
| type | Type name: surfaceInterpolate | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of operand and output fields | wordList | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [surfaceInterpolate](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/surfaceInterpolate)

API:

* [Foam::functionObjects::surfaceInterpolate](https://api.openfoam.com/2606/Foam_functionObjects_surfaceInterpolate.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
