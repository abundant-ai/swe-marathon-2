<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/rotatingWallVelocity -->

# rotatingWallVelocity

## Description

The `rotatingWallVelocity` is a boundary condition that provides a rotational
velocity condition.

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
    type            rotatingWallVelocity;
    origin          <vector>;
    axis            <vector>;
    omega           <Function1<vector>>

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `rotatingWallVelocity` | word | yes | \- |
| `origin` | Origin of the rotation in Cartesian coordinates | vector | yes | \- |
| `axis` | Axis of rotation | vector | yes | \- |
| `omega` | Angular velocity of the frame \[rad/s] | Function1\<vector\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* [spinningDisk](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/kinematicParcelFoam/spinningDisk)
* [mixerVesselAMI](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/RAS/mixerVesselAMI)

Source code:

* [rotatingWallVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/rotatingWallVelocity)

API:

* [Foam::rotatingWallVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_rotatingWallVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
