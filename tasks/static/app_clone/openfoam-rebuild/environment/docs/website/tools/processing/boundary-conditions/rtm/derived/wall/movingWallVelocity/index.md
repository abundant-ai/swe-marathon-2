<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/movingWallVelocity/ -->

# movingWallVelocity

## Description

The `movingWallVelocity` is a velocity boundary condition that provides
a condition for cases with moving walls.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                    movingWallVelocity;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `movingWallVelocity` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)
* [movingBox](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/overBuoyantPimpleDyMFoam/movingBox)

Source code:

* [movingWallVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/movingWallVelocity)

API:

* [Foam::movingWallVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_movingWallVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
