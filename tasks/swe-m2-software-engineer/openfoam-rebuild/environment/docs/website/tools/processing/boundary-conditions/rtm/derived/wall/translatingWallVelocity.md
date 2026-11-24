<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/translatingWallVelocity -->

# translatingWallVelocity

## Description

The `translatingWallVelocity` is a velocity boundary condition for translational
motion on walls that sets the velocity parallel to the wall to a given value,
e.g. to approximate a moving ground plane. The patch normal velocity component
is set to zero.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            translatingWallVelocity;
    U               <Function1<vector>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `translatingWallVelocity` | word | yes | \- |
| `U` | Translational velocity | Function1\<vector\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* [tank3D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/driftFluxFoam/RAS/tank3D)

Source code:

* [translatingWallVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/translatingWallVelocity)

API:

* [Foam::translatingWallVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_translatingWallVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.7\.0](https://www.openfoam.com/news/main-news/openfoam-1.7.0)
