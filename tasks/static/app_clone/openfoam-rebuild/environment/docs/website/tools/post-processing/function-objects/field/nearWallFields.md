<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/nearWallFields -->

# nearWallFields

## Description

The `nearWallFields` function object
samples near\-patch volume fields within an input distance range.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `nearWallFields` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
nearWallFields1
{
    // Mandatory entries (unmodifiable)
    type            nearWallFields;
    libs            (fieldFunctionObjects);
    fields
    (
        (<field1> <outField1>)
        (<field2> <outField2>)
    );
    patches         (<patch1> <patch2> ... <patchN>);
    distance        0.01;

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
| type | Type name: nearWallFields | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of input\-output fields | wordHashTable | yes | \- |
| patches | Names of patches to sample | wordList | yes | \- |
| distance | Wall\-normal distance from patch to sample | scalar | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [nearWallFields](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/nearWallFields)

API:

* [Foam::functionObjects::nearWallFields](https://api.openfoam.com/2606/Foam_functionObjects_nearWallFields.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
