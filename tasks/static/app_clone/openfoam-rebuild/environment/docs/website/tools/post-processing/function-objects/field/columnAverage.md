<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/columnAverage -->

# columnAverage

## Description

The `columnAverage` function object computes the arithmetic average of given
quantities along columns of cells in a given direction for **structured\-like
layered meshes**. It is, for example, useful for channel\-like cases where
spanwise average of a field is desired. However, the `columnAverage` function
object **does not operate on arbitrary unstructured meshes**.

The `columnAverage` function object, for each patch face, calculates the average
value of all cells attached in the patch face normal direction, and then pushes
the average value back to *all cells in the column*.

The `columnAverage` function object can be applied to any volume fields,
generating a volume field. However, the operation **cannot be applied onto
surface fields**, e.g `wallShearStress`.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `columnAverage` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
columnAverage1
{
    // Mandatory entries (unmodifiable)
    type            columnAverage;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    patches         (<patch1> <patch2> ... <patchN>)
    fields          (<field1> <field2> ... <fieldN>);

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
| type | Type name: columnAverage | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| patches | Names of patches to collapse onto | word | yes | \- |
| fields | Names of the operand fields | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [transient](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/periodicHill/transient)

Source code:

* [columnAverage](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/columnAverage)

API:

* [Foam::functionObjects::columnAverage](https://api.openfoam.com/2606/Foam_functionObjects_columnAverage.html)

**History:** Introduced in version [v1812](https://www.openfoam.com/news/main-news/openfoam-v1812)
