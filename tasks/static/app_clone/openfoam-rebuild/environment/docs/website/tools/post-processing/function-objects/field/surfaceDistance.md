<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/surfaceDistance -->

# surfaceDistance

## Description

The `surfaceDistance` function object
computes the distance to the nearest surface from a given geometry.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/surfaceDistance` |

## Usage

Example of the `surfaceDistance` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
surfaceDistance1
{
    // Mandatory entries (unmodifiable)
    type            surfaceDistance;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    geometry
    {
        motorBike.obj
        {
            type triSurfaceMesh;
            name motorBike;
        }
    }

    // Optional entries (runtime modifiable)
    calculateCells  true;

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
| type | Type name: surfaceDistance | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| geometry | Surface details | dict | yes | \- |
| calculateCells | Calculate distance from cell | bool | no | true |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [surfaceDistance](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/surfaceDistance)

API:

* [Foam::functionObjects::surfaceDistance](https://api.openfoam.com/2606/Foam_functionObjects_surfaceDistance.html)

**History:** Introduced in version [v1912](https://www.openfoam.com/news/main-news/openfoam-v1912)
