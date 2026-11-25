<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldCoordinateSystemTransform -->

# fieldCoordinateSystemTransform

## Description

The `fieldCoordinateSystemTransform` function object is used to convert a field
from the global Cartesian system to a local user\-specified co\-ordinate system.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field(s)` | `$FOAM_CASE/<time>/<inpField>s` |
| output file | \- | \- |
| output field | `{vol,surface}<Type>Field(s)` | `$FOAM_CASE/<time>/<outField>s` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `fieldCoordinateSystemTransform` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

To transform the global velocity into a local cylindrical system defined by

```
origin: (0 0 0)
axis:   (0 0 1)
radius: (1 0 0)

```

the following entries may be used:

```
transform1
{
    // Mandatory entries (unmodifiable)
    type            fieldCoordinateSystemTransform;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields          (U);
    coordinateSystem
    {
        origin          (0 0 0);
        coordinateRotation
        {
            type            axesRotation;
            e3              (0 0 1);
            e1              (1 0 0);
        }
    }

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
| type | Type name: fieldCoordinateSystemTransform | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of the operand fields | wordList | yes | \- |
| coordinateSystem | Local coordinate system | dict | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Stored properties

### Fields

Each input field is transformed into a field with the name:

```
<field>:Transformed

```

For the example above, the `U` field is transformed into

```
U:Transformed

```

which is registered to the mesh database and written to the time directories
according to the `writeControl` entry.

## Further information

Tutorial:

* [pipeCyclic](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/pipeCyclic)

Source code:

* [fieldCoordinateSystemTransform](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldCoordinateSystemTransform)

API:

* [Foam::functionObjects::fieldCoordinateSystemTransform](https://api.openfoam.com/2606/Foam_functionObjects_fieldCoordinateSystemTransform.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
