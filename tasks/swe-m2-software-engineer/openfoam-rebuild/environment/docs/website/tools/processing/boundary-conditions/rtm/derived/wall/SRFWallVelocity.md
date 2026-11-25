<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/SRFWallVelocity -->

# SRFWallVelocity

## Description

The `SRFWallVelocity` is a boundary condition that provides
wall\-velocity condition to be used in conjunction with the single rotating
frame (SRF) model.

The condition applies the appropriate rotation transformation in time and
space to determine the local SRF velocity of the wall.

up\=−up,srf \\u\_p \= \- \\u\_{p,srf}up​\=−up,srf​
where:

| Property | Description |
| --- | --- |
| up\\u\_pup​ | Patch velocity \[m/s] |
| up,srf\\u\_{p,srf}up,srf​ | SRF velocity |

The normal component of up\\u\_pup​ is removed to ensure zero wall\-flux even
if the wall patch faces are irregular.

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
    type            SRFWallVelocity;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `SRFWallVelocity` | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [SRFWallVelocityFvPatchVectorField](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/cfdTools/general/SRF/derivedFvPatchFields/SRFWallVelocityFvPatchVectorField)

API:

* [Foam::SRFWallVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_SRFWallVelocityFvPatchVectorField.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
