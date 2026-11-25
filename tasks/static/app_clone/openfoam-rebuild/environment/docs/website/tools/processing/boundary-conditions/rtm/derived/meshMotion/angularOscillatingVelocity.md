<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/angularOscillatingVelocity -->

# angularOscillatingVelocity

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
    type            angularOscillatingVelocity;
    axis            <vector>;
    origin          <vector>;
    angle0          <scalar>;
    amplitude       <scalar>;
    omega           <scalar>;

    // Optional entries
    p0              <pointField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `angularOscillatingVelocity` | word | yes | \- |
| `axis` | Rotation axis | vector | yes | \- |
| `origin` | Rotation origin | vector | yes | \- |
| `angle0` | Initial angle | scalar | yes | \- |
| `amplitude` | Oscillation amplitude | scalar | yes | \- |
| `omega` | Rotation speed | scalar | yes | \- |
| `p0` | Initial displacement field | pointField | no | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [angularOscillatingVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/angularOscillatingVelocity)

API:

* [Foam::angularOscillatingVelocityPointPatchVectorField](https://api.openfoam.com/2606/Foam_angularOscillatingVelocityPointPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
