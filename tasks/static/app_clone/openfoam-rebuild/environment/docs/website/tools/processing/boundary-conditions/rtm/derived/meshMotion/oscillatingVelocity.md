<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/oscillatingVelocity -->

# oscillatingVelocity

## Description

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
    type            oscillatingVelocity;
    amplitude       <vector>;
    omega           <scalar>;

    // Optional entries
    p0              <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `oscillatingVelocity` | word | yes | \- |
| `amplitude` | Oscillation amplitude | scalar | yes | \- |
| `omega` | Rotation speed | scalar | yes | \- |
| `p0` | Initial displacement field | pointField | no | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [oscillatingVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/oscillatingVelocity)

API:

* [Foam::oscillatingVelocityPointPatchVectorField](https://api.openfoam.com/2606/Foam_oscillatingVelocityPointPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
