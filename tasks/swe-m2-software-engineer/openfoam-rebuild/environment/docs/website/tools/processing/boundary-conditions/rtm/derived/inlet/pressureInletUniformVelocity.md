<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/pressureInletUniformVelocity -->

# pressureInletUniformVelocity

## Description

The `pressureInletUniformVelocity` is a velocity boundary condition that
calculates uniform inflow velocity by averaging the flux over the patch,
and then applying it in the direction normal to the patch faces.

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
    type                pressureInletUniformVelocity;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `pressureInletUniformVelocity` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::pressureInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureInletVelocityFvPatchVectorField.html)

## Further information

Tutorial:

* N/A

Source code:

* [pressureInletUniformVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressureInletUniformVelocity)

API:

* [Foam::pressureInletUniformVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureInletUniformVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
